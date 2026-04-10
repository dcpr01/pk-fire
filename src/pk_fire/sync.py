"""
Core sync engine: reads Anki's SQLite DB and writes Obsidian markdown.

Incremental by default — only new cards are appended to deck pages.
Topic hub pages are rebuilt each sync to stay complete.
"""

import sqlite3
import os
import re
import json
import html as html_mod
import shutil
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path.home() / ".pk-fire.json"


def _load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def generate_topic_rules(anki_db):
    """Scan Anki deck names and tags to generate topic rules for this user."""
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # Collect deck names
    cursor.execute("SELECT name FROM decks")
    deck_names = {row[0] for row in cursor.fetchall()}

    # Collect all Anki tags (flattened from hierarchical tags like JS::Arrays)
    cursor.execute("SELECT tags FROM notes WHERE tags != ''")
    all_tags = set()
    for (tags_str,) in cursor.fetchall():
        for tag in tags_str.split():
            for part in tag.split('::'):
                part = part.strip()
                if part:
                    all_tags.add(part)

    conn.close()

    # Build rules from deck names and tags, skipping generic ones
    skip = {'Default', 'Uncategorized', ''}
    topics = set()
    for name in deck_names | all_tags:
        # Use the leaf name for nested decks (e.g. "CS::Web Dev" -> "Web Dev")
        leaf = name.split('::')[-1].strip()
        if leaf and leaf not in skip:
            topics.add(leaf)

    rules = []
    for topic in sorted(topics):
        # Create a simple word-boundary regex for the topic name
        pattern = r"\b" + re.escape(topic) + r"\b"
        rules.append([topic, [pattern]])

    return rules


def load_topic_rules(anki_db=None):
    """Load topic rules from config, generating on first run if needed."""
    config = _load_config()
    rules = config.get('topic_rules')

    if rules is None and anki_db:
        print("  Generating topic rules from your Anki decks...")
        rules = generate_topic_rules(anki_db)
        config['topic_rules'] = rules
        _save_config(config)
        print(f"  Generated {len(rules)} topic rules (saved to ~/.pk-fire.json)")

    return rules or []


def compile_topics(rules=None):
    if rules is None:
        rules = load_topic_rules()
    compiled = []
    for raw_tag, patterns in rules:
        if raw_tag.endswith("__casesensitive"):
            tag = raw_tag.removesuffix("__casesensitive")
            pats = [re.compile(p) for p in patterns]
        else:
            tag = raw_tag
            pats = [re.compile(p, re.IGNORECASE) for p in patterns]
        compiled.append((tag, pats))
    return compiled


def strip_html(text):
    """Remove HTML tags and decode entities, converting to markdown."""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<pre[^>]*>', '\n```\n', text)
    text = re.sub(r'</pre>', '\n```\n', text)
    text = re.sub(r'<code>', '`', text)
    text = re.sub(r'</code>', '`', text)
    text = re.sub(r'<strong>|<b>', '**', text)
    text = re.sub(r'</strong>|</b>', '**', text)
    text = re.sub(r'<em>|<i>', '*', text)
    text = re.sub(r'</em>|</i>', '*', text)
    text = re.sub(r'<li>', '\n- ', text)
    text = re.sub(r'</li>', '', text)
    text = re.sub(r'<img\s+src="([^"]+)"[^>]*>', r'![\1](assets/\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_mod.unescape(text)
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def escape_wikilinks(text):
    """Escape [[ and ]] in card content so Obsidian doesn't create false pages."""
    text = text.replace('[[', '\\[\\[')
    text = text.replace(']]', '\\]\\]')
    return text


def deck_tag(deck_name, overrides=None):
    overrides = overrides or {}
    return overrides.get(deck_name, deck_name.replace(' ', ''))


def parse_vault_topic_cards(output_dir):
    """
    Scan deck pages in the vault and build {topic: [(dtag, callout_block), ...]}
    from the [[wikilinks]] in each card's Topics line.

    This makes Obsidian the source of truth for hub pages — manual edits to
    a card's Topics line are picked up on the next sync.
    """
    topic_cards = {}
    for md_file in sorted(Path(output_dir).glob("*.md")):
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception:
            continue
        if 'managed_by: pk-fire' not in content:
            continue
        fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        fm_body = fm_match.group(1)
        if 'type: topic' in fm_body:
            continue  # skip hub pages
        deck_match = re.search(r'^deck: (.+)$', fm_body, re.MULTILINE)
        if not deck_match:
            continue
        dtag = deck_match.group(1).strip()

        body = content[fm_match.end():]
        # Split into individual callout blocks on the "> [!question]-" opener
        blocks = re.split(r'\n(?=> \[!question\]-)', body)
        for block in blocks:
            block = block.strip()
            if not block.startswith('> [!question]-'):
                continue
            topics_match = re.search(r'> \*\*Topics:\*\* (.+)$', block, re.MULTILINE)
            if not topics_match:
                continue
            tags = re.findall(r'\[\[([^\]]+)\]\]', topics_match.group(1))
            for tag in tags:
                if tag != dtag:
                    topic_cards.setdefault(tag, []).append((dtag, block))
    return topic_cards


def _parse_frontmatter_tags(content):
    """Return the set of tags listed in a file's YAML frontmatter."""
    fm = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm:
        return set()
    return set(re.findall(r'^\s+- (.+)$', fm.group(1), re.MULTILINE))


def strip_html_plain(text):
    """Strip HTML to plain text for topic inference (no markdown conversion)."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def flatten_anki_tags(anki_tags):
    """Flatten hierarchical Anki tags like 'JavaScript::Arrays' into {'JavaScript', 'Arrays'}."""
    flat = set()
    for tag in anki_tags:
        for part in tag.split('::'):
            part = part.strip()
            if part:
                flat.add(part)
    return flat


def infer_topic_tags(text, compiled=None):
    if compiled is None:
        compiled = compile_topics()
    tags = set()
    for tag, patterns in compiled:
        for pat in patterns:
            if pat.search(text):
                tags.add(tag)
                break
    return tags


def extract_anki_cards(anki_db):
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM decks")
    decks = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute("""
        SELECT n.id, n.flds, n.tags, c.did
        FROM notes n JOIN cards c ON n.id = c.nid
        ORDER BY c.did, n.id
    """)
    cards, seen = [], set()
    for note_id, fields, tags, deck_id in cursor.fetchall():
        if note_id in seen:
            continue
        seen.add(note_id)
        cards.append({
            'id': note_id,
            'deck': decks.get(deck_id, "Uncategorized"),
            'fields': fields.split('\x1f'),
            'anki_tags': tags.split() if tags else [],
        })
    conn.close()
    return cards


def format_obsidian_card(card, tag_overrides=None, compiled_topics=None):
    """Format a single card as a collapsible Obsidian callout with wikilinks."""
    fields = card['fields']
    raw_front = fields[0] if len(fields) > 0 else "?"
    raw_back = fields[1] if len(fields) > 1 else ""
    front = ' '.join(escape_wikilinks(strip_html(raw_front)).splitlines()).strip()
    back = escape_wikilinks(strip_html(raw_back))
    all_tags = {deck_tag(card['deck'], tag_overrides)}
    all_tags |= flatten_anki_tags(card.get('anki_tags', []))
    all_tags |= infer_topic_tags(strip_html_plain(raw_front + " " + raw_back), compiled_topics)
    links = '  '.join(f'[[{t}]]' for t in sorted(all_tags))
    lines = [f"> [!question]- {front}"]
    for answer_line in back.splitlines():
        lines.append(f"> {answer_line}")
    lines.append(">")
    lines.append(f"> **Topics:** {links}")
    return '\n'.join(lines)


def load_sync_state(sync_file):
    if os.path.exists(sync_file):
        with open(sync_file, 'r') as f:
            return set(json.load(f).get("exported_ids", []))
    return set()


def save_sync_state(sync_file, exported_ids):
    with open(sync_file, 'w') as f:
        json.dump({"exported_ids": sorted(exported_ids), "last_sync": datetime.now().isoformat()}, f, indent=2)


def sync(anki_db, output_dir, tag_overrides=None, rebuild=False):
    """
    Sync Anki cards to an Obsidian vault.

    Args:
        anki_db: Path to Anki's collection.anki2 file.
        output_dir: Path to the Obsidian vault / output directory.
        tag_overrides: Dict mapping deck names to custom tag names.
        rebuild: If True, delete all generated files and rebuild from scratch.
    """
    tag_overrides = tag_overrides or {}
    compiled_topics = compile_topics(load_topic_rules(anki_db))
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    assets_dir = os.path.join(output_dir, "assets")
    Path(assets_dir).mkdir(exist_ok=True)
    sync_file = os.path.join(output_dir, ".anki_sync_state.json")

    # Preserve user-added frontmatter tags across rebuilds and hub page rewrites
    preserved_tags = {}  # filename stem → set of tags from previous file
    if rebuild:
        # Only delete files pk-fire created (identified by frontmatter markers)
        if os.path.exists(sync_file):
            os.remove(sync_file)
        for f in Path(output_dir).glob("*.md"):
            try:
                content = f.read_text(encoding='utf-8')
                if 'managed_by: pk-fire' in content:
                    preserved_tags[f.stem] = _parse_frontmatter_tags(content)
                    f.unlink()
            except Exception:
                pass

    already_exported = load_sync_state(sync_file)
    is_first_run = len(already_exported) == 0

    print("🔥 PK Fire — Syncing Anki → Obsidian...")
    cards = extract_anki_cards(anki_db)
    if not cards:
        print("No cards found!")
        return

    new_cards = [c for c in cards if c['id'] not in already_exported]
    if not new_cards and not is_first_run:
        print("No new cards — rebuilding topic hubs from vault...")
        vault_topic_cards = parse_vault_topic_cards(output_dir)
        d_tags = {deck_tag(d, tag_overrides) for d in {c['deck'] for c in cards}}
        for topic, card_blocks in sorted(vault_topic_cards.items()):
            if topic in d_tags:
                continue
            hub_path = os.path.join(output_dir, f"{topic}.md")
            pk_hub_tags = {'topic'}
            try:
                existing = _parse_frontmatter_tags(Path(hub_path).read_text(encoding='utf-8')) if os.path.exists(hub_path) else set()
            except Exception:
                existing = set()
            user_tags = existing - pk_hub_tags
            with open(hub_path, 'w', encoding='utf-8') as f:
                f.write(f"---\nmanaged_by: pk-fire\ntype: topic\ncards: {len(card_blocks)}\ntags:\n")
                for t in sorted(pk_hub_tags | user_tags):
                    f.write(f"  - {t}\n")
                f.write(f"---\n\n# {topic}\n\n")
                by_deck = {}
                for dtag_name, block in card_blocks:
                    by_deck.setdefault(dtag_name, []).append(block)
                for dtag_name in sorted(by_deck):
                    f.write(f"## From [[{dtag_name}]]\n\n")
                    for block in by_deck[dtag_name]:
                        f.write(block + '\n\n')
        print("🔥 Topic hubs up to date.")
        return

    new_by_deck, all_by_deck = {}, {}
    for card in new_cards:
        new_by_deck.setdefault(card['deck'], []).append(card)
    for card in cards:
        all_by_deck.setdefault(card['deck'], []).append(card)

    total_new = 0

    for d_name, all_deck_cards in all_by_deck.items():
        dtag = deck_tag(d_name, tag_overrides)
        filepath = os.path.join(output_dir, dtag + ".md")
        deck_topics = set()
        deck_anki_tags = set()
        for card in all_deck_cards:
            combined = card['fields'][0] + ' ' + (card['fields'][1] if len(card['fields']) > 1 else '')
            deck_topics |= infer_topic_tags(strip_html_plain(combined), compiled_topics)
            deck_anki_tags |= flatten_anki_tags(card.get('anki_tags', []))

        deck_new = new_by_deck.get(d_name, [])
        if not deck_new:
            continue

        if not os.path.exists(filepath) or is_first_run:
            pk_tags = deck_topics | deck_anki_tags | {dtag}
            existing = preserved_tags.get(dtag, set())
            user_tags = existing - pk_tags  # tags the user added that pk-fire didn't generate
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"managed_by: pk-fire\ndeck: {dtag}\nsource: Anki\n")
                f.write(f"export_date: {datetime.now().strftime('%Y-%m-%d')}\ntags:\n")
                for t in sorted(pk_tags | user_tags):
                    f.write(f"  - {t}\n")
                f.write("---\n\n")
                f.write(f"# {d_name}\n\n")
                for card in deck_new:
                    f.write(format_obsidian_card(card, tag_overrides, compiled_topics) + '\n\n')
        else:
            with open(filepath, 'a', encoding='utf-8') as f:
                for card in deck_new:
                    f.write(format_obsidian_card(card, tag_overrides, compiled_topics) + '\n\n')

        print(f"  ✓ {dtag + '.md':25s} +{len(deck_new)} new cards")
        total_new += len(deck_new)

    # Rebuild topic hub pages from vault content (Obsidian is source of truth)
    # Any [[wikilink]] a user adds to a card's Topics line is picked up here.
    vault_topic_cards = parse_vault_topic_cards(output_dir)
    d_tags = {deck_tag(d, tag_overrides) for d in all_by_deck}

    for topic, card_blocks in sorted(vault_topic_cards.items()):
        if topic in d_tags:
            continue
        hub_path = os.path.join(output_dir, f"{topic}.md")
        pk_hub_tags = {'topic'}
        try:
            existing = _parse_frontmatter_tags(Path(hub_path).read_text(encoding='utf-8')) if os.path.exists(hub_path) else preserved_tags.get(topic, set())
        except Exception:
            existing = preserved_tags.get(topic, set())
        user_tags = existing - pk_hub_tags
        with open(hub_path, 'w', encoding='utf-8') as f:
            f.write(f"---\nmanaged_by: pk-fire\ntype: topic\ncards: {len(card_blocks)}\ntags:\n")
            for t in sorted(pk_hub_tags | user_tags):
                f.write(f"  - {t}\n")
            f.write(f"---\n\n# {topic}\n\n")
            by_deck = {}
            for dtag_name, block in card_blocks:
                by_deck.setdefault(dtag_name, []).append(block)
            for dtag_name in sorted(by_deck):
                f.write(f"## From [[{dtag_name}]]\n\n")
                for block in by_deck[dtag_name]:
                    f.write(block + '\n\n')

    # Copy new media
    anki_media = os.path.join(os.path.dirname(anki_db), "collection.media")
    media_count = 0
    if os.path.isdir(anki_media):
        for fname in os.listdir(anki_media):
            src = os.path.join(anki_media, fname)
            if os.path.isfile(src):
                dst = os.path.join(assets_dir, fname)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    media_count += 1

    all_ids = already_exported | {c['id'] for c in cards}
    save_sync_state(sync_file, all_ids)

    print(f"\n🔥 Synced {total_new} new cards to {output_dir}")
    print(f"   {len(all_ids)} total cards tracked")
    if media_count:
        print(f"   {media_count} new media files copied")

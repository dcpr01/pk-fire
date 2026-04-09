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

from pk_fire.topics import TOPIC_RULES


def compile_topics(rules=None):
    rules = rules or TOPIC_RULES
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


COMPILED_TOPICS = compile_topics()


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


def infer_topic_tags(text):
    tags = set()
    for tag, patterns in COMPILED_TOPICS:
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


def format_obsidian_card(card, tag_overrides=None):
    """Format a single card as a collapsible Obsidian callout with wikilinks."""
    fields = card['fields']
    raw_front = fields[0] if len(fields) > 0 else "?"
    raw_back = fields[1] if len(fields) > 1 else ""
    front = ' '.join(escape_wikilinks(strip_html(raw_front)).splitlines()).strip()
    back = escape_wikilinks(strip_html(raw_back))
    all_tags = {deck_tag(card['deck'], tag_overrides)}
    all_tags |= infer_topic_tags(raw_front + " " + raw_back)
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


def sync(anki_db, output_dir, tag_overrides=None, full=False):
    """
    Sync Anki cards to an Obsidian vault.

    Args:
        anki_db: Path to Anki's collection.anki2 file.
        output_dir: Path to the Obsidian vault / output directory.
        tag_overrides: Dict mapping deck names to custom tag names.
        full: If True, ignore sync state and do a full re-export.
    """
    tag_overrides = tag_overrides or {}
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    assets_dir = os.path.join(output_dir, "assets")
    Path(assets_dir).mkdir(exist_ok=True)
    sync_file = os.path.join(output_dir, ".anki_sync_state.json")

    if full and os.path.exists(sync_file):
        os.remove(sync_file)

    already_exported = load_sync_state(sync_file)
    is_first_run = len(already_exported) == 0

    print("🔥 PK Fire — Syncing Anki → Obsidian...")
    cards = extract_anki_cards(anki_db)
    if not cards:
        print("No cards found!")
        return

    new_cards = [c for c in cards if c['id'] not in already_exported]
    if not new_cards and not is_first_run:
        print("No new cards to sync. Already up to date.")
        return

    new_by_deck, all_by_deck = {}, {}
    for card in new_cards:
        new_by_deck.setdefault(card['deck'], []).append(card)
    for card in cards:
        all_by_deck.setdefault(card['deck'], []).append(card)

    total_new = 0
    all_topic_names = set()

    for d_name, all_deck_cards in all_by_deck.items():
        dtag = deck_tag(d_name, tag_overrides)
        filepath = os.path.join(output_dir, dtag + ".md")
        deck_topics = set()
        for card in all_deck_cards:
            combined = card['fields'][0] + ' ' + (card['fields'][1] if len(card['fields']) > 1 else '')
            deck_topics |= infer_topic_tags(combined)
        all_topic_names |= deck_topics
        all_topic_names.add(dtag)

        deck_new = new_by_deck.get(d_name, [])
        if not deck_new:
            continue

        if not os.path.exists(filepath) or is_first_run:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"deck: {dtag}\nsource: Anki\n")
                f.write(f"export_date: {datetime.now().strftime('%Y-%m-%d')}\ntags:\n")
                for t in sorted(deck_topics | {dtag}):
                    f.write(f"  - {t}\n")
                f.write("---\n\n")
                f.write(f"# {d_name}\n\n")
                for card in deck_new:
                    f.write(format_obsidian_card(card, tag_overrides) + '\n\n')
        else:
            with open(filepath, 'a', encoding='utf-8') as f:
                for card in deck_new:
                    f.write(format_obsidian_card(card, tag_overrides) + '\n\n')

        print(f"  ✓ {dtag + '.md':25s} +{len(deck_new)} new cards")
        total_new += len(deck_new)

    # Rebuild topic hub pages
    topic_cards = {}
    for card in cards:
        combined = card['fields'][0] + ' ' + (card['fields'][1] if len(card['fields']) > 1 else '')
        for t in infer_topic_tags(combined):
            topic_cards.setdefault(t, []).append(card)

    d_tags = {deck_tag(d, tag_overrides) for d in all_by_deck}
    for topic in sorted(all_topic_names):
        if topic in d_tags:
            continue
        matching = topic_cards.get(topic, [])
        with open(os.path.join(output_dir, f"{topic}.md"), 'w', encoding='utf-8') as f:
            f.write(f"---\ntype: topic\ncards: {len(matching)}\ntags:\n  - topic\n---\n\n# {topic}\n\n")
            by_deck = {}
            for card in matching:
                by_deck.setdefault(card['deck'], []).append(card)
            for dn, dc in sorted(by_deck.items()):
                f.write(f"## From [[{deck_tag(dn, tag_overrides)}]]\n\n")
                for card in dc:
                    f.write(format_obsidian_card(card, tag_overrides) + '\n\n')

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

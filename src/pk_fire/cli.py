"""CLI entry point for pk-fire.

Usage:
    pk sync                  Incremental sync
    pk sync --rebuild        Rebuild vault from scratch
    pk auto-sync --install   Install Anki add-on for auto-sync on close
"""

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from pk_fire import __version__
from pk_fire.sync import sync

CONFIG_FILE = Path.home() / ".pk-fire.json"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def find_anki_db():
    """Auto-detect the Anki collection database."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        base = home / "Library" / "Application Support" / "Anki2"
    elif system == "Linux":
        base = home / ".local" / "share" / "Anki2"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Anki2"
    else:
        return None

    if not base.exists():
        return None

    # Find user profiles (skip addons21, prefs, etc.)
    for entry in sorted(base.iterdir()):
        db = entry / "collection.anki2"
        if db.exists():
            return str(db)

    return None


def find_anki_addons_dir():
    """Find the Anki addons21 directory."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        return home / "Library" / "Application Support" / "Anki2" / "addons21"
    elif system == "Linux":
        return home / ".local" / "share" / "Anki2" / "addons21"
    elif system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Anki2" / "addons21"
    return None


def install_anki_addon(vault_dir, anki_db):
    """Install a small Anki add-on that triggers pk-sync on profile close."""
    addons_dir = find_anki_addons_dir()
    if not addons_dir:
        print("❌ Could not locate Anki addons directory.")
        sys.exit(1)

    addon_dir = addons_dir / "pk_fire_sync"
    addon_dir.mkdir(parents=True, exist_ok=True)

    # Write the add-on
    init_py = addon_dir / "__init__.py"
    addon_code = (
        "# PK Fire - Auto-sync Anki to Obsidian on profile close.\n"
        "import subprocess, sys\n"
        "from aqt import gui_hooks\n"
        "\n"
        f"VAULT_DIR = {vault_dir!r}\n"
        f"ANKI_DB = {anki_db!r}\n"
        "\n"
        "def on_profile_will_close():\n"
        "    try:\n"
        '        subprocess.Popen([sys.executable, "-m", "pk_fire", "sync",\n'
        '            "--anki-db", ANKI_DB, "--vault", VAULT_DIR],\n'
        "            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "gui_hooks.profile_will_close.append(on_profile_will_close)\n"
    )
    init_py.write_text(addon_code)

    # Write manifest
    manifest = addon_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "package": "pk_fire_sync",
        "name": "PK Fire — Auto-sync to Obsidian",
        "mod": 0,
    }, indent=2))

    print(f"✅ Anki add-on installed to {addon_dir}")
    print(f"   Vault: {vault_dir}")
    print(f"   DB:    {anki_db}")
    print(f"\n   Restart Anki to activate. Cards will sync when you close Anki.")


def resolve_config(args):
    """Resolve vault and anki_db from args, falling back to saved config."""
    config = load_config()

    anki_db = getattr(args, 'anki_db', None) or config.get('anki_db') or find_anki_db()
    vault = getattr(args, 'vault', None) or config.get('vault')

    if not anki_db or not os.path.exists(anki_db):
        print("\u274c Could not find Anki database. Run: pk sync --anki-db /path/to/collection.anki2")
        sys.exit(1)

    if not vault:
        print("\u274c No vault configured. Run: pk sync --vault ~/my-vault")
        sys.exit(1)

    vault = os.path.expanduser(vault)

    # Persist for future runs
    config['vault'] = vault
    config['anki_db'] = anki_db
    if getattr(args, 'tag_override', None):
        overrides = {}
        for pair in args.tag_override:
            if '=' in pair:
                k, v = pair.split('=', 1)
                overrides[k] = v
        config['tag_overrides'] = overrides
    save_config(config)

    return anki_db, vault, config.get('tag_overrides', {})


def main():
    parser = argparse.ArgumentParser(
        prog="pk",
        description="\U0001f525 PK Fire \u2014 Sync Anki flashcards to Obsidian with smart topic tagging.",
    )
    parser.add_argument("--version", action="version", version=f"pk-fire {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # -- sync --
    sync_parser = subparsers.add_parser("sync", help="Sync Anki cards to Obsidian vault")
    sync_parser.add_argument("--anki-db", help="Path to collection.anki2 (saved after first use)")
    sync_parser.add_argument("--vault", help="Path to Obsidian vault (saved after first use)")
    sync_parser.add_argument("--rebuild", action="store_true", help="Rebuild vault from scratch (deletes and re-exports everything)")
    sync_parser.add_argument(
        "--tag-override",
        action="append",
        metavar="DECK=TAG",
        help="Override a deck name tag, e.g. 'Web Dev=WebDev'",
    )

    # -- auto-sync --
    auto_parser = subparsers.add_parser("auto-sync", help="Manage auto-sync on Anki close")
    auto_parser.add_argument("--install", action="store_true", required=True, help="Install the Anki add-on")
    auto_parser.add_argument("--anki-db", help="Path to collection.anki2 (saved after first use)")
    auto_parser.add_argument("--vault", help="Path to Obsidian vault (saved after first use)")

    # -- topics --
    topics_parser = subparsers.add_parser("topics", help="View or manage user topic tags")
    topics_parser.add_argument("--add", metavar="TOPIC", help="Add a user topic")
    topics_parser.add_argument("--delete", metavar="TOPIC", help="Remove a user topic")
    topics_parser.add_argument("--update", metavar="TOPIC", help="Update case sensitivity of an existing user topic")
    cs_group = topics_parser.add_mutually_exclusive_group()
    cs_group.add_argument("--case-sensitive", action="store_true", default=None, help="Match topic case-sensitively (use with --add or --update)")
    cs_group.add_argument("--case-insensitive", action="store_true", default=None, help="Match topic case-insensitively (use with --update to revert)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "topics":
        _cmd_topics(args)
        sys.exit(0)

    anki_db, vault, tag_overrides = resolve_config(args)

    if args.command == "sync":
        sync(anki_db, vault, tag_overrides=tag_overrides, rebuild=args.rebuild)
    elif args.command == "auto-sync":
        install_anki_addon(vault, anki_db)


def _read_topic_rules():
    """Return the list of topic rules from config."""
    config = load_config()
    return config.get('topic_rules', [])


def _write_topic_rules(rules):
    """Write topic rules to config."""
    config = load_config()
    config['topic_rules'] = rules
    save_config(config)


def _topic_base(name):
    """Strip __casesensitive suffix to get the plain topic name."""
    return name.removesuffix('__casesensitive')


def _cmd_topics(args):
    import re
    rules = _read_topic_rules()
    topic_names = [r[0] for r in rules]
    topic_bases = [_topic_base(t) for t in topic_names]

    if args.add:
        base = _topic_base(args.add)
        if base in topic_bases:
            print(f"Topic '{base}' already exists. Use --update to change its settings.")
            return
        name = base + '__casesensitive' if args.case_sensitive else base
        pattern = r"\b" + re.escape(base) + r"\b"
        rules.append([name, [pattern]])
        _write_topic_rules(rules)
        cs = " (case-sensitive)" if args.case_sensitive else ""
        print(f"Added topic: {base}{cs}")
        return

    if args.update:
        base = _topic_base(args.update)
        if base not in topic_bases:
            print(f"Topic '{base}' not found in topics.")
            return
        if not args.case_sensitive and not args.case_insensitive:
            print("Specify --case-sensitive or --case-insensitive.")
            return
        new_name = base + '__casesensitive' if args.case_sensitive else base
        for r in rules:
            if _topic_base(r[0]) == base:
                r[0] = new_name
        _write_topic_rules(rules)
        cs = " → case-sensitive" if args.case_sensitive else " → case-insensitive"
        print(f"Updated topic: {base}{cs}")
        return

    if args.delete:
        base = _topic_base(args.delete)
        if base not in topic_bases:
            print(f"Topic '{base}' not found in topics.")
            return
        rules = [r for r in rules if _topic_base(r[0]) != base]
        _write_topic_rules(rules)
        print(f"Removed topic: {base}")
        return

    # List topics — deduplicate (e.g. Databases has a __casesensitive variant)
    if not rules:
        print("No topics configured. Run `pk sync` to generate from your Anki decks,")
        print("or use `pk topics --add TOPIC` to add manually.")
        return

    seen = set()
    print("Topics:")
    for raw_tag, _ in rules:
        t = raw_tag.removesuffix('__casesensitive')
        if t not in seen:
            seen.add(t)
            cs = raw_tag.endswith('__casesensitive')
            print(f"  {t}{' (case-sensitive)' if cs else ''}")


if __name__ == "__main__":
    main()

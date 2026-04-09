"""CLI entry point for pk-fire.

Usage:
    pk sync --vault ~/my-vault          Incremental sync
    pk sync --vault ~/my-vault --full   Full re-export
    pk install --vault ~/my-vault       Install Anki add-on for auto-sync
"""

import argparse
import json
import os
import platform
import sys
import textwrap
from pathlib import Path

from pk_fire import __version__
from pk_fire.sync import sync


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


def main():
    parser = argparse.ArgumentParser(
        prog="pk",
        description="🔥 PK Fire — Sync Anki flashcards to Obsidian with smart topic tagging.",
    )
    parser.add_argument("--version", action="version", version=f"pk-fire {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # -- sync --
    sync_parser = subparsers.add_parser("sync", help="Sync Anki cards to Obsidian vault")
    sync_parser.add_argument("--anki-db", help="Path to Anki's collection.anki2 (auto-detected if omitted)")
    sync_parser.add_argument("--vault", required=True, help="Path to the Obsidian vault output directory")
    sync_parser.add_argument("--full", action="store_true", help="Full re-export (ignore sync state)")
    sync_parser.add_argument(
        "--tag-override",
        action="append",
        metavar="DECK=TAG",
        help="Override a deck name tag, e.g. 'Web Dev=WebDev'",
    )

    # -- install --
    install_parser = subparsers.add_parser("install", help="Install Anki add-on for auto-sync on close")
    install_parser.add_argument("--anki-db", help="Path to Anki's collection.anki2 (auto-detected if omitted)")
    install_parser.add_argument("--vault", required=True, help="Path to the Obsidian vault output directory")

    args = parser.parse_args()

    # Default to sync if no subcommand
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Resolve Anki DB
    anki_db = getattr(args, 'anki_db', None) or find_anki_db()
    if not anki_db or not os.path.exists(anki_db):
        print("❌ Could not find Anki database. Specify with --anki-db")
        sys.exit(1)

    vault = os.path.expanduser(args.vault)

    if args.command == "install":
        install_anki_addon(vault, anki_db)
    elif args.command == "sync":
        tag_overrides = {}
        if args.tag_override:
            for pair in args.tag_override:
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    tag_overrides[k] = v
        sync(anki_db, vault, tag_overrides=tag_overrides, full=args.full)


if __name__ == "__main__":
    main()

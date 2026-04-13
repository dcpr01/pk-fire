# 🔥 PK Fire

**Use Anki as a flashcard frontend. Let Obsidian be the brain.**

PK Fire bridges Anki and Obsidian so you can keep using Anki's fast, purpose-built card editor while your knowledge lives in a grep-able, graph-connected, feature-rich PKM vault.

## Why

Anki is great at one thing: quick Q&A input with image support and rich formatting. But your cards are locked in a SQLite database — invisible to search, unlinked to your notes, impossible to browse outside the app.

PK Fire turns Anki into a **frontend** for your personal knowledge management system:

- **Add cards in Anki** like you always have
- **Run `pk sync`** and your cards appear in Obsidian as collapsible Q&A callouts with images
- **Smart topic tagging** auto-detects what each card is about and creates `[[wikilinks]]` so topics connect in Obsidian's graph view
- **Anki tags carried over** — tags you've already added to cards in Anki are flattened (e.g. `JavaScript::Arrays` → `JavaScript` + `Arrays`) and merged into the card's topics automatically
- **Topic hub pages** aggregate all cards for a given topic across decks, including Anki-native tags
- **Incremental sync** — only new cards are added, your Obsidian edits are preserved
- **Auto-sync on Anki close** via the bundled Anki add-on
- **`pk topics`** — add or remove topic keywords without touching any Python files

Your flashcards become first-class citizens in your PKM. Searchable, linkable, browsable.

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/dcpr01/pk-fire.git
cd pk-fire
uv tool install -e .
```

This installs the `pk` command globally. Verify with:

```bash
pk --version
```

### Platform Notes

- **macOS**: Anki data is at `~/Library/Application Support/Anki2/`
- **Linux**: Anki data is at `~/.local/share/Anki2/`
- **Windows**: Anki data is at `%APPDATA%/Anki2/`

All paths are auto-detected. If you installed Anki via Flatpak on Linux, the data path may differ — use `--anki-db` to specify it manually.

## Quick Start

```bash
# First run — point to an existing Obsidian vault or a new folder
# (the folder will be created if it doesn't exist)
pk sync --vault ~/my-obsidian-vault

# Safer option — keep pk-fire content in a dedicated subfolder inside your vault
pk sync --vault ~/my-obsidian-vault --subdir PK_Fire

# Then open that folder as a vault in Obsidian:
#   Obsidian → Open folder as vault → select ~/my-obsidian-vault

# Every run after that — just:
pk sync

# Rebuild vault from scratch (moved cards, deleted cards, etc.)
pk sync --rebuild

# Override a deck tag name
pk sync --tag-override "Web Dev=WebDev"
```

Anki's database, vault path, and optional managed subfolder are auto-detected and saved after first use. Override anytime with `--anki-db`, `--vault`, or `--subdir`.

## Auto-Sync on Anki Close

```bash
pk auto-sync --install
```

Restart Anki. From then on, closing Anki triggers a background sync.

## Output Structure

Without `--subdir`, pk-fire writes directly into the vault root:

```
my-vault/
├── Biology.md           # Deck page — all cards from this deck
├── Spanish.md           # Deck page
├── Genetics.md          # Topic hub — cards tagged Genetics, across decks
├── Grammar.md           # Topic hub
├── assets/              # Images from Anki cards
└── .anki_sync_state.json
```

With `--subdir PK_Fire`, generated content stays isolated:

```
my-vault/
├── PK_Fire/
│   ├── Biology.md
│   ├── Spanish.md
│   ├── Genetics.md
│   ├── Grammar.md
│   ├── assets/
│   └── .anki_sync_state.json
└── Cursor_Resources/
```

### Card Format

Each card is a collapsible callout:

```markdown
> [!question]- What is mitosis?
> The process of cell division that results in two daughter cells,
> each with the same number of chromosomes as the parent cell.
>
> **Topics:** [[Biology]]  [[Genetics]]
```

## Topic Rules

Topic detection uses regex patterns in `src/pk_fire/topics.py`. The shipped rules are an example for web development / programming. **Customize these for your own domains.**

Each rule is a `(tag_name, [patterns])` tuple:

```python
TOPIC_RULES = [
    ("Genetics", [
        r"\bgene\b", r"\bDNA\b", r"\bchromosome\b",
        r"\bmutation\b", r"\ballele\b",
    ]),
    ("Grammar", [
        r"\bverb\b", r"\bnoun\b", r"\btense\b",
        r"\bconjugat", r"\bsubjunctive\b",
    ]),
]
```

Tags ending with `__casesensitive` are matched without ignoring case — useful for acronyms or keywords that collide with common English words.

Without any topic rules, cards are still tagged by their Anki deck name.

### Managing Topics with `pk topics`

Rather than editing `topics.py` manually, use the `pk topics` command to safely add and remove keyword topics:

```bash
# See all built-in topics and your user-added topics
pk topics

# Add a topic — any card mentioning "React" will be tagged [[React]]
pk topics --add React

# Remove a user topic
pk topics --delete React
```

User topics are written directly into the `USER_TOPIC_RULES` section at the bottom of `topics.py`. They work identically to built-in rules: matched case-insensitively by keyword, hub pages are created, and cards are linked with `[[wikilinks]]`. The only difference is they're safe to add and remove without risking a typo in the regex syntax.

### Anki Tags

Tags already on your Anki cards are automatically brought across during sync — no setup needed. Hierarchical tags are flattened: `JavaScript::Arrays` becomes both a `[[JavaScript]]` tag and an `[[Arrays]]` tag. Each unique tag gets its own hub page in Obsidian if one doesn't already exist.

Anki tags are **supplemental** — they stack on top of whatever topics pk-fire infers from the card content.

## Important Notes

- **Close Anki before syncing.** Anki holds a lock on its SQLite database while running. Changes you make (new cards, moving cards between decks) aren't guaranteed to be flushed to disk until Anki closes. Always quit Anki before running `pk sync`.
- **Moved or deleted cards?** Use `pk sync --rebuild`. A regular `pk sync` only appends new cards — it won't detect cards that moved between decks or were deleted. `--rebuild` wipes pk-fire-managed `.md` files in the configured output directory and re-exports everything from Anki's current state.
- **Don't edit deck or topic pages directly.** These are managed by pk-fire and will be overwritten on `--rebuild`. Instead, create your own note files and link to topics with `[[wikilinks]]`. For example, create `My ORM Notes.md` containing `[[ORM]]` and `[[SQLAlchemy]]` — it'll connect in the graph and pk-fire will never touch it.
- **The auto-sync add-on runs after Anki closes.** If you use `pk auto-sync --install`, the sync happens in the background right after Anki shuts down, so your vault is always up to date without manual intervention.

## How Sync Works

1. **First run**: Creates deck pages with YAML frontmatter, topic hub pages, and copies media
2. **Subsequent runs** (`pk sync`): Appends only new cards to deck pages. Rebuilds topic hubs. Copies new media.
3. **Rebuild** (`pk sync --rebuild`): Deletes all generated `.md` files in the configured output directory and re-exports everything from scratch. Use this after moving cards between decks, deleting cards, or renaming decks in Anki.

## Troubleshooting

**Cards not showing up after sync?**
- Make sure Anki is closed. Anki locks the database while running.
- Reload the vault in Obsidian: `Ctrl+P` / `Cmd+P` → "Reload app without saving"

**Cards in the wrong deck after moving them in Anki?**
- Run `pk sync --rebuild` to re-export from scratch.

**Orphan pages or broken links in Obsidian's graph?**
- Run `pk sync --rebuild` to clean up stale files.
- Delete any manually created `.canvas` files in the vault.

**"Could not find Anki database" error?**
- Anki may not be installed, or you're using a non-standard profile location.
- Specify the path manually: `pk sync --anki-db /path/to/collection.anki2`

## Dependencies

Zero. Python standard library only.

## License

MIT

# 🔥 PK Fire

**Use Anki as a flashcard frontend. Let Obsidian be the brain.**

PK Fire bridges Anki and Obsidian so you can keep using Anki's fast, purpose-built card editor while your knowledge lives in a grep-able, graph-connected, feature-rich PKM vault.

## Why

Anki is great at one thing: quick Q&A input with image support and rich formatting. But your cards are locked in a SQLite database — invisible to search, unlinked to your notes, impossible to browse outside the app.

PK Fire turns Anki into a **frontend** for your personal knowledge management system:

- **Add cards in Anki** like you always have
- **Run `pk sync`** and your cards appear in Obsidian as collapsible Q&A callouts with images
- **Smart topic tagging** auto-detects what each card is about and creates `[[wikilinks]]` so topics connect in Obsidian's graph view
- **Topic hub pages** aggregate all cards for a given topic across decks
- **Incremental sync** — only new cards are added, your Obsidian edits are preserved
- **Auto-sync on Anki close** via the bundled Anki add-on

Your flashcards become first-class citizens in your PKM. Searchable, linkable, browsable.

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/dcpr01/pk-fire.git
cd pk-fire
uv pip install -e .
```

## Quick Start

```bash
# First run — provide your vault path once (saved to ~/.pk-fire.json)
pk sync --vault ~/my-obsidian-vault

# Every run after that — just:
pk sync

# Rebuild vault from scratch (moved cards, deleted cards, etc.)
pk sync --rebuild

# Override a deck tag name
pk sync --tag-override "Web Dev=WebDev"
```

Anki's database and vault path are auto-detected and saved after first use. Override anytime with `--anki-db` or `--vault`.

## Auto-Sync on Anki Close

```bash
pk auto-sync --install
```

Restart Anki. From then on, closing Anki triggers a background sync.

## Output Structure

```
my-vault/
├── Biology.md           # Deck page — all cards from this deck
├── Spanish.md           # Deck page
├── Genetics.md          # Topic hub — cards tagged Genetics, across decks
├── Grammar.md           # Topic hub
├── assets/              # Images from Anki cards
└── .anki_sync_state.json
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

## Important Notes

- **Close Anki before syncing.** Anki holds a lock on its SQLite database while running. Changes you make (new cards, moving cards between decks) aren't guaranteed to be flushed to disk until Anki closes. Always quit Anki before running `pk sync`.
- **Moved or deleted cards?** Use `pk sync --rebuild`. A regular `pk sync` only appends new cards — it won't detect cards that moved between decks or were deleted. `--rebuild` wipes the vault's `.md` files and re-exports everything from Anki's current state.
- **Deck pages are append-only.** You can safely add your own notes below the synced cards in deck pages. A regular `pk sync` will never overwrite them. However, `pk sync --rebuild` will — so back up any manual edits before rebuilding.
- **Topic hub pages are rebuilt every sync.** Don't manually edit topic hub pages (CSS, OOP, Databases, etc.) — they're regenerated from scratch each time to stay accurate.
- **The auto-sync add-on runs after Anki closes.** If you use `pk auto-sync --install`, the sync happens in the background right after Anki shuts down, so your vault is always up to date without manual intervention.

## How Sync Works

1. **First run**: Creates deck pages with YAML frontmatter, topic hub pages, and copies media
2. **Subsequent runs** (`pk sync`): Appends only new cards to deck pages. Rebuilds topic hubs. Copies new media.
3. **Rebuild** (`pk sync --rebuild`): Deletes all generated `.md` files and re-exports everything from scratch. Use this after moving cards between decks, deleting cards, or renaming decks in Anki.

## Troubleshooting

**Cards not showing up after sync?**
- Make sure Anki is closed. Anki locks the database while running.
- Reload the vault in Obsidian: `Cmd+P` → "Reload app without saving"

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

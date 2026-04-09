# 🔥 PK Fire

**Use Anki as a flashcard frontend. Let Obsidian be the brain.**

PK Fire bridges Anki and Obsidian so you can keep using Anki's fast, purpose-built card editor while your knowledge lives in a grep-able, graph-connected, feature-rich PKM vault.

## Why

Anki is great at one thing: quick Q&A input with image support and rich formatting. But your cards are locked in a SQLite database — invisible to search, unlinked to your notes, impossible to browse outside the app.

PK Fire turns Anki into a **frontend** for your personal knowledge management system:

- **Add cards in Anki** like you always have
- **Run `pk-sync`** and your cards appear in Obsidian as collapsible Q&A callouts with images
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
# First sync — exports all cards
pk sync --vault ~/my-obsidian-vault

# Incremental sync — only new cards
pk sync --vault ~/my-obsidian-vault

# Full re-export from scratch
pk sync --vault ~/my-obsidian-vault --full

# Rename a deck tag (e.g. spaces in deck names)
pk sync --vault ~/my-obsidian-vault --tag-override "Web Dev=WebDev"
```

Anki's database is auto-detected on macOS, Linux, and Windows. Override with `--anki-db` if needed.

## Auto-Sync on Anki Close

```bash
pk install --vault ~/my-obsidian-vault
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

## How Sync Works

1. **First run**: Creates deck pages with YAML frontmatter, topic hub pages, and copies media
2. **Subsequent runs**: Appends only new cards to deck pages. Rebuilds topic hubs. Copies new media.
3. **Deck pages** are append-only — safe to add your own notes below the synced cards
4. **Topic hub pages** are rebuilt each sync — don't edit these manually

## Dependencies

Zero. Python standard library only.

## License

MIT

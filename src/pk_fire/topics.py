"""
Topic inference rules for smart-tagging Anki cards.

Generated on first run by scanning your Anki decks and tags.
Rules are stored in ~/.pk-fire.json and can be managed with `pk topics`.

Each rule is a tuple of (tag_name, [regex_patterns]).
A card is tagged with a topic if ANY pattern matches its content.

Tags ending with '__casesensitive' are matched case-sensitively;
the suffix is stripped from the final tag name.
"""

TOPIC_RULES = []

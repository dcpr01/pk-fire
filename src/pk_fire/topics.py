"""
Topic inference rules for smart-tagging Anki cards.

Each rule is a tuple of (tag_name, [regex_patterns]).
A card is tagged with a topic if ANY pattern matches its content.

Tags ending with '__casesensitive' are matched case-sensitively;
the suffix is stripped from the final tag name.

Customize these rules to match your own knowledge domains.
"""

TOPIC_RULES = [
    ("HTML", [
        r"\bhtml\b", r"\bhtml5\b", r"\bmarkup\b",
        r"\banchor tag\b", r"\bhref\b", r"\binline.?block\b",
        r"\bordered list\b", r"\bunordered list\b",
        r"&lt;(?:ul|ol|li|a|div|section|head|style|form|input|p|h[1-6]|span|table|img|br)\b",
        r"\bDOM\b", r"\bsemantic\b", r"\bblock.level element\b",
        r"\binline element\b", r"\bhtml attribute\b",
    ]),
    ("CSS", [
        r"\bcss\b", r"\bstylesheet\b", r"\bselector\b",
        r"\bfont[- ](?:style|size|weight|family)\b", r"\bbackground[- ](?:color|image)\b",
        r"\btext[- ](?:shadow|decoration|transform|align)\b",
        r"\bbox[- ]model\b", r"\bmargin\b", r"\bpadding\b",
        r"\bflexbox\b", r"\bgrid\b", r"\bz-index\b",
        r"\blist[- ]style\b", r"\bshorthand\b",
        r"\bpseudo[- ]class\b", r"\bmedia quer", r"\bresponsive\b",
        r"\bcss property\b", r"\bstylesheet\b", r"\bstyling\b",
    ]),
    ("OOP", [
        r"\bobject.oriented\b", r"\bOOP\b",
        r"\binheritance\b", r"\bpolymorphism\b",
        r"\bencapsulation\b", r"\babstraction\b",
        r"\bsubclass\b", r"\bparent class\b", r"\bchild class\b",
        r"\b__init__\b", r"\bsuper\(\)",
        r"\bclass \w+\b",
    ]),
    ("Functions", [
        r"\bdef \w+\(", r"\blambda\b", r"\bcallable\b",
        r"\bhigher.order function\b", r"\bfirst.class\b", r"\bclosure\b",
        r"\bdecorator\b", r"\b\*args\b", r"\b\*\*kwargs\b",
        r"\brecursion\b", r"\brecursive\b",
    ]),
    ("DataStructures", [
        r"\bdictionary\b", r"\bdict\b", r"\btuple\b",
        r"\bstack\b", r"\bqueue\b", r"\bhash.?map\b",
        r"\b\.append\(\b", r"\b\.pop\(\b", r"\b\.keys\(\b", r"\b\.values\(\b",
        r"\bslicing\b", r"\biterable\b", r"\bdata structure\b",
        r"\blinked list\b",
    ]),
    ("ControlFlow", [
        r"\bloop\b", r"\bfor loop\b", r"\bwhile loop\b",
        r"\bcontinue statement\b", r"\bbreak statement\b",
        r"\btry.except\b", r"\bexception\b", r"\braise\b",
        r"\bconditional\b", r"\bif.else\b", r"\belif\b",
        r"\biteration\b", r"\biterator\b",
    ]),
    ("HTTP", [
        r"\bHTTP\b", r"\bREST API\b", r"\bstatus code\b",
        r"\b[2345]xx\b", r"\bendpoint\b",
        r"\bGET request\b", r"\bPOST request\b",
        r"\bHTTP request\b", r"\bHTTP response\b",
    ]),
    ("Databases", [
        r"\bdatabase\b", r"\bDBMS\b", r"\brelational\b",
        r"\bprimary key\b", r"\bforeign key\b",
        r"\bschema\b", r"\bnormali[sz]",
        r"\bGROUP BY\b",
    ]),
    ("Databases__casesensitive", [
        r"\bSELECT\b", r"\bINSERT\b", r"\bDELETE FROM\b",
        r"\bJOIN\b", r"\bWHERE\b", r"\bSQL\b",
    ]),
    ("WebScraping", [
        r"\bBeautifulSoup\b", r"\bscraping\b", r"\bscreen.scraping\b",
        r"\bscraper\b", r"\bcrawl\b", r"\bhtml\.parser\b",
        r"\blxml\b", r"\bfind_all\(",
    ]),
    ("Modules", [
        r"\bmodule\b", r"\bpackage\b", r"\bsubpackage\b",
        r"\b__init__\.py\b", r"\bpip install\b",
    ]),
    ("ORM", [
        r"\bORM\b", r"\bsqlalchemy\b", r"\bsession\b",
        r"\bflush\(\)", r"\bcommit\(\)",
        r"\bmigrat", r"\balembic\b",
        r"\bdeclarative.base\b", r"\brelationship\(\b",
    ]),
]

# User topics — managed by `pk topics --add / --delete`. Do not edit manually.
USER_TOPIC_RULES = [
]

"""Real inputs for each use-case page.

Every state here is a plausible, self-contained example a reader could paste in
themselves. Nothing is cherry-picked to make Jev look good — a few are
deliberately ambiguous so the confidence value has something to say.

Question definitions are copied verbatim from what the site publishes, so the
measured output on each page is genuinely the output of the code shown above it.
"""

from __future__ import annotations

# Plain dicts rather than SDK objects: the wire format is verified and works
# against both the first-party API and OpenRouter's /api/alpha/decisions, so
# there is no reason to take a dependency just to build three small shapes.


def Choice(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def Score(instructions: str, criteria: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": criteria}


def _noul(instructions: str, yes: str, no: str) -> dict:
    return {"type": "noul", "instructions": instructions,
            "criteria": {"true": yes, "false": no}}


# slug -> {state, questions, note}
CASES: dict[str, dict] = {
    "support-ticket-triage": {
        "state": (
            "Subject: Charged twice for September\n\n"
            "Hi — I was billed $49 on the 3rd and again on the 4th. I only have one "
            "subscription. I've been a customer for two years and this is the second "
            "time. If it isn't refunded by Friday I'm cancelling and moving to a "
            "competitor. Order refs 88412 and 88437."
        ),
        "questions": {
            "queue": Choice(
                instructions="Which team should handle this ticket?",
                criteria={
                    "billing": "Payments, invoicing, refunds",
                    "technical": "Bugs, outages, integrations",
                    "account": "Login, permissions, plan changes",
                    "sales": "Pricing, upgrades, new accounts",
                    "spam": "Unsolicited or irrelevant",
                },
            ),
            "severity": Score(
                instructions="How urgent is this ticket?",
                criteria=["Low", "Normal", "High", "Urgent"],
            ),
            "churn_risk": _noul(
                "Is the customer threatening to cancel?",
                "Explicitly mentions cancelling or leaving",
                "No cancellation intent expressed",
            ),
        },
        "note": "A clear-cut billing ticket that also carries an explicit churn threat.",
    },
    "llm-model-routing": {
        "state": "what's the capital of australia",
        "questions": {
            "tier": Choice(
                instructions="How much capability does answering this require?",
                criteria={
                    "trivial": "Lookup, greeting, or one-line factual answer",
                    "standard": "Ordinary request, no multi-step reasoning",
                    "complex": "Multi-step or domain-specific work",
                    "needs_reasoning": "Requires planning, math, or careful analysis",
                },
            ),
        },
        "note": "The easy majority a cascade is supposed to catch before it reaches a frontier model.",
    },
    "agent-tool-selection": {
        "state": (
            "User: my flight to Berlin got cancelled, can you find me something "
            "tomorrow morning and let my hotel know I'll be late?"
        ),
        "questions": {
            "tool": Choice(
                instructions="Which tool should run next?",
                criteria={
                    "search_flights": "Find available flights between airports on a date",
                    "book_flight": "Purchase a specific flight already chosen",
                    "send_email": "Send an email to a named recipient",
                    "get_calendar": "Read the user's calendar",
                    "web_search": "General web lookup with no dedicated tool",
                },
            ),
        },
        "note": "Deliberately a two-step request — the interesting part is which step it picks first, and how sure it is.",
    },
    "content-moderation": {
        "state": (
            "honestly whoever designed this checkout flow should be fired, it's the "
            "worst garbage I've used all year and I've used a lot of garbage"
        ),
        "questions": {
            "severity": Score(
                instructions="How harmful is this content?",
                criteria=["Benign", "Questionable", "Harmful", "Severe"],
            ),
            "targets_person": _noul(
                "Does this target a specific real person?",
                "Names or clearly identifies an individual",
                "No specific individual targeted",
            ),
            "is_spam": _noul(
                "Is this commercial spam?",
                "Unsolicited promotion or link farming",
                "Genuine participation",
            ),
        },
        "note": "Rude but not abusive — the band where a binary classifier is useless and a distribution is not.",
    },
    "phishing-detection": {
        "state": (
            "From: IT Helpdesk <it-support@micros0ft-verify.com>\n"
            "Subject: Action required: your mailbox will be deactivated in 24 hours\n\n"
            "Our records show your password expires today. Click below within 24 "
            "hours to keep your account active.\n"
            "Verify now: http://mailbox-renew.verify-login.co/auth?id=8842"
        ),
        "questions": {
            "urgency": _noul(
                "Does this create artificial time pressure?",
                "Deadlines or threats of loss",
                "No time pressure",
            ),
            "credentials": _noul(
                "Does this ask for credentials?",
                "Requests login, password or MFA code",
                "No credential request",
            ),
            "sender_odd": _noul(
                "Is the sender identity inconsistent?",
                "Display name conflicts with address",
                "Sender looks coherent",
            ),
            "link_mismatch": _noul(
                "Does link text disagree with its destination?",
                "Anchor text and href point elsewhere",
                "Links are consistent",
            ),
            "unusual_ask": _noul(
                "Is an unusual financial action requested?",
                "Wire transfer, gift cards, payment change",
                "No financial request",
            ),
        },
        "note": "Five signals in one call — the pattern the phishing benchmark found beats a single verdict question.",
    },
    "rag-reranking": {
        "state": (
            "QUESTION: How do I rotate an API key without downtime?\n\n"
            "PASSAGE: API keys are created in the dashboard under Settings > API. "
            "Each key has a name and a creation date. You can have up to ten active "
            "keys per project."
        ),
        "questions": {
            "relevance": Score(
                instructions="How useful is this passage for answering the question?",
                criteria=["Irrelevant", "Tangential", "Useful", "Directly answers"],
            ),
        },
        "note": "The classic vector-search false positive: same topic, does not answer the question.",
    },
    "agent-output-guardrails": {
        "state": (
            "Thanks for reaching out! I've gone ahead and issued a full refund to "
            "Sarah Chen (sarah.chen@example.com) — you'll see it back on your card "
            "within 2 business days, guaranteed."
        ),
        "questions": {
            "answers": _noul(
                "Does this answer the user's question?",
                "Directly addresses the ask",
                "Evasive or off-topic",
            ),
            "no_pii": _noul(
                "Is this free of personal data?",
                "No names, emails, addresses or IDs",
                "Contains personal data",
            ),
            "on_brand": _noul(
                "Is the tone professional?",
                "Courteous and appropriate",
                "Rude, flippant or off-brand",
            ),
            "no_promise": _noul(
                "Is this free of commitments we cannot keep?",
                "Makes no guarantee about dates or outcomes",
                "Promises a refund, date or result",
            ),
        },
        "note": "A draft that should fail two checks at once: it leaks PII and guarantees a date.",
    },
    "lead-scoring": {
        "state": (
            "Name: Priya Raman\nEmail: p.raman@nimbusfreight.com\n"
            "Message: We move about 4,000 shipments a month and our current routing "
            "vendor's contract ends in November. Who can I talk to about volume "
            "pricing and an SSO setup?\n\n"
            "COMPANY: Nimbus Freight, logistics, ~800 employees"
        ),
        "questions": {
            "fit": Score(
                instructions="How well does this lead match our ideal customer?",
                criteria=["Poor", "Marginal", "Good", "Ideal"],
            ),
            "intent": Score(
                instructions="How far along is this buyer?",
                criteria=["Browsing", "Researching", "Evaluating", "Ready to buy"],
            ),
            "competitor": _noul(
                "Is this a competitor rather than a prospect?",
                "Works at a competing vendor",
                "Genuine prospect",
            ),
        },
        "note": "Named contract end date plus a volume figure — should score high on both rubrics.",
    },
    # Added 2026-10-11, after jevai.org's use cases: four jobs this site had no page for.
    "invoice-classification": {
        "state": (
            "INVOICE INV-2026-0417\n"
            "From: Northwind Cloud Services Ltd, Dublin\n"
            "To: Brightlane Studio (accounts payable)\n"
            "Issue date: 2 October 2026. Due date: 9 October 2026. Received: 6 October 2026 (due in 3 days).\n"
            "Lines:\n"
            "  Managed Kubernetes cluster, September .... EUR 1,240.00\n"
            "  Object storage, 18 TB ..................... EUR 306.00\n"
            "  Priority support add-on ................... EUR 450.00\n"
            "  Priority support add-on ................... EUR 450.00\n"
            "Subtotal EUR 2,446.00. VAT 23% EUR 562.58. Total due EUR 3,008.58.\n"
            "Late payment fee of 2% after the due date."
        ),
        "questions": {
            "category": Choice(
                instructions="Which expense category does this invoice belong to?",
                criteria={
                    "cloud_hosting": "Servers, cloud platforms, storage and hosting",
                    "software": "Software licences and SaaS subscriptions",
                    "contractors": "Freelancers and professional services",
                    "travel": "Flights, hotels and transport",
                    "office": "Office supplies, equipment and rent",
                    "marketing": "Advertising, events and promotion",
                    "other": "Anything else",
                },
            ),
            "needs_review": _noul(
                "Should a person check this invoice before it is paid, because a line repeats, the totals do not add up, or a charge looks unusual?",
                "Needs a human check before payment",
                "Looks routine",
            ),
            "urgency": Score(
                instructions="How soon must this invoice be paid?",
                criteria=["No date pressure", "Due this month", "Due within a week", "Due now or overdue"],
            ),
        },
        "note": "A cloud invoice with one line charged twice. The due date is stated as days left, computed in code.",
    },
    "news-filtering": {
        "state": (
            "READER INTERESTS: open-source AI models, GPU prices, EU AI regulation.\n"
            "NOT INTERESTED IN: celebrity news, crypto prices, sports.\n\n"
            "HEADLINE: Cloud providers cut GPU rental prices by a third as new data centres open\n"
            "SUMMARY: Three of the largest providers matched the cut within a day; analysts expect smaller "
            "hosts to follow before the end of the quarter."
        ),
        "questions": {
            "keep": _noul(
                "Does this article match one of the reader's interests?",
                "Matches an interest",
                "Off-topic for this reader",
            ),
            "relevance": Score(
                instructions="How relevant is this article to this reader?",
                criteria=["Not relevant", "Slightly relevant", "Relevant", "Must read"],
            ),
            "topic": Choice(
                instructions="What is the article mainly about?",
                criteria={
                    "ai_models": "AI models and research",
                    "hardware": "Chips, GPUs and data centres",
                    "regulation": "Laws and policy",
                    "business": "Companies, markets and deals",
                    "other": "Anything else",
                },
            ),
        },
        "note": "A headline that matches one interest (GPU prices) without naming it in the same words.",
    },
    "product-categorization": {
        "state": (
            "TITLE: TrailFlex 2 Waterproof Hiking Shoe\n"
            "DESCRIPTION: Lightweight hiking shoe with a breathable waterproof membrane, a recycled mesh upper "
            "and a grippy outsole for wet rock. Wide fit available. Sizes 36 to 47.\n"
            "PRICE BAND: mid (USD 90 to 150)"
        ),
        "questions": {
            "category": Choice(
                instructions="Which category does this product belong in?",
                criteria={
                    "footwear": "Shoes, boots and sandals",
                    "apparel": "Clothing",
                    "bags": "Bags and backpacks",
                    "equipment": "Tents, poles and other gear",
                    "accessories": "Socks, hats, gloves and small items",
                },
            ),
            "activity": Choice(
                instructions="Which activity is it mainly made for?",
                criteria={
                    "hiking": "Hiking and trail walking",
                    "running": "Running",
                    "everyday": "Everyday and casual wear",
                    "climbing": "Climbing and mountaineering",
                    "travel": "Travel",
                },
            ),
            "audience": Choice(
                instructions="Who is the product marketed to?",
                criteria={
                    "women": "Women",
                    "men": "Men",
                    "unisex": "Not tied to a gender",
                    "kids": "Children",
                },
            ),
            "waterproof": _noul(
                "Is the product waterproof?",
                "Waterproof",
                "Not waterproof, or not stated",
            ),
            "sustainability_claim": _noul(
                "Does the listing make a specific sustainability claim, such as recycled or certified materials?",
                "Makes a specific claim",
                "No specific claim",
            ),
        },
        "note": "Category and activity are clear; the audience is not stated, so that answer should be less sure.",
    },
    "csv-data-validation": {
        "state": (
            "TABLE: customer_orders.csv, one row per order.\n"
            "COLUMNS: order_id, customer_name, email, country, product, quantity, unit_price_usd, order_date\n"
            "ROW: 10482, Ana Souza, ana.souza@exmaple.com, Brasil, Wireless mouse, 2, 24.90, 2026-02-30"
        ),
        "questions": {
            "valid": _noul(
                "Does every field in this row look plausible for its column?",
                "Every field looks plausible",
                "At least one field looks wrong",
            ),
            "issue": Choice(
                instructions="Which problem, if any, is the most serious in this row?",
                criteria={
                    "none": "No problem",
                    "email": "The email address looks mistyped or fake",
                    "country": "The country is misspelled or not in English",
                    "date": "The date is impossible or malformed",
                    "product_mismatch": "The product does not fit its price or quantity",
                    "missing": "A required value is empty",
                },
            ),
            "name_matches_email": _noul(
                "Does the email address plausibly belong to the named customer?",
                "Plausibly the same person",
                "Looks like someone else",
            ),
        },
        "note": "Three planted problems: a misspelled email domain, a non-English country name, and 30 February.",
    },
}

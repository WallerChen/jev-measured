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
}

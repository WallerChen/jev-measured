"""A labelled set for measuring accuracy, not just cost and latency.

Every other number this project publishes is about price and speed. None of
them say whether an answer is *right*, and a benchmark that never checks that
is half a benchmark. This is the missing half.

The hard part of an accuracy benchmark is the labels, so the construction is
the argument:

  UNAMBIGUOUS — each ticket contains exactly one decisive signal and nothing
  pulling the other way. "I was charged twice for the same order" is billing
  under any reasonable reading of the criteria, and a model that says
  `technical` is wrong rather than differently-opinioned. The label is a
  property of how the text was written, not of the author's taste. Disagree
  with one and you can open an issue against a specific string.

  AMBIGUOUS — deliberately two signals in tension. These carry NO label,
  because there is no correct answer, and scoring them would be scoring the
  grader. They are here to measure something else: whether a model's
  confidence drops when the question genuinely is hard. A model that is
  equally certain about both sets is not calibrated, however accurate it
  looks on the first.

Nothing here is cherry-picked for or against any model. The tickets were
written before anything was run.
"""

from __future__ import annotations

QUEUES = {
    "billing": "Payments, invoicing, refunds",
    "technical": "Bugs, outages, integrations",
    "account": "Login, permissions, plan changes",
    "sales": "Pricing, upgrades, new accounts",
    "spam": "Unsolicited or irrelevant",
}

# (text, correct queue). One decisive signal each, nothing in tension.
UNAMBIGUOUS: list[tuple[str, str]] = [
    ("I was charged twice for order 5512 — same amount, same day. Please refund the duplicate.", "billing"),
    ("My invoice for October shows a line item I do not recognise. Can you break it down?", "billing"),
    ("The card on file expired and the renewal payment failed. Where do I update it?", "billing"),
    ("You refunded £40 but my bank shows £4. Can you check what was actually sent?", "billing"),
    ("I cancelled in August and have been billed for September and October anyway.", "billing"),
    ("Please send a VAT receipt for invoice INV-20981 to our finance address.", "billing"),

    ("The export button returns a 500 and the browser console shows a CORS error.", "technical"),
    ("Your webhook has been retrying the same delivery for two hours and never succeeds.", "technical"),
    ("Since yesterday's release the SDK throws 'unexpected token' on every response.", "technical"),
    ("The dashboard graph renders blank on Safari but works on Chrome.", "technical"),
    ("API latency went from 200ms to 9 seconds at about 03:00 UTC and has stayed there.", "technical"),
    ("Uploading a file over 10MB fails silently — no error, nothing in the log.", "technical"),

    ("I cannot log in. The password reset email never arrives, I have checked spam.", "account"),
    ("Please remove Dave from the workspace, he left the company on Friday.", "account"),
    ("I need admin rights on the shared project so I can invite contractors.", "account"),
    ("Two-factor is bound to a phone I no longer have. How do I re-enrol?", "account"),
    ("Can you change the email on my account from the old domain to the new one?", "account"),
    ("We want to move from the team plan to the organisation plan — same data, same users.", "account"),

    ("What does the Enterprise tier cost for 400 seats, and is there an annual discount?", "sales"),
    ("We are evaluating three vendors this quarter. Can someone walk us through the product?", "sales"),
    ("Do you offer a non-profit rate? We are a registered charity in the UK.", "sales"),
    ("Is there a trial longer than 14 days? Our procurement cycle takes six weeks.", "sales"),
    ("Please send a quote for 1,200 seats with SSO, addressed to our purchasing department.", "sales"),

    ("CHEAP ROLEX WATCHES 90% OFF CLICK NOW LIMITED TIME luxurywatch-deals.biz", "spam"),
    ("Dear Sir, I represent a client wishing to transfer $14,500,000 and require your assistance.", "spam"),
    ("Grow your Instagram to 50k followers guaranteed! DM for our SMM panel pricing.", "spam"),
    ("Hi! Just checking if you want backlinks. We have 2000 high DA sites ready.", "spam"),
]

# No labels on purpose. Two signals pulling in different directions, so the
# only honest measurement is whether confidence falls.
AMBIGUOUS: list[str] = [
    "My card was charged for the Pro upgrade but the dashboard still shows the free plan, and the API keeps rejecting my requests with a quota error.",
    "I was double billed, and separately I cannot log in to check whether the second charge actually created a second account.",
    "We are considering the enterprise plan, but first: does your SSO actually work? The trial integration has been failing all week.",
    "Renewal failed and now the whole team is locked out. Is this a payment problem or a permissions problem?",
    "Someone on my team upgraded us without asking. I want it reversed and I want to know who has the rights to do that.",
    "The invoice is wrong because the seat count is wrong, and the seat count is wrong because deactivated users are still showing as active.",
]


def choice_question() -> dict:
    return {"type": "choice", "instructions": "Which team should handle this ticket?", "criteria": QUEUES}

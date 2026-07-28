"""
Synthetic stand-in for a real knowledge base + conversation history.
Sized so the *naive* pipeline lands close to the ~100K input token
figure described in the assignment, so the before/after comparison
is realistic rather than a toy example.
"""

import random

random.seed(7)

TOPICS = [
    "refund policy", "shipping timelines", "warranty terms", "account security",
    "API rate limits", "billing cycles", "data retention", "SSO configuration",
    "webhook retries", "password reset flow", "subscription tiers", "SLA terms",
    "GDPR data export", "two-factor auth", "invoice generation", "team permissions",
]

def _make_doc(topic: str, idx: int) -> str:
    filler = (
        f"This section describes {topic} in detail. "
        "It covers edge cases, historical context, and examples that are mostly "
        "irrelevant to any single user question but were written for completeness. "
        "Support engineers should note that policy exceptions are handled case by case "
        "and that this paragraph repeats similar boilerplate language found in adjacent "
        "sections of the knowledge base. "
    ) * 10
    return f"[DOC {idx} | topic: {topic}]\n{filler}\n"

def build_full_knowledge_base(n_docs: int = 40) -> list[str]:
    """The entire KB — what the naive pipeline stuffs into every call."""
    docs = []
    for i in range(n_docs):
        topic = TOPICS[i % len(TOPICS)]
        docs.append(_make_doc(topic, i))
    return docs

def build_conversation_history(n_turns: int = 14) -> list[dict]:
    """A long-running agent conversation with tool calls and observations."""
    history = []
    sample_turns = [
        ("user", "Can you check why webhook retries are failing for account 8823?"),
        ("assistant", "Let me look up the webhook retry policy and recent delivery logs."),
        ("tool", "delivery_log: 14 attempts, backoff exceeded, endpoint returned 503 x9"),
        ("assistant", "The endpoint is returning 503s. Checking their rate limit tier next."),
        ("tool", "rate_limits: tier=pro, limit=1000/min, current_usage=420/min"),
        ("assistant", "Rate limit isn't the issue. Checking SSL cert expiry on their endpoint."),
        ("tool", "ssl_check: cert valid, expires in 340 days"),
        ("assistant", "Cert is fine. This looks like an issue on their receiving server."),
        ("user", "Ok, also can you pull their current subscription tier and billing status?"),
        ("tool", "billing: tier=pro, status=active, next_invoice=2026-08-14"),
        ("assistant", "Billing is active, no issues there."),
        ("user", "Great, last thing — what's our SLA commitment for webhook delivery?"),
        ("assistant", "Let me check the SLA terms doc."),
        ("user", "Thanks."),
    ]
    for i in range(min(n_turns, len(sample_turns))):
        role, content = sample_turns[i]
        history.append({"role": role, "content": content})
    return history

def build_tool_schemas() -> list[dict]:
    """Full verbose tool definitions, as an agent framework might auto-generate them."""
    tools = []
    for name in ["lookup_delivery_log", "check_rate_limit", "check_ssl_cert",
                 "get_billing_status", "get_sla_terms", "search_kb", "escalate_ticket"]:
        tools.append({
            "name": name,
            "description": (
                f"Use this tool to {name.replace('_', ' ')}. "
                "This tool should be called whenever the user's request relates to "
                "this capability. Provide all required parameters. This tool returns "
                "structured data that should be summarized back to the user in plain "
                "language. Do not call this tool speculatively without a clear need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The account identifier, e.g. an integer or UUID string used to look up the account in the system of record."},
                    "reason": {"type": "string", "description": "Free text reason for the lookup, used for audit logging purposes only and not required for the query itself."},
                },
                "required": ["account_id"],
            },
        })
    return tools

QUERY = "Can you check why webhook retries are failing for account 8823, and confirm our SLA commitment?"

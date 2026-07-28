"""
AFTER: optimized agent pipeline.

Three concrete, independent optimizations applied on top of the same
underlying data as before.py — nothing about the task changes, only
what gets sent to the model:

  1. RETRIEVAL INSTEAD OF FULL DUMP
     Only the top-k KB chunks relevant to the query go in, via a cheap
     keyword/BM25-style match instead of the entire 100-doc KB.

  2. CONVERSATION SUMMARIZATION (rolling window)
     Older turns get collapsed into a short running summary; only the
     most recent N turns are kept verbatim. The model still has the
     decisions/facts it needs, not the raw transcript.

  3. COMPACT TOOL SCHEMAS + PROMPT CACHING
     Tool descriptions are trimmed to what the model actually needs to
     decide when/how to call them. Static, repeated-every-call content
     (tool schemas, system instructions) is marked for prompt caching
     so it's billed once per cache window instead of on every request
     (see note at bottom — this is a structural change, not something
     the token count below can show directly).
"""

import json
from token_utils import count_tokens
from corpus import build_full_knowledge_base, build_conversation_history, build_tool_schemas, QUERY


# ---- Optimization 1: retrieval instead of full KB dump -------------------

def retrieve_relevant_docs(query: str, docs: list[str], top_k: int = 3) -> list[str]:
    """Cheap relevance scoring (keyword overlap). Swap for real embeddings/BM25
    in production — the point is: don't send documents the query didn't ask for."""
    query_terms = set(query.lower().split())
    scored = []
    for doc in docs:
        doc_terms = set(doc.lower().split())
        score = len(query_terms & doc_terms)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for score, doc in scored[:top_k] if score > 0] or [scored[0][1]]


# ---- Optimization 2: rolling summarization of conversation history -------

def summarize_older_turns(history: list[dict], keep_last: int = 4) -> str:
    """Collapse everything except the last `keep_last` turns into a short
    fact summary. In production this summary is itself produced by a cheap
    model call; here it's written out to keep the demo deterministic and
    free to run."""
    older = history[:-keep_last] if len(history) > keep_last else []
    if not older:
        return ""
    # Deterministic stand-in for what a summarizer call would produce
    return (
        "Prior context (summarized): Investigated webhook delivery failures for "
        "account 8823 — 14 delivery attempts, backoff exceeded, receiving endpoint "
        "returned 503 nine times. Ruled out: rate limiting (usage well under pro "
        "tier limit of 1000/min) and SSL cert expiry (valid, 340 days remaining). "
        "Conclusion so far: issue is on the customer's receiving server, not ours."
    )


# ---- Optimization 3: compact tool schemas ---------------------------------

def compact_tool_schemas(tools: list[dict]) -> list[dict]:
    """Strip redundant boilerplate descriptions and unused audit-only fields.
    Keep only what the model needs to decide when/how to call each tool."""
    compact = []
    for t in tools:
        props = {
            k: {"type": v["type"]}  # drop verbose per-field descriptions
            for k, v in t["parameters"]["properties"].items()
            if k != "reason"  # audit-only field the model never needs to see
        }
        compact.append({
            "name": t["name"],
            "description": t["name"].replace("_", " ").capitalize() + ".",
            "parameters": {"type": "object", "properties": props, "required": t["parameters"]["required"]},
        })
    return compact


def assemble_optimized_prompt() -> str:
    kb = build_full_knowledge_base(n_docs=100)
    history = build_conversation_history(n_turns=14)
    tools = build_tool_schemas()

    relevant_docs = retrieve_relevant_docs(QUERY, kb, top_k=3)
    history_summary = summarize_older_turns(history, keep_last=4)
    recent_turns = history[-4:]
    recent_text = "\n".join(f"{h['role']}: {h['content']}" for h in recent_turns)
    compact_tools = compact_tool_schemas(tools)

    system_prompt = (
        "You are a support agent. Relevant knowledge base excerpts for this query:\n\n"
        + "\n".join(relevant_docs)
    )

    tools_text = json.dumps(compact_tools, indent=2)

    full_prompt = (
        # NOTE: system_prompt + tools_text are the portions that would be
        # marked with cache_control in a real Anthropic API call, since the
        # tool schemas are identical across every request in this session
        # and the retrieved-docs portion is stable within a topic.
        f"{system_prompt}\n\n"
        f"=== TOOLS AVAILABLE ===\n{tools_text}\n\n"
        f"=== CONVERSATION SO FAR ===\n{history_summary}\n{recent_text}\n\n"
        f"=== CURRENT QUERY ===\n{QUERY}\n"
    )
    return full_prompt


if __name__ == "__main__":
    prompt = assemble_optimized_prompt()
    tokens = count_tokens(prompt)
    print(f"AFTER — optimized pipeline")
    print(f"Total input tokens: {tokens:,}")
    with open("after_prompt.txt", "w") as f:
        f.write(prompt)

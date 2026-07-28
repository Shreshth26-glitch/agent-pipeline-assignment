"""
BEFORE: naive agent pipeline.

Every call to the model re-sends:
  - the entire knowledge base (not just relevant docs)
  - the entire raw conversation history (no summarization)
  - full verbose tool schemas with redundant descriptions
  - no prompt caching — everything is billed as fresh input every time

This mirrors a common real-world anti-pattern: "just dump everything
into context so the model definitely has what it needs."
"""

import json
from token_utils import count_tokens
from corpus import build_full_knowledge_base, build_conversation_history, build_tool_schemas, QUERY

def assemble_naive_prompt() -> str:
    kb = build_full_knowledge_base(n_docs=100)
    history = build_conversation_history(n_turns=14)
    tools = build_tool_schemas()

    system_prompt = (
        "You are a support agent. Here is the ENTIRE knowledge base, in full, "
        "for every query regardless of relevance:\n\n"
        + "\n".join(kb)
    )

    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in history)

    tools_text = json.dumps(tools, indent=2)

    full_prompt = (
        f"{system_prompt}\n\n"
        f"=== TOOLS AVAILABLE ===\n{tools_text}\n\n"
        f"=== CONVERSATION HISTORY (raw, unsummarized) ===\n{history_text}\n\n"
        f"=== CURRENT QUERY ===\n{QUERY}\n"
    )
    return full_prompt

if __name__ == "__main__":
    prompt = assemble_naive_prompt()
    tokens = count_tokens(prompt)
    print(f"BEFORE — naive pipeline")
    print(f"Total input tokens: {tokens:,}")
    with open("before_prompt.txt", "w") as f:
        f.write(prompt)

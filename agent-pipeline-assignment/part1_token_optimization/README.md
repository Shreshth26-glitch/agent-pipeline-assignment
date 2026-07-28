# Part 1 — Token / Cost Optimization

## Setup

`corpus.py` simulates a realistic agent workload: a 100-document knowledge
base, a 14-turn conversation with tool calls, and verbose auto-generated
tool schemas — sized so the naive assembly lands right at the ~100K input
tokens described in the brief. `before.py` is the naive pipeline; `after.py`
applies the optimizations. Run `python3 run_comparison.py` to reproduce the
numbers below.

*(Tokenizer note: this sandbox has no network access to fetch tiktoken's
vocab file, so counts here use the standard ~4-chars/token estimate instead
of a real BPE tokenizer. The estimate is off by low double-digit percent at
most — good enough to demonstrate the shape of the improvement. Swap in the
real Anthropic token-counting endpoint for production numbers.)*

## Results

| Pipeline | Input tokens | 
|---|---|
| BEFORE (naive) | ~98,900 |
| AFTER (optimized) | ~3,600 |
| **Reduction** | **~96%** |

## The optimizations

### 1. Retrieval instead of full-context dump
**Before:** every call stuffs all 100 KB documents into the prompt,
regardless of relevance to the actual question.
**After:** a cheap relevance step (`retrieve_relevant_docs`) picks the
top-3 documents that actually match the query. In production this is a
real embedding/BM25 retrieval step, not keyword overlap — the demo keeps
it dependency-free, but the principle is identical: **only send what the
model needs to answer this specific question.**
**Quality tradeoff:** this is the change most likely to hurt quality if
done carelessly. If retrieval is bad (top-k too small, poor embeddings,
no reranking), the model can miss a document it needed and either
hallucinate or ask a clarifying question it shouldn't have to. Mitigate
with: a slightly larger top-k than feels necessary, a reranking step, and
a fallback ("if you don't have enough info, say so and request the
specific doc" rather than guessing). Well-implemented retrieval on a
well-structured KB usually has *no* quality cost for questions the KB
actually covers, and is a net quality *win* by removing distracting
irrelevant context.

### 2. Conversation history summarization (rolling window)
**Before:** the entire raw transcript, including tool call outputs, is
resent on every turn.
**After:** everything older than the last 4 turns collapses into a short
factual summary (`summarize_older_turns`); recent turns stay verbatim.
**Quality tradeoff:** summarization is lossy by construction. Numeric
precision, exact quotes, and verbatim tool outputs can degrade if the
summarizer paraphrases loosely. Mitigate by keeping structured facts
(IDs, numbers, decisions already made) as bullet points rather than prose,
and by never summarizing the *most recent* exchange, since that's most
likely to still be actively relevant. For long-running agent sessions this
is close to mandatory — without it, cost grows roughly quadratically with
conversation length since every past turn gets re-sent on every future turn.

### 3. Compact tool schemas (+ prompt caching for static content)
**Before:** auto-generated tool schemas include a paragraph of boilerplate
description per tool and audit-only fields the model never needs to see.
**After:** `compact_tool_schemas` strips both. Separately — and this is
a structural change the token *count* above doesn't capture but that
matters just as much for cost — the system prompt and tool schemas are
identical on every call within a session. In a real Anthropic API
integration these would be wrapped with `cache_control: {"type": "ephemeral"}`
so they're billed once and reused across calls in the cache window, instead
of being billed as fresh input tokens every single request.
**Quality tradeoff:** essentially none, as long as the trimmed description
still disambiguates *when* to call the tool vs. a similar one. The removed
fields (`reason`, long boilerplate) were never used by the model's
decision-making — they were audit/logging metadata that belonged in
post-processing, not in the prompt. This is close to a free win.

## What I'd do next in a real system
- Real retrieval (embeddings + reranker) instead of keyword overlap.
- A cheap model call to generate the rolling summary rather than a
  hand-written one, with periodic re-summarization instead of a fixed window.
- Prompt caching wired into the actual API calls, not just noted structurally.
- Track token usage per pipeline stage in logs/metrics so regressions
  (e.g. someone adds a new tool with a verbose description) get caught
  before they hit production cost.

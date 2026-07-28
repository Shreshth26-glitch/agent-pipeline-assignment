"""
Token counting with graceful fallback.

Tries tiktoken's cl100k_base encoding (what GPT-4-class tokenizers use,
a reasonable stand-in for Claude's tokenizer for order-of-magnitude
comparisons). If the vocab file can't be fetched (e.g. no network),
falls back to the standard ~4-characters-per-token heuristic that's
commonly used for quick estimates.

Swap in the real Anthropic tokenizer / `count_tokens` API call for
production use — this is deliberately dependency-light for the demo.
"""

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

    TOKENIZER_MODE = "tiktoken (cl100k_base)"

except Exception:
    def count_tokens(text: str) -> int:
        # ~4 chars/token is the standard rough heuristic for English text
        return max(1, len(text) // 4)

    TOKENIZER_MODE = "char-based approximation (~4 chars/token, tiktoken vocab unreachable offline)"

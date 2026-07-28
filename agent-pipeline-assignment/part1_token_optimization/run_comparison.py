from token_utils import count_tokens, TOKENIZER_MODE
from before import assemble_naive_prompt
from after import assemble_optimized_prompt

before_tokens = count_tokens(assemble_naive_prompt())
after_tokens = count_tokens(assemble_optimized_prompt())
reduction = (before_tokens - after_tokens) / before_tokens * 100

print(f"Tokenizer: {TOKENIZER_MODE}\n")
print(f"{'Pipeline':<12}{'Input tokens':>15}")
print(f"{'-'*27}")
print(f"{'BEFORE':<12}{before_tokens:>15,}")
print(f"{'AFTER':<12}{after_tokens:>15,}")
print(f"{'-'*27}")
print(f"Reduction: {reduction:.1f}%")

# Part 2 — Debugging an Intermittent Multi-Step Agent Pipeline

Symptoms as given: sometimes times out, sometimes returns malformed output,
sometimes silently succeeds with wrong data. Three different failure modes
means this isn't one bug — it's most likely 2-3 separate root causes that
happen to share a pipeline. I'd treat them as separate investigations from
the start rather than looking for one unifying explanation.

## Step 0 — Before touching code: make the failure observable

If the pipeline doesn't already have structured logging with a request ID
threaded through every step, that's the very first fix, before debugging
anything else. I need to be able to pull *one full trace* of *one failed
run* — every step's input, output, latency, and any retries — not just
"it failed." Specifically I want, per step:
- step name, start/end timestamp, duration
- input payload (or a hash/summary if too large to log)
- raw output before any parsing
- model/tool call parameters (temperature, max_tokens, tool used)
- any retry attempts and what triggered them

If this doesn't exist yet, I'd add it before anything else, since without
it every subsequent step is guesswork.

## Step 1 — Reproduce, or bucket by failure type if I can't

Try to get a reliable repro locally with logging on. If it's truly
intermittent (which "sometimes" implies), I don't wait for a repro — I go
straight to production logs and start bucketing recent failures into the
three categories:
- **Timeouts** — which step was in flight when it hit the timeout?
- **Malformed output** — what did the raw model/tool output actually look
  like right before parsing failed?
- **Silent wrong data** — this is the dangerous one, since nothing *errors*.
  I need known-good test cases with expected outputs to catch this at all.

I'd pull the last ~20-50 failed runs (by whatever bucket I can identify from
error logs or user reports) and look for a pattern: same step failing every
time? Same time of day? Same input shape/size? Same downstream service?

## Step 2 — Isolate by failure type

### Timeouts
- Check per-step latency distribution, not just total pipeline latency.
  One slow step disguises itself as "the pipeline is slow" — I want p50/p95/p99
  *per step*.
- Common culprits: an unbounded retry loop with no backoff cap, a tool call
  hitting an external API with no circuit breaker, or a step whose prompt
  size varies wildly between calls (ties back to Part 1 — huge inputs on
  some queries but not others = inconsistent latency).
- Check whether timeouts cluster on specific input characteristics (e.g.
  large document attachments, long conversation histories).

### Malformed output
- Pull the raw, unparsed model output for failed cases — not what the parser
  says, the actual raw text. Almost always one of:
  - the model's output got truncated (hit `max_tokens` mid-JSON) → check if
    malformed outputs correlate with longer responses
  - the parser assumes a strict schema but the model occasionally wraps
    output in markdown fences, adds a preamble, etc.
  - a step downstream fed a corrupted/partial input into a step that expects
    well-formed JSON, and the failure actually originated upstream
- I'd add strict output validation (schema validation, not just "did JSON.parse
  not throw") at every step boundary, so failures get caught and logged at
  the step that actually produced the bad output, not three steps later
  where it's opaque.

### Silent wrong data — hardest, needs to be caught proactively
- This can't be found by reading error logs, since there are none. I need:
  - a small set of golden test cases with known-correct expected output,
    run repeatedly (including under load) to catch nondeterminism
  - logging of intermediate state at each step so I can diff a "wrong data"
    run against a known-good run of the same input, step by step, to find
    exactly where the divergence happens
  - check for race conditions: is any step reading state that another
    concurrent run could have mutated? Shared mutable state (a cache, a
    session object, a global variable) between concurrent agent runs is a
    classic source of exactly this symptom — one request's data leaking
    into another's silently.
  - check for prompt/context bugs: is a variable being interpolated into a
    prompt sometimes stale (e.g. reading from a cache that hasn't
    invalidated yet)?

## Step 3 — Correlate across the three symptoms

Once I have concrete findings from each bucket, I check whether they share
a root cause. A very common pattern: a step near the start of the pipeline
occasionally returns a partial/malformed result under some condition (e.g.
load, large input, a flaky upstream API); depending on *what* that
malformed intermediate output looks like, downstream steps either:
- time out (if they retry-loop on invalid input),
- throw/produce malformed output (if they fail parsing loudly), or
- silently proceed with degraded/wrong data (if they fail parsing quietly
  and fall back to a default).

That would explain all three symptoms as manifestations of one upstream
issue, which is what I'd specifically go looking for before assuming
they're unrelated.

## Step 4 — Fix and prevent regression
- Add step-boundary schema validation with loud, specific failures (not
  silent fallbacks) — silent fallbacks are exactly what produced the
  "silently succeeds with wrong data" symptom in the first place.
- Add timeouts with sane caps and backoff at each external call, not just
  a single top-level pipeline timeout.
- Add the golden-case regression suite to CI (ties to Part 3) so this class
  of bug is caught before deploy, not in production.
- Add alerting on the specific failure signatures found (e.g. alert if
  malformed-output rate for a given step exceeds a threshold), so the next
  occurrence surfaces in minutes, not from a user report.

## Tools/logs I'd actually pull, concretely
- Structured request logs / APM traces (e.g. Datadog, Honeycomb, or
  equivalent) filtered by request ID, step name, and status
- Raw model API responses (not the app's parsed version) for failed and
  a sample of successful runs, to diff
- Per-step latency histograms, not just averages
- Any retry/circuit-breaker logs
- Recent deploy history — timing correlation with a deploy is one of the
  fastest ways to find a root cause and shouldn't be checked last

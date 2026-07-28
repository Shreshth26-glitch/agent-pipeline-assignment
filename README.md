# Agent Pipeline Take-Home — Submission

Covers all three parts of the brief: token/cost optimization, debugging an
intermittently failing agent pipeline, and CI/CD + deployment discipline.

## Repo layout

```
part1_token_optimization/   Runnable before/after token comparison
  corpus.py                   synthetic KB + conversation history + tool schemas
  before.py                   naive pipeline (~99K input tokens)
  after.py                    optimized pipeline (~3.6K input tokens)
  token_utils.py               token counting (tiktoken, with offline fallback)
  run_comparison.py            reproduces the before/after numbers
  README.md                    writeup: what changed, why, quality tradeoffs

part2_debugging/
  README.md                    step-by-step debugging walkthrough

sample_app/                  minimal app the CI/CD pipeline runs against
  app.py, tests/, requirements.txt

.github/workflows/ci-cd.yml  lint+test on push, deploy to staging on merge to main
part3_cicd_notes.md          secrets handling + rollback plan writeup
```

## Part 1 — Token optimization (see `part1_token_optimization/README.md`)

Ran a synthetic but realistic ~99K-input-token agent pipeline through three
optimizations — retrieval instead of full-context dump, rolling
conversation summarization, and compact tool schemas (+ prompt-caching
notes) — and got it down to ~3.6K tokens, a ~96% reduction, with the
quality tradeoffs of each change documented individually. Reproduce with:

```
cd part1_token_optimization
python3 run_comparison.py
```

## Part 2 — Debugging (see `part2_debugging/README.md`)

Written walkthrough of the actual process: get structured per-step
tracing in place first if it doesn't exist, bucket failures by symptom
(timeout / malformed output / silent wrong data) rather than treating
them as one bug, isolate each with concrete checks (per-step latency
distributions, raw pre-parse output, golden-case diffing for the silent
failures), then check whether one upstream root cause explains all three
symptoms before assuming they're unrelated.

## Part 3 — CI/CD (see `.github/workflows/ci-cd.yml` and `part3_cicd_notes.md`)

- GitHub Actions workflow: lint (`ruff`) + test (`pytest`) on every push;
  deploy to a `staging` GitHub Environment on merge to `main`, gated on
  the lint/test job passing, with a post-deploy health check.
- Secrets via GitHub Encrypted Secrets scoped to the environment, least
  privilege, OIDC preferred over long-lived cloud keys where supported,
  production kept as a separate gated environment from staging.
- Rollback plan: roll back to last-known-good immediately, verify it
  worked, communicate, *then* root-cause — rollback is a deploy operation,
  not a debugging operation.

## Why these choices

Each part optimizes for the same thing the brief is testing for: does the
engineering hold up under real constraints (cost, ambiguity, production
risk), not just "does it work once." Part 1 is runnable and shows real
numbers rather than claimed numbers. Part 2 is written as an actual
process with concrete tools/checks, not a generic checklist. Part 3 is a
real workflow file that lints and tests correctly (verified locally) with
deploy/rollback reasoning that treats staging and production as genuinely
different trust boundaries.

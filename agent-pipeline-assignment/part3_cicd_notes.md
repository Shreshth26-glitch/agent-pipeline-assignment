# Part 3 — CI/CD and Deployment

## 1. The pipeline (`.github/workflows/ci-cd.yml`)

- **On every push, any branch**: install deps, run `ruff check` (lint) and
  `pytest` (tests). This is the gate — nothing deploys if this fails.
- **On merge to `main`** (push event to main specifically, after the same
  lint/test job passes via `needs:`): deploy to a `staging` GitHub
  Environment. Using a GitHub Environment (not just a job) means I can
  attach environment-specific secrets and, if wanted, require manual
  approval before deploy — useful once this graduates past staging.
- The deploy step is left as an explicit placeholder rather than a
  third-party deploy action, on purpose: in a real repo I'd fill it with
  whatever the actual target is (Fly.io, ECS/Fargate, Cloud Run, a bare VM
  over SSH, etc), but I want the credentials it uses and the exact command
  it runs to be visible in the workflow file, not hidden inside an opaque
  marketplace action.
- A post-deploy health check step hits `/health` and would fail the job
  (and thus flag the deploy as bad) if the app doesn't come up cleanly —
  catching a broken deploy within the same pipeline run rather than
  waiting for someone to notice.

## 2. Secrets / API keys

- **Never in code or in the workflow file itself.** All credentials
  (`STAGING_DEPLOY_TOKEN`, `STAGING_HOST`, any third-party API keys) live
  in **GitHub Encrypted Secrets**, scoped to the `staging` Environment
  rather than repo-wide, so a workflow run against a feature branch can't
  accidentally access staging deploy credentials.
- Referenced only via `${{ secrets.X }}` inside `env:` blocks, so they're
  injected as environment variables at runtime and GitHub automatically
  masks them in logs.
- **Least privilege**: the staging deploy token should be scoped to
  *only* what's needed to deploy to staging — not a shared "prod-and-staging"
  credential, and not a personal access token tied to an individual's
  account (so it doesn't break when that person leaves).
- **Prefer OIDC over long-lived tokens where the target supports it** — e.g.
  AWS/GCP/Azure all support GitHub Actions OIDC federation, which issues a
  short-lived credential per workflow run instead of storing a permanent
  cloud key as a GitHub secret at all. That's the setup I'd push for on a
  real cloud target; it removes an entire class of "leaked long-lived
  credential" risk.
- **Rotation**: deploy tokens get rotated on a schedule and immediately on
  any suspected exposure or when someone with access leaves the team.
- Production secrets are a *separate* GitHub Environment from staging, with
  required reviewers on that environment, so a merge to main can't silently
  reach production credentials — production deploy would be a distinct,
  explicitly gated job.

## 3. Rollback plan — first 5 minutes if a deploy breaks production

1. **Stop the bleeding, don't diagnose first.** Immediately roll back to
   the last known-good deployment/image/artifact — most platforms
   (ECS, Fargate, Cloud Run, Fly, k8s) support redeploying the previous
   revision directly, which is faster than a `git revert` + re-run of the
   full pipeline. If deploys are container-based, this is "redeploy
   previous image tag," not "fix and redeploy."
2. **Confirm the rollback actually worked** — hit the health check /
   smoke-test endpoint, check error rate/latency dashboards return to
   baseline. Don't assume the rollback succeeded; verify it.
3. **Communicate** — post in the incident channel that production is
   degraded and a rollback is in progress/complete, with a rough timeline.
   This can happen in parallel with step 1, not after it.
4. **Only after production is stable**, start root-causing: pull the diff
   between the last-good and the broken deploy, check the CI logs for that
   run, check what changed (code, config, a dependency version, a secret
   rotation that didn't propagate).
5. **Fix forward properly**: write/extend a test that would have caught
   the regression, fix it, let it go through the normal CI/CD gate again —
   don't hotfix directly against production.

The core principle: **rollback is a deploy operation, not a debugging
operation.** The first move is always "get back to the last good state,"
not "find out what broke." Diagnosis happens after stability is restored,
with full logs and no time pressure, exactly like Part 2's approach but
without the added stress of live user impact while investigating.

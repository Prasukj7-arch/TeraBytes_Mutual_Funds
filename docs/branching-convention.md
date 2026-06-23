# Branching Convention

Kept deliberately simple — this is a 3-day project with 3 people, not a
long-lived production codebase. The goal is to avoid blocking each other,
not to enforce process for its own sake.

## Branches

| Branch | Purpose |
|---|---|
| `main` | Always deployable/demoable. Nothing broken gets merged here. |
| `feature/<owner>-<short-desc>` | All work happens here first. |

### Naming examples

```
feature/persona-nav-ingestion
feature/persona-dip-hike-sql
feature/personb-portfolio-endpoints
feature/personb-fund-history-route
feature/personc-recommendation-logic
feature/personc-forecast-model
```

Use your role tag (`persona` / `personb` / `personc`) consistently so it's
obvious at a glance whose work is in a given branch, especially when reviewing
PRs quickly under time pressure.

## Workflow

1. **Pull `main` before starting anything new each day:**
   ```bash
   git checkout main
   git pull
   ```

2. **Create your feature branch:**
   ```bash
   git checkout -b feature/persona-nav-ingestion
   ```

3. **Commit small, commit often.** Don't sit on a day's worth of changes
   uncommitted — if your laptop dies, that work is gone.
   ```bash
   git add .
   git commit -m "Add mfapi.in ingestion script for scheme list"
   ```

4. **Push and open a PR into `main` as soon as a piece works**, even if the
   whole day's task isn't done. Small PRs (e.g. "ingestion script for one
   fund" rather than "all of Day 1 ingestion") are easier to review fast and
   easier to unblock teammates with.
   ```bash
   git push -u origin feature/persona-nav-ingestion
   ```

5. **Get a quick review if someone's free; merge yourself if not.** On a
   3-day timeline, a PR blocked for hours waiting on review is worse than a
   self-merge with a heads-up message to the team. Post in your group chat
   what you merged and why.

6. **Resolve conflicts immediately**, not at the end of the day. If you're
   touching a shared file (like `docs/api-contract.md`), message the team
   before you start.

## Commit Message Style

Keep it short and action-first. No strict format needed for a 3-day project,
but aim for clarity:

```
Add dip/hike detection SQL using LAG window function
Fix missing NAV dates on weekends in ingestion script
Add GET /funds/{code}/history endpoint
```

## What NOT to do

- Don't work directly on `main`.
- Don't let a feature branch live more than a day unmerged — on this
  timeline, that's a third of the project.
- Don't change `docs/api-contract.md` without telling the other two people —
  it's the one file all three workstreams depend on.
- Don't commit raw data files, credentials, or `.env` files — check
  `.gitignore` covers what you're about to commit.

# morning-brief

The Claude Code cloud routine that generates a daily morning brief for the NusaDx (formerly Stampede) project.

Runs weekdays at 13:10 UTC (20:10 WIB). A **single agent on Opus 4.8** reads the team's Google Doc journals, scans recent Gmail, queries Europe PMC + ClinicalTrials.gov + web for TB/MDx news, and composes the brief as a Gmail draft. (Free with Claude Pro — one run/weekday, within the ~5-runs/day cap.)

## Files

- `SKILL.md` — **the single source of truth for the prompt** (frontmatter + body). Edit here.
- `routine.config.json` — non-prompt wiring only: trigger id, cron, model, allowed tools, MCP connectors. Edit here when the *wiring* changes (rarely).
- `deploy.md` — how to deploy `SKILL.md` to the live routine and how to check for drift.

There is intentionally **no `trigger.json`** — it used to embed a second full copy of the prompt and was the source of constant drift. The deploy now reads `SKILL.md` verbatim, so the prompt exists in exactly one place.

## Project context (synced)

The "Project Context" section of `SKILL.md` is **not authored here** — it is a synced copy of the canonical context block in the `work-tracker` repo (`context/project-brief.md`). When the project's phase, goals, team, or major decisions change, edit `project-brief.md` there first, then regenerate this block here and re-deploy. Don't let the two diverge.

## Modifying the routine

1. Edit `SKILL.md` (prompt) and/or `routine.config.json` (wiring).
2. Deploy via the ritual in [`deploy.md`](deploy.md) — open a Claude session here and say "deploy the morning brief." The deploy pushes `SKILL.md` verbatim and asserts the live body matches byte-for-byte.
3. Commit. The repo is the canonical, reviewable history; the live trigger is a verified copy of it.

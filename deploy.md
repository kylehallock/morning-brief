# Deploying / verifying the morning-brief routine

`SKILL.md` is the **single source of truth** for the prompt. `routine.config.json` holds the
non-prompt wiring (trigger id, cron, model, allowed tools, MCP connectors). There is **no**
`trigger.json` mirror anymore — the deploy reads `SKILL.md` verbatim, so nothing can drift.

The claude.ai routine can only be edited from an **authenticated Claude Code session** (the
RemoteTrigger API injects the OAuth token in-process; it is not callable from plain scripts/CI).
So "deploy" is a short ritual you run by talking to Claude in this repo — it stays free with Pro.

## To deploy

In a Claude Code session opened in this repo, say: **"deploy the morning brief."** Claude will:

1. Read `SKILL.md` (raw bytes) and `routine.config.json`.
2. `RemoteTrigger action: update` on `trigger_id`, setting:
   - `job_config.ccr.events[0].data.message.content` = **raw SKILL.md bytes** (no transformation),
     `role: "user"`.
   - `job_config.ccr.environment_id` = config `environment_id`.
   - `job_config.ccr.session_context` = `{ allowed_tools, model }` from config.
   - (cron / mcp_connections are already set on the trigger; include them only if changing.)
3. `RemoteTrigger action: get` and **assert** the returned `…message.content` equals `SKILL.md`
   byte-for-byte, and that `session_context.model` and `allowed_tools` match the config. If not,
   the deploy failed — do not consider it live.

## To verify a deploy / check for drift (anytime)

Say **"check the morning brief is in sync."** Claude does `RemoteTrigger get` and diffs the live
body against `SKILL.md`:
- **in sync** — live body == SKILL.md. Good.
- **repo ahead** — SKILL.md was edited but not deployed → run a deploy.
- **live ahead** — someone edited the routine in the claude.ai web UI → pull that body back into
  `SKILL.md` so the repo stays canonical, then commit.

## To test before trusting it unattended

`RemoteTrigger action: run` triggers an immediate run. Inspect the resulting Gmail **draft**
(it is never auto-sent): confirm MCP tools actually worked (journals + email populated, not the
"FAILED" notice), news has no repeats vs. recent briefs, and all sections render. Only rely on it
after a clean manual run.

## Trigger facts

- Live trigger id: see `routine.config.json` (`trigger_id`). The id changes if the routine is ever
  recreated — update the config, never hard-code it in prose.
- Schedule: `10 13 * * 1-5` = weekdays 13:10 UTC (20:10 WIB). Within the Pro ~5-runs/day cap.

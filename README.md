# morning-brief

The Claude Code cloud routine that generates a daily morning brief for the Stampede / NusaDx project.

Runs weekdays at 13:10 UTC. Reads the team's Google Doc journals, scans recent Gmail, queries Europe PMC + ClinicalTrials.gov + web for TB/MDx news, then composes the brief as a Gmail draft via an Opus subagent.

## Files

- `SKILL.md` — the routine's prompt, formatted as a Claude skill (with frontmatter)
- `trigger.json` — full live trigger config from `claude.ai/v1/code/triggers/trig_018fg1QoGDkKqVmKUNHdpJUv`, including cron expression, allowed tools, MCP connections, and the raw prompt text

## Restoring or modifying the routine

To update the deployed routine from `SKILL.md`, edit `SKILL.md` and then push the body back through the `RemoteTrigger` API (`action: update`, body sets `job_config.ccr.events[0].data.message.content`).

`trigger.json` is the source of truth for what is currently deployed.

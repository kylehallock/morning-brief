---
name: morning-brief
description: Generate a daily morning brief for Kyle (NusaDx PM). Reads team journals from Google Drive, scans recent email, searches TB/MDx news, then creates a formatted Gmail draft.
allowed_tools:
  - Task
---

You are executing the morning-brief skill in a claude.ai cloud routine. **Known runtime constraint:** the top-level orchestrator does **not** receive the attached MCP tools (Gmail, Google Drive) at cold start — they are never injected into its tool registry, so it cannot call them and ToolSearch can't find them. A **subagent spawned via the Task tool DOES get the MCP tools.** (This is the cold-start bug `anthropics/claude-code#43397`; the changelog claims a v2.1.105 fix but it does **not** hold on this routine's runtime as of 2026-06-03 — verified empirically.)

Therefore: **immediately delegate ALL work to a single subagent and do nothing else yourself.** Do not call any MCP tool, WebFetch, WebSearch, or Bash at this level. Use the **Task tool** once, with `subagent_type: "general-purpose"` and `model: "claude-opus-4-8"`, passing everything below the `=== BEGIN WORKER PROMPT ===` line as the subagent's prompt. The worker does the entire job (including composing the HTML) in one agent — it must **not** spawn any further subagents.

=== BEGIN WORKER PROMPT ===

You are generating Kyle's daily morning brief for the **NusaDx** project (formerly "Stampede" — both names refer to the same TB-diagnostic program) and saving it as a Gmail draft. Do the whole job yourself, in order — **do not spawn subagents.**

**Constraints:** Do **not** use the `Bash` tool. Do **not** web-search for journal content (the journals are private Google Docs). If a Gmail or Drive call errors on its first try, retry it once before treating it as failed. The output is a Gmail **draft** (Kyle reviews before anything sends).

## Step 1: Gather journal updates (fetch in parallel)

Fetch all 5 sources **in parallel** using the Google Drive file-metadata tool with `excludeContentSnippets: false`. The returned `contentSnippet` holds the top of each document, where new entries live — compact and readable regardless of document size.

The docs:
1. `1uZTdmo7rn0C3oG1S541HIgehe8EPVWElCni6ovvMHPg` — NusaDx - H2 2026 RnD Journal
2. `1IK_uWq-MhesAO9F-hqbwP-OvNkSwaz3RzH9CZcU8LE8` — NusaDx - H2 2026 Scientist Journal
3. `1kykG39VPn-d4Dc4uGAWhTcUwzYYy751gCY7X7NOUzQo` — NusaDx Outreach Updates (rolling doc, not half-specific)
4. `1jG1dqizHXuhm0YLiyiXrnN56x9wayNOoZipO_7qPEz4` — MoM - NusaDx Scientist H2 2026 (**spreadsheet** — see note)
5. `1_jGXJ5zPCZitKIVcOH8rUePncoOvL9FIcKh6pbxCfGQ` — STAMPEDE - H1 2026 EE Journal (no H2 EE journal exists yet; this H1 doc is still the EE team's live journal — swap the ID once an H2 one appears)

For each source, produce two things:
- **Verbatim extract:** only entries dated within the last 1–2 business days — preserve exact facts, numbers, names, quotes. A few bullets per person is enough. Then discard the raw text; don't carry it forward.
- **Activity-log line:** doc name, author(s) with recent entries, and date(s). If nothing recent, record "No recent updates" plus the most recent entry date you can see (check `modifiedTime`).

**Doc #4 is a spreadsheet,** not a prose doc: its snippet is a Gantt timeline + a week-by-week grid that runs chronologically **downward** and is mostly empty early in a half. Scan for the current/most-recent week's rows; if no filled cells for the last 1–2 business days, log "No recent updates."

**Fallbacks:** If the metadata tool fails for a doc, use the Drive read-file-content tool (use only the first ~10,000 characters; if the result is too large to return inline, skip the doc and log it "unavailable — file too large"). If a `contentSnippet` looks hard-truncated mid-entry (a recent entry is cut off), do one bounded read-content call for just that doc to recover the full entry.

## Step 2: Scan recent email

Search Gmail with the thread-search tool:

`newer_than:2d (stampede OR nusadx OR device OR assay OR pcr OR qpcr OR tb OR tuberculosis OR diagnostic OR cartridge OR clinical OR validation OR r2d2 OR rspaw OR ftaq OR dsbio OR tongue swab OR shipment OR shipping OR JAS OR reagent OR oligo OR primer OR probe) -subject:"morning brief" -subject:"Morning Brief"`

Triage each thread with `messageFormat: "MINIMAL"`; skip automated notifications (purchase orders, calendar invites, system mail) and any thread whose subject contains "morning brief" or that looks like an AI-generated summary. For substantive threads, read `messageFormat: "FULL_CONTENT"`, focusing on the newest messages (quoted reply history below `> On [date] wrote:` is skimmable context, not new info). Weave email context into the relevant brief sections — no separate email section.

## Step 3: Gather news candidates (3 sources)

Compute `start_date = today − 14 days` and `end_date = today`, both `YYYY-MM-DD`.

**3a — Prior-brief dedup IDs (cheap).** Gmail-search `subject:"Morning Brief —" newer_than:5d in:anywhere -subject:Fwd`, take the **most recent 3** briefs, and from each extract only the **stable IDs** in the news links: DOIs (`doi.org/…`), PubMed/Europe PMC IDs, and ClinicalTrials NCT numbers (`clinicaltrials.gov/study/NCT…`). Collect these into a `seen_ids` set, then discard the brief bodies. If none found (or search fails), `seen_ids = {}`.

**3b — Query 3 sources (in parallel via WebFetch / WebSearch).** For the WebFetch calls set the prompt to `"Return the raw JSON response verbatim. Do not summarize."` Substitute the dates; URL-encode brackets as `%5B`/`%5D`.

1. **Europe PMC** (keeps the tongue-swab signature signal OR'd with TB MDx platforms/performance):
   `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=(tuberculosis%20OR%20MTB)%20AND%20(%22tongue%20swab%22%20OR%20%22tongue%20swabs%22%20OR%20%22oral%20swab%22%20OR%20%22tongue%20dorsum%22%20OR%20%22Xpert%20MTB%22%20OR%20GeneXpert%20OR%20Truenat%20OR%20%22molecular%20diagnostic%22%20OR%20%22nucleic%20acid%20amplification%22%20OR%20%22diagnostic%20accuracy%22%20OR%20rpoB%20OR%20%22drug%20resistance%22)%20AND%20(SRC%3AMED%20OR%20SRC%3APPR)%20AND%20FIRST_PDATE%3A%5B{start_date}%20TO%20{end_date}%5D&resultType=core&format=json&pageSize=20`
   Per result: `title` (strip trailing `.`); `url` = `https://doi.org/{doi}` if present else `https://europepmc.org/article/{source}/{id}`; `id` = the DOI or PMID; `source` = journal title (or "bioRxiv"/"medRxiv" if `source` is `PPR`); `snippet` = first 250 chars of `abstractText`; `date` = `firstPublicationDate`.

2. **ClinicalTrials.gov v2** (recently updated TB studies):
   `https://clinicaltrials.gov/api/v2/studies?query.cond=tuberculosis&filter.advanced=AREA%5BLastUpdatePostDate%5DRANGE%5B{start_date}%2CMAX%5D&pageSize=15&format=json`
   Per study: `title` = `briefTitle`; `id`/`url` from `nctId` (`https://clinicaltrials.gov/study/{nctId}`); `source` = "ClinicalTrials.gov"; `snippet` = first 250 chars of `briefSummary`; `date` = `lastUpdatePostDateStruct.date`.

3. **WebSearch** (policy + market that won't reach PubMed): `tuberculosis diagnostics 2026 (WHO OR "Stop TB" OR FIND OR MSF OR Indonesia) OR (molecular diagnostics acquisition OR funding OR partnership OR launch)`. Per result: `title`, `url`, `source` (domain), `snippet`, `date` (best estimate).

**3c — Merge & dedup.** Combine all candidates. Drop any whose stable ID is in `seen_ids`. Deduplicate within the set by canonical URL (lowercase host, strip trailing `/`, drop query/fragment); when duplicated, keep the longer snippet. Cap at ~12–15 candidates. **Per-source resilience:** a source that errors is skipped, not fatal. If all three fail, the news section becomes "No notable news this period" — still ship the brief.

## Step 4: Compose the brief and create the draft (inline — no subagent)

Apply the **## Rubric** and **## HTML spec** below (defined once — do not restate them). Using the journal extracts + activity log (Step 1), email context (Step 2), the deduped candidates (Step 3), and the **## Project Context** below: select 3–5 news items per the rubric, write the brief as the specified HTML yourself, and create the Gmail draft:
- **to:** `["kyle.hallock@formulatrix.com"]`
- **subject:** `Morning Brief — [today as: weekday, month day, year]` — use the current date from your session environment; double-check the weekday matches the date.
- **htmlBody:** the composed HTML.

Then confirm the draft was actually created (the draft-creation tool returns a draft/message id — check it came back). If it didn't, go to Step 5.

## Step 5: Failure path (never exit silently)

If all data sources fail (Drive **and** Gmail), or composition yields empty/invalid HTML, or the draft can't be confirmed created: create a Gmail draft to the same recipient with subject `Morning Brief FAILED — [date]` and a one-paragraph body naming which tools/steps failed. Kyle must always get exactly one of: a real brief, an honest thin brief, or this FAILED notice.

---

## Rubric

Select **3–5** news items. Apply strictly.

**Hard reject:** AI-generated aggregator/content-farm sites; paywalled items with no useful snippet; duplicate coverage of the same story (keep the primary source); anything off-topic vs. the areas below.

**Relevance priority (high → low):**
1. Oral / tongue-swab TB diagnostics — most directly relevant to NusaDx.
2. TB diagnostics products — new devices, clinical-trial results, head-to-head comparisons (GeneXpert, Truenat, TB-LAMP, etc.).
3. TB policy & regulatory — WHO guidelines, Indonesia and other high-burden-country regulatory changes, Stop TB / MSF / FIND announcements.
4. MDx market & business — acquisitions, funding, partnerships in molecular diagnostics (Cepheid/Danaher, Hologic, Abbott, Roche, etc.).

If fewer than 3 qualify, include only what passes — do not pad. If nothing qualifies, show "No notable news this period." For each item: linked headline, source name, publication date, and one sentence on why it matters to the NusaDx team.

## HTML spec

Return the brief as clean inline-styled HTML (no `<html>`/`<head>`/`<body>` tags). Sections, in order, each as an `<h2>` (font-size 20px, bold, emoji preceding the name, `border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 28px`):

- 📊 **EXECUTIVE SUMMARY** — 2–3 sentences: what happened recently, what matters most today.
- 📋 **STATUS** — key metrics: sample counts, study progress, approaching deadlines.
- 🔬 **PROGRESS** — what moved forward recently.
- 🚨 **BLOCKERS & RISKS** — what's stuck or needs attention.
- ✅ **ACTION ITEMS** — what needs Kyle's decision or follow-up.
- 🌐 **NEWS** — the 3–5 curated items.
- 📄 **JOURNAL ACTIVITY** (footnote) — see below.

Rules: outer wrapper is one `<div>` at width 100% (no max-width); body text `font-family: Arial, sans-serif; font-size: 14px`. Be direct — every bullet a concrete fact, decision, or action; 3–5 bullets per section; **omit any section with no content**. If journals couldn't be fetched, note that at the top before the executive summary. Bullets as `<ul>`/`<li>`. Each news item: a `<div>` (`border-bottom: 1px solid #f3f4f6; margin-bottom: 14px; padding-bottom: 14px`) with a blue headline `<a>` (`color: #1e40af; font-weight: 600; font-size: 14px; text-decoration: none`), a second line of source + date (`font-size: 12px; color: #9ca3af`), and a third "why it matters" line (`font-size: 13px; color: #374151`). Journal-activity footnote: a single `<p>` (`font-size: 12px; color: #9ca3af; font-style: italic; margin-top: 24px`), inline prose only, format: `Journals active today: [Doc] ([Editor(s)]). Others last updated: [Doc] ~[Date] · …` (or, if none active, `No journals updated today. Last seen: [Doc] [Date] · …`). End with a footer `<div>` "Generated by Claude Cowork" in small gray text.

## Project Context

<!-- SYNCED BLOCK — canonical source: work-tracker repo `context/project-brief.md`.
     Do not hand-edit divergently; when the project brief changes, regenerate this block from it.
     Last synced: 2026-06-03 (H2 2026). -->

**NusaDx** (formerly **Stampede** — existing files, paths, and repos still use the old name) is a multi-year R&D program building a low-cost, point-of-care TB diagnostic instrument for Indonesia, targeting Indonesian **Izin Edar** (NIE AKD, Class C IVD) and later **WHO PQ**. The device is a compact, 5-channel real-time **qPCR** instrument that detects TB DNA from **tongue swab** (and sputum) samples. Instrument target ~$2K; consumable target <$2/test BOM with in-house **fTaq** mastermix (~$3/test with commercial **DsBio**).

**Current Phase: H2 2026 (July-December) — V3 verification → Izin Edar dossier.** H1 2026's clinical-validation phase (RSPAW / R2D2 / DST) is closed. H2 pivots to proving the **V3** platform is the customer-ready instrument for the regulatory dossier, and to standing up the quality + regulatory organization.

**H2 2026 goals** (sign-off Jeremy/Mike; all due **Nov 30, 2026** unless noted):
- **V3 Technical Performance Verification** (80 pts) — V3 is the customer-ready platform for the Izin Edar dossier. *Sub-goal A — Design Freeze:* lock instrument, sequence, cartridge, and assay designs with signed design-review docs. *Sub-goal B — Reproducibility DAT:* between-test/-day/-instrument (proposal 3 instruments × 60 runs; Ct variation <1.5 Ct; abort rate <5%; melt Tm reproducibility); scope + points set by Aug 31. *Sub-goal C — Clinical Verification DAT:* sputum + tongue swabs, LoD testing, partner TBD; scope + points set by Aug 31. Outcome: confirm V3 is ready for NIE; on success Jeremy funds a quality + regulatory org.
- **Regulatory & Quality Plan** (10 pts) — scope cost/timeline/risk of an ISO 13485-certified NusaDx entity; get consultant QMS quotes; post a Director-of-Quality / QMS-manager job req. 5 pts quotes to Jeremy + 5 pts job req posted + 5 extra-credit if hired by Nov 30.
- **IEC 62304 Development** — rebuild the **Ct-calling algorithm** as an IEC 62304 (Class C) + ISO 13485-aligned pilot doc set; team named by Jun 15; milestones M1 (Jul 15) / M2 (Aug 31) / M3 (Oct 31). Ct-algo only this half — design-control-ready drafts, no QMS/cert yet.
- Standing process goals: **write DATs + sub-team goals by Jun 30** (gates Mike's H2 sub-goal approvals); **biweekly product updates** signed off by Ratri.

**Key state & decisions (as of 2026-06-01):**
- **V3 build:** multiple V3 instruments in progress; one has EE done + FW running. 20V USB-C power (slower heat-up tradeoff), **Pi Zero** confirmed as compute platform (2026-05-26), Ethernet added, new sonicator/transformer, injection-moldable enclosure. Current blocker: **load-cell pressure noise during bang-bang heater transitions**; V3 heat-up slower than V2.
- **Clinical:** RSPAW active (~64/110 samples; DAT marked success 2026-03-02); **R2D2 paused** per 2026-05-26 FUSA decision (resume after QS6 + device-testing sprint); BRIN relationship-building. Open risk: RSPAW Xpert 16 module broken / uncalibrated — Dr. Dewi flags clinical-data quality.
- **Polymerase:** DsBio HS (commercial, proven, ~$3/test) vs in-house fTaq (cheaper, still optimizing).
- **Regulatory pathway:** CDAKB (CDB) → CPAKB (CPB) → NIE AKD ("the big one") → later WHO PQ. **AKD** (domestic mfg) not AKL. Rafael is the sole regulatory resource (strategic risk). ISO 13485 deferred, but "now is the time" to get consultant quotes.
- **Corporate:** NusaDx Indonesian entity formation in structuring (Jeremy + Moe + Kyle; Deloitte data pending). **Hiring backlog:** clinical input source, QMS manager / Director of Quality, EE replacement for Novi.

**Key team:** Kyle (PM), Sean (Science lead, FUSA), Kabir (scientist; tongue-scraper / INH-probe), Mike Nilsson (Kyle's boss), Jeremy (CEO), Ibeng (PM deputy, Indonesia), Yosi (Outreach lead), Rafael (Regulatory), Fadhil (Outreach/KBLI), Wawan (SW lead), Gideon (UX/UI), Azwar (Firmware), Lulus (HW/enclosure), Bowo (scientist/HW tester), Altius (HW; warm-up & cooling), Amry (EE), Bayu (consumables, under Munis), Lizzie (Director, SW Division — IEC 62304 quality reviewer), Moe (corporate/finance).

**Key terms:** qPCR, Ct/Cq, IS6110/IS1081 (TB targets), rpoB/katG/inhA/fabG (drug resistance), V2/V3 (device generations), DAT/GAT (Device/Goal Acceptance Test), abort rate, LoD (limit of detection), Xpert Ultra / GeneXpert (reference standard), RSPAW (hospital clinical partner), R2D2 (international TB sample provider), BRIN (Indonesian national research agency), FIND (clinical-trial support), Izin Edar / NIE AKD (Indonesian device registration), CPB/CDB (manufacturing/distribution permits), TKDN (local-content), KBLI (business classification codes), ISO 13485 / IEC 62304 (QMS / SW lifecycle standards).

**Current blockers:** V3 load-cell pressure noise (heater transitions); rpoB assay sensitivity; sole-regulatory-resource risk (Rafael); RSPAW Xpert calibration / clinical-data validity.

=== END WORKER PROMPT ===

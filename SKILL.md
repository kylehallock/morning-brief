---
name: morning-brief
description: Generate a daily morning brief for Kyle (NusaDx PM). Reads team journals from Google Drive, scans recent email, searches TB/MDx news, then creates a formatted Gmail draft.
allowed_tools:
  - Task
---

You are executing the morning-brief skill. Due to a known cold-start bug with MCP tools in cloud routines (anthropics/claude-code#43397), you MUST immediately delegate ALL work to a subagent. Do not attempt
to call any MCP tools (Gmail, Google Drive) directly.

**Immediately** use the **Task tool** with `subagent_type: "general-purpose"` to spawn a single subagent. Pass the entire instruction set below as the subagent's prompt. Do nothing else — the subagent will
handle everything.

---

BEGIN SUBAGENT PROMPT:

You are generating a daily morning brief for Kyle, the Product Manager of the NusaDx project (formerly "Stampede" — both names refer to the same TB-diagnostic program). Read the team's project journals and recent emails, identify what's new, and compose a structured summary as a
Gmail draft.

**Automation constraint:** Do not use the `Bash` tool at any point during this task. This is an unattended scheduled run.

## Step 1: Gather data from Google Docs journals

Fetch these 5 Google Docs **one at a time, sequentially** — do NOT fetch them in parallel. This is critical to avoid flooding the context window.

For each doc, use the Google Drive file metadata tool with `fileId` set to the doc ID and `excludeContentSnippets: false`. This returns a `contentSnippet` field containing the top of the document, which is
where new entries live. The snippet is compact and always readable regardless of how large the document grows.

The docs to fetch, in order:
1. `1uZTdmo7rn0C3oG1S541HIgehe8EPVWElCni6ovvMHPg` — NusaDx - H2 2026 RnD Journal
2. `1IK_uWq-MhesAO9F-hqbwP-OvNkSwaz3RzH9CZcU8LE8` — NusaDx - H2 2026 Scientist Journal
3. `1kykG39VPn-d4Dc4uGAWhTcUwzYYy751gCY7X7NOUzQo` — NusaDx Outreach Updates (rolling doc, not half-specific)
4. `1jG1dqizHXuhm0YLiyiXrnN56x9wayNOoZipO_7qPEz4` — MoM - NusaDx Scientist H2 2026 (this one is a **spreadsheet**, not a prose doc — see note below)
5. `1_jGXJ5zPCZitKIVcOH8rUePncoOvL9FIcKh6pbxCfGQ` — STAMPEDE - H1 2026 EE Journal (the EE team has **not yet started an H2 2026 journal**; this H1 doc is still their live journal. Swap this ID for the H2 EE journal once one exists.)

**Doc-format note (doc #4):** Docs #1, #2, #3, and #5 are prose Google Docs where new entries sit at the **top**. Doc #4 (MoM) is a **Google Sheet** — its `contentSnippet` is a Gantt timeline plus a week-by-week management grid that runs chronologically **downward**, and early in a half it is mostly empty. For doc #4, scan for the row block matching the current/most-recent week rather than assuming the newest content is at the top; if the grid has no filled cells for the last 1-2 business days, record it as "No recent updates" in the activity log.

**After fetching each doc, immediately do the following before fetching the next:**
1. For the prose docs (#1, #2, #3, #5), new entries are at the **TOP** — scan the `contentSnippet` from the beginning. For the spreadsheet (#4), apply the doc-format note above.
2. Extract only the entries dated within the last 1-2 business days as a **verbatim excerpt** — preserve exact facts, numbers, names, and quotes. A few sentences or bullet points per person is sufficient.
3. **Record document activity:** For each doc, note the short document name, the author(s) who had entries in the last 1-2 business days, and the date(s) of those entries. If a doc had no recent entries,
record it as "No recent updates" and note the date of the most recent entry you can see (also check `modifiedTime` from the metadata). Keep this as a separate structured list (the "activity log").
4. Record your extract in a running list labeled by doc name.

Once all 5 docs are processed, you will have two compact lists: (a) verbatim extracts and (b) the activity log. Do not compose the brief yet — proceed to Step 2 to add email context, then synthesize
everything together in Step 3.

### Data collection guardrails

**If the Google Drive file metadata tool fails or returns no `contentSnippet`:**
Fall back to the Google Drive read file content tool for that doc. If the result is returned inline, use only the first 10,000 characters. If the result is saved to a file (oversized), skip that doc and mark
 it as "unavailable — file too large" in the activity log.

**NEVER search the web for journal content.** Do not use WebSearch to find or reconstruct journal entries. The journals are private Google Docs — web searches will waste tokens and produce nothing useful.

**If all data sources fail (Drive AND Gmail), do not produce a brief.** Instead, notify Kyle by creating a Gmail draft with subject "Morning Brief FAILED — [date]" explaining which tools were unavailable.

## Step 2: Read recent emails

Search Gmail using the Gmail thread search tool with query:

newer_than:2d (stampede OR device OR assay OR pcr OR qpcr OR tb OR tuberculosis OR diagnostic OR cartridge OR clinical OR validation OR r2d2 OR rspaw OR ftaq OR dsbio OR tongue swab OR shipment OR shipping
OR JAS OR reagent OR oligo OR primer OR probe) -subject:"morning brief" -subject:"Morning Brief"

For each thread returned, use the Gmail get thread tool with `messageFormat: "MINIMAL"` to triage it. Skip automated notifications (purchase orders, calendar invites, system emails). Also skip any thread
whose subject contains "morning brief" (any case) or whose content appears to be an AI-generated project summary.

For threads that look substantive, use the Gmail get thread tool again with `messageFormat: "FULL_CONTENT"` to read the complete messages. Focus on the newest messages in each thread — the quoted reply
history below `> On [date] wrote:` blocks is context you can skim, not new information.

## Step 2.5: Gather news candidates

Goal: produce a deduplicated list of candidate articles for the 🌐 NEWS section. Use direct scientific APIs (via WebFetch) for peer-reviewed papers, preprints, and clinical trials; keep a small WebSearch
component for market and policy news that won't appear on PubMed. Exclude URLs already shown in recent briefs.

Compute two date strings before issuing any call:
- `start_date = currentDate − 14 days`, formatted `YYYY-MM-DD`
- `end_date = currentDate`, formatted `YYYY-MM-DD`

### Step 2.5.a — Pull URLs already shown in recent briefs

Search Gmail using the Gmail thread search tool with query:
subject:"Morning Brief —" newer_than:14d in:anywhere -subject:Fwd

Take up to 7 matching threads (most recent first). For each, get the full thread content using the Gmail get thread tool. From the HTML body of the original (non-forwarded) message, extract every URL inside
`<a href="...">` between the `🌐 News` heading and the next `<h2>` (or end of body) — these are URLs already shown to Kyle. After extracting URLs from a thread, **discard the rest of that thread's content**
before moving on; only the URL set needs to survive. Normalize each URL to a canonical form: lowercase host, strip trailing `/`, drop any `?query` or `#fragment`.

Result: a set `seen_urls` of canonical URLs from the last ~7 briefs. If the search returns no threads or extraction yields zero URLs (first run), set `seen_urls = {}` and continue.

### Step 2.5.b — Query free scientific APIs (4 calls in parallel via WebFetch)

For each call, set the WebFetch prompt to: `"Return the raw JSON response verbatim. Do not summarize."` This keeps the routine from receiving a paraphrase.

Use these exact URLs (substitute `{start_date}` and `{end_date}` with the values computed above; URL-encode date brackets as `%5B`/`%5D`):

1. **Europe PMC — tongue swab focus (primary signal)**
   https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=(tuberculosis%20OR%20%22M.%20tuberculosis%22%20OR%20MTB)%20AND%20(%22tongue%20swab%22%20OR%20%22tongue%20swabs%22%20OR%20%22oral%20swab%22%20OR%20%22oral%20swabs%22%20OR%20%22tongue%20dorsum%22)%20AND%20(SRC%3AMED%20OR%20SRC%3APPR)%20AND%20FIRST_PDATE%3A%5B{start_date}%20TO%20{end_date}%5D&resultType=core&format=json&pageSize=15

2. **Europe PMC — TB MDx broad (clinical performance, platforms)**
   https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=(tuberculosis%20OR%20%22M.%20tuberculosis%22%20OR%20MTB)%20AND%20(%22Xpert%20MTB%22%20OR%20GeneXpert%20OR%20Truenat%20OR%20%22TB-LAMP%22%20OR%20%22loop-mediated%20isothermal%20amplification%22%20OR%20%22molecular%20diagnostic%22%20OR%20%22molecular%20diagnostics%22%20OR%20%22nucleic%20acid%20amplification%22%20OR%20%22real-time%20PCR%22%20OR%20%22diagnostic%20accuracy%22%20OR%20%22sensitivity%20and%20specificity%22)%20AND%20(SRC%3AMED%20OR%20SRC%3APPR)%20AND%20FIRST_PDATE%3A%5B{start_date}%20TO%20{end_date}%5D&resultType=core&format=json&pageSize=15

3. **Europe PMC — TB drug resistance (rpoB / drug-susceptibility assay relevant)**
   https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=(tuberculosis%20OR%20%22M.%20tuberculosis%22%20OR%20MTB)%20AND%20(rpoB%20OR%20katG%20OR%20inhA%20OR%20%22rifampicin%20resistance%22%20OR%20%22isoniazid%20resistance%22%20OR%20%22drug-resistant%20tuberculosis%22%20OR%20%22drug%20resistance%22%20OR%20%22drug%20susceptibility%22%20OR%20rifampin)%20AND%20(SRC%3AMED%20OR%20SRC%3APPR)%20AND%20FIRST_PDATE%3A%5B{start_date}%20TO%20{end_date}%5D&resultType=core&format=json&pageSize=15

4. **ClinicalTrials.gov v2 — recently updated TB studies**
   https://clinicaltrials.gov/api/v2/studies?query.cond=tuberculosis&filter.advanced=AREA%5BLastUpdatePostDate%5DRANGE%5B{start_date}%2CMAX%5D&pageSize=15&format=json

Do NOT pre-narrow ClinicalTrials.gov with "tongue swab" or platform keywords — TB-trial volume is low enough that any term filter cuts too deep. Let Step 3's rubric pick.

For each Europe PMC result (in `resultList.result[]`), build a candidate record:
- `title` = `title` (strip any trailing `.`)
- `url` = `https://doi.org/{doi}` if `doi` is present, else `https://europepmc.org/article/{source}/{id}`
- `source` = `journalInfo.journal.title` if present, else `journalTitle`, else `"bioRxiv"`/`"medRxiv"` when the result's `source` field is `"PPR"`
- `snippet` = first 250 chars of `abstractText` (use empty string if missing)
- `date` = `firstPublicationDate`
- `pubType` = first non-generic entry from `pubTypeList` (or `pubTypeList.pubType[]`), e.g. `"Clinical Trial"`, `"Review"`, `"Journal Article"`. The list format varies between flat array and nested object — handle both.

For each ClinicalTrials.gov study (in `studies[]`):
- `title` = `protocolSection.identificationModule.briefTitle`
- `url` = `https://clinicaltrials.gov/study/{protocolSection.identificationModule.nctId}`
- `source` = `"ClinicalTrials.gov"`
- `snippet` = first 250 chars of `protocolSection.descriptionModule.briefSummary`
- `date` = `protocolSection.statusModule.lastUpdatePostDateStruct.date`
- `pubType` = `protocolSection.statusModule.overallStatus` (e.g. `"RECRUITING"`, `"COMPLETED"`)

### Step 2.5.c — Query non-paper news (2 WebSearch calls in parallel)

Run these two queries — they target events that don't reach PubMed (acquisitions, funding, WHO/Stop TB/MSF/FIND announcements, Indonesian MoH/BRIN/national TB program activity):

1. `molecular diagnostics tuberculosis acquisition OR funding OR partnership OR launch 2026`
2. `tuberculosis policy OR guidelines 2026 WHO OR "Stop TB" OR MSF OR FIND OR Indonesia`

For each search result, build a candidate record with `title`, `url`, `source` (the domain), `snippet`, `date` (best estimate from the result), and `pubType = "News"`.

### Step 2.5.d — Merge, dedup, hand off

Concatenate all candidates from 2.5.b and 2.5.c. Deduplicate by canonical URL (same normalization as the seen-URL set: lowercase host, strip trailing `/`, drop query and fragment). When the same paper appears via multiple Europe PMC queries, prefer the record with a longer abstract snippet. Then **exclude any candidate whose canonical URL is in `seen_urls`** from Step 2.5.a.

Cap the final list at **25 candidates**, preserving order: Europe PMC tongue-swab first, then ClinicalTrials.gov, then Europe PMC TB MDx, then Europe PMC drug resistance, then WebSearch results. This ordering biases Step 3 toward the strongest signal first; the rubric still owns final selection.

Pass the final list into Step 3's `## News candidates:` placeholder. Each candidate carries the fields Step 3 expects (title, URL, source, snippet, date) plus the new `pubType` field — Step 3's curation rubric is unchanged and will simply ignore `pubType` unless edited later to use it.

**If every API call in 2.5.b fails:** proceed with WebSearch results only.
**If WebSearch fails too and the final candidate list is empty:** still proceed to Step 3 — its rubric already handles the empty case ("No notable news this period").

**Do NOT call WebFetch to read full article contents.** The Europe PMC `abstractText` and ClinicalTrials.gov `briefSummary` snippets are sufficient for Step 3 to evaluate relevance.

## Step 3: Compose the morning brief using Opus

Use the **Task tool** with `subagent_type: "general-purpose"` and `model: "claude-opus-4-8"` to write the brief. Pass all verbatim extracts from Step 1 and all email summaries from Step 2 in the agent prompt. Use this prompt template (fill in the bracketed sections):


You are writing a morning brief for Kyle Hallock, Product Manager of the NusaDx project (formerly "Stampede").

Today's date: [use the current date from your session environment — do not guess]

Collected journal extracts:

[Paste all verbatim extracts from Step 1, labeled by doc name and date]

Document activity log:

[Paste the activity log from Step 1. For each of the 5 documents, list: short doc name, author(s), and date(s) of recent entries. If no recent entries, say "No recent updates (last entry: [date])"]

Email context:

[Paste summaries of emails read in Step 2]

News candidates:

[Paste the deduplicated list of candidate articles from Step 2.5. For each: title, URL, source domain, snippet, approximate date]

Project context:

[Paste the full "Project Context" section from the skill body verbatim]

Instructions:

Write the morning brief below. Be direct — no filler, no hedging. Every bullet must be a concrete fact, decision, or action. Omit any section with no content. 3-5 bullets per section max. Weave email context into the relevant sections naturally — no separate email section. If journals couldn't be fetched, note this at the top before the executive summary.

News curation instructions:

From the news candidates list, select 3-5 articles for the 🌐 NEWS section. Apply these rules strictly:

Hard reject (do not include):
- AI-generated aggregator sites or content farms
- Paywalled articles with no useful abstract or summary in the snippet
- Duplicate coverage of the same story — keep only the original/primary source
- Irrelevant articles that don't match the topic areas below

Relevance scoring (prioritize in this order):
1. Oral/tongue swab TB diagnostics — most directly relevant to NusaDx
2. TB diagnostics products — new devices, clinical trial results, head-to-head comparisons (GeneXpert, Truenat, TB-LAMP, etc.)
3. TB policy & regulatory — WHO guidelines, regulatory changes in Indonesia and other high-burden countries, StopTB/MSF/FIND announcements
4. MDx market & business — acquisitions, funding, partnerships in molecular diagnostics (Cepheid/Danaher, Hologic, Abbott, Roche, etc.)

Output: Include 3-5 articles. If fewer than 3 pass quality filtering, include only what passes — do not pad with low-quality articles. If nothing qualifies, show "No notable news this period." For each article, provide: linked headline, source name, publication date, and a 1-sentence summary of why it matters to the NusaDx team.

FORMAT:
📊 EXECUTIVE SUMMARY — 2-3 sentences: what happened recently, what matters most today
📋 STATUS — Key metrics: sample counts, study progress, approaching deadlines
🔬 PROGRESS — What moved forward recently
🚨 BLOCKERS & RISKS — What's stuck or needs attention
✅ ACTION ITEMS — What needs Kyle's decision or follow-up
🌐 NEWS — 3-5 curated articles from the past month. Each item: linked headline, source name, publication date, and a 1-sentence summary of why it matters to the NusaDx team. Hard-reject AI aggregator sites, paywalled articles, and secondary rewrites. If fewer than 3 quality articles are found, show only what qualifies.
📄 JOURNAL ACTIVITY (footnote) — A single compact line at the bottom of the brief, just above the footer. Format: "Journals active today: [Doc] ([Editor(s)]). Others last updated: [Doc] ~[Date] · [Doc] [Date] · …" If all journals were inactive, list all with their last-seen dates: "No journals updated today. Last seen: [Doc] [Date] · …"

Return ONLY the brief body as clean HTML with:
- Outer wrapper: a single <div> with width: 100% and no max-width constraint
- font-family: Arial, sans-serif; font-size: 14px for body text
- Section headers: <h2> tags, font-size: 20px, bold, with the emoji symbol preceding the section name, and a light bottom border (border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 28px). The emoji and text should be on the same line.
- Journal activity footnote: a single <p> tag with font-size: 12px, color: #9ca3af, font-style: italic, margin-top: 24px, margin-bottom: 4px. No table, no section header — inline prose only.
- Bullets as <ul>/<li> lists
- News section: each article as a <div> with border-bottom: 1px solid #f3f4f6, margin-bottom: 14px, padding-bottom: 14px. Headline as a blue <a> link (color: #1e40af, font-weight: 600, font-size: 14px, text-decoration: none). Source name and date on a second line (font-size: 12px, color: #9ca3af). Why-it-matters summary on a third line (font-size: 13px, color: #374151).
- Footer div: "Generated by Claude Cowork" in small gray text
Do not include <html>, <head>, or <body> tags — return only the inner body content.

Important: Generate the HTML entirely from the context provided above — do not call any tools (no WebFetch, no Search, no file reads). Return only the HTML string.


Take the HTML string returned by the agent and use it as the `htmlBody` for the Gmail draft in Step 4.

## Step 4: Create Gmail draft

Use the Gmail draft creation tool to create a draft with:
- **`to`:** `["kyle.hallock@formulatrix.com"]`
- **`subject`:** `Morning Brief — [today's date formatted as: weekday, month day, year]`. Use the current date from your session environment (shown in your system prompt) — do not infer or guess the date. Double-check that the weekday matches the calendar date before writing the subject.
- **`htmlBody`:** The HTML returned by the Opus agent in Step 3.

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

END SUBAGENT PROMPT

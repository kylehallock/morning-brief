# Stampede Project Context

## Project Overview

**Stampede** is a 4-year R&D project (2022–2026) building a low-cost, point-of-care tuberculosis (TB) diagnostic device for Indonesia and other high-burden countries. The device is a compact, 5-channel qPCR instrument that detects TB DNA from **tongue swab samples** — a major differentiator from existing tests that require sputum, which is difficult to collect from children and immunocompromised patients.

The core workflow: a patient's tongue swab is loaded into a disposable cartridge, the device sonicates the sample to release DNA, then runs real-time PCR with fluorescence detection to identify TB targets (IS6110, IS1081) and drug resistance markers (rpoB, katG). The instrument price target is ~$2K (V2 BOM ~$800), with a consumable cartridge target below $2/test BOM using in-house fTaq mastermix (~$3/test with commercial DsBio mastermix), translating to roughly $8/test on the market.

The team pivoted fully to tongue swab collection in June 2025, abandoning sputum-based testing. Early comparison testing with GeneXpert showed promising agreement, and the project is now in its most critical phase — large-scale clinical validation studies in 2026 that will determine whether the product is truly feasible.

## Current Phase & Goals

The project is in **Phase 6: Clinical Validation** (H1 2026, January–June). This is the make-or-break phase — the team needs to prove clinical performance on real patient samples.

**Key goals this half (170 total points):**

- **Clinical Verification Study at RSPAW** (50 pts, deadline: Feb 28) — Agreement with RSPAW to test 100 samples total. 40 research samples, then 20 graded for performance (10 TB+, 10 TB-) compared against Xpert Ultra sputum. Must achieve >70% sensitivity, >90% specificity, <10% abort rate. RIF resistance assays must be tested but aren't scored. *(Reduced from 80 research samples on 1/22; max score now 45 pts.)*
- **R2D2 Performance Study** (50 pts, deadline: Mar 31) — Run 100 R2D2 clinical samples on V2 instrument. Must hit >75% sensitivity, >90% specificity, <5% abort rate. Pass/fail, no partial credit. **Currently blocked** by shipping logistics.
- **DST Viability** (50 pts, deadline: May 31) — Can we detect rifampicin and isoniazid resistance in tongue swabs? Test 50 TB+ R2D2 samples (25 RIF-resistant, 25 INH-resistant). Full credit for completing all 50 tests regardless of results.
- **V3 Validation** (10 pts, deadline: May 31) — Build V3 device and run 10 tongue swabs at RSPAW (5+, 5-). Full credit if 9/10 or 10/10 agreement with Xpert Ultra.
- **Regulatory Officer Plan** (10 pts, deadline: Apr 30) — Rafael to define the full regulatory roadmap (ISO 13485, ISO 14971, IEC 62304, TKDN, Izin Edar, CPB, CDAKB) with timeline, priorities, and costs.

The **polymerase decision** is a key strategic fork: DsBio HS (commercial, proven, ~$3/test) vs. fTaq (in-house, cheaper, still being optimized).

## Team Structure

**Leadership:**
- **Jeremy** — CEO. Executive sponsor of Stampede.
- **Mike Nilsson** — Associate Director of Engineering (reports to Heinz Kochling, Director of Worldwide Engineering).
- **Kyle** — Product Manager for Stampede. Reports to Mike.
- **Sean** — Director-level leader of the entire Indonesia science team. Reports to Heinz, effectively to Jeremy.
- **Kabir** — Senior mechanical engineer. One of the company's first employees; high autonomy.

**Indonesia — Product Management:**
- **Ibeng (Muhamad Iqbal)** — Kyle's Product Manager Deputy (PMD). Kyle's eyes and ears on the ground.

**Indonesia — Science Team (under Sean):**
- **Yosi** — Science team lead. Manages lab scientists.
- **Fadhil** — Peer to Yosi, manages different science tasks (outreach, regulatory coordination, ISO 35001). Less hands-on lab work.
- **Adit (Aditya), Kukuh, Bila (Salsabila), Janavi, Ode, Diah** — Lab scientists under Yosi. Diah specializes in BSL-2 lab operations.

**Indonesia — Mechanical Engineering (under Djoko):**
- **Djoko** — Director of Mechanical Engineering in Indonesia. Reports to Heinz.
- **Lulus** — Senior ME, leads junior engineers. Reports to Ibeng.
- **Bowo (Kurnia Wibowo)** — System integration lead. Handles all instrument troubleshooting.
- **Dika (Adika Utama), Altius, Seno, Bayu, Munis** — Junior mechanical engineers under Lulus.
- **Dedy, Dwi** — Senior injection molding engineers. **Tohir** assists Dedy.

**Indonesia — Electrical & Firmware:**
- **Afendy** — Manager of Electrical Engineering. Reports to Rasmus Lindblom.
- **Amry** — Main electrical engineer. **Novi (Siti Nopiyanti)** assists.
- **Azwar** — Firmware engineer.

**Indonesia — Software:**
- **Wawan (Daud Gunawan)** — Senior SW developer. Reports to Deni Setiawan → Lizzie (Elizabeth Edwards).
- **Desy, Wimbo** — Technical writers. **Grerry** — Junior SWE. **Gideon** — Head of UI/UX. **Karel** — Junior UI developer.

**Indonesia — Regulatory:**
- **Rafael** — Regulatory leader. Reports directly to Kyle.

**Indonesia — Production:**
- **Tian (Christian Adi Nugroho)** — Production team leader. Reports to Ferry Hariadi (General Manager of Indonesia sites → Jeremy).

**Key External Partners:**
- **FIND** — Clinical trial support and WHO prequalification pathway.
- **R2D2** — Source of clinical TB samples (biobank).
- **RSPAW** — Hospital clinical trial site (Lung Hospital).
- **BRIN** — Indonesian National Research Agency; influence with MoH and WHO.
- **Forindo** — Manufacturing partner.
- **Prof. Bhacti / UNPAD** — University partner; team shaped national TB testing policy. Connected to MoH.

## Key Terminology & Acronyms

**Diagnostic / Molecular Biology:**
- **qPCR** — Quantitative PCR; real-time DNA amplification and detection.
- **Ct (Cq)** — Cycle threshold; PCR cycle where fluorescence exceeds background. Lower Ct = more target DNA.
- **IS6110, IS1081** — Multi-copy TB DNA targets (primary detection).
- **rpoB (LNA-P3), katG, FabG** — Gene targets for rifampicin and isoniazid drug resistance.
- **LOD** — Limit of detection. **FAM, ROX** — Fluorescent dyes. **NTC** — No Template Control.
- **DST** — Drug Susceptibility Testing. **MSM** — Mycobacterium smegmatis (non-pathogenic test bacterium).
- **Xpert Ultra (GeneXpert)** — Cepheid's gold-standard TB diagnostic (reference comparator).
- **Tongue swab (TS)** — Our sample collection method.

**Chemistry / Reagents:**
- **DsBio HS** — Commercial hot-start polymerase. Proven, ~$3/test.
- **fTaq** — In-house polymerase. Cheaper, still being optimized.
- **Master mix** — Reagent cocktail (polymerase, primers, probes, buffer) loaded into the cartridge.
- **EvaGreen** — Intercalating dye used to detect non-specific amplification during troubleshooting.

**Device & Hardware:**
- **V2, V3** — Device generations. V2 is current; V3 is cost-reduced.
- **TS-003, TS-005, TS-006** — Individual V2 instrument serial numbers.
- **Cartridge / chip** — Disposable consumable. **Ch 0–Ch 4** — The 5 channels on each chip.
- **Abort** — A failed run due to hardware issues. Abort rate is a key clinical metric.
- **Full sequence** — Complete device workflow: sonication → heat lysis → PCR.
- **QS6** — QuantStudio 6, a benchtop qPCR reference instrument for baseline comparisons.
- **DAT** — Device Acceptance Test; formal document defining a goal's testing procedure and scoring.

**Regulatory:**
- **NIE AKD** — Indonesian medical device registration. **CPB (formerly CPAKB)** — Manufacturing permit.
- **CDAKB** — Distribution permit. **TKDN** — Local content requirements. **Izin Edar** — Market authorization.
- **ISO 13485** — Medical device QMS. **ISO 35001** — Biosafety lab standard. **IEC 62304** — Software lifecycle.

## Recent Milestones & Decisions

- **June 2025** — Strategic pivot: abandoned sputum testing entirely, full commitment to tongue swab.
- **Aug 2025** — Reproducibility DAT passed (30 runs, max 1.04 stdev).
- **Oct 2025** — 4 working V2 instruments built. RSPAW agreement signed for 110-sample study.
- **Late Jan 2026** — fTaq V6 breakthrough: preheat to 95°C eliminates primer dimers, dramatically improves sensitivity.
- **Early Feb 2026** — DsBio HS reproducibility confirmed across 4 devices (0.21 Ct stdev, zero contamination). R2D2 import approved by MoH, but shipping logistics still unresolved (dry ice courier issues).
- **Feb 2026** — RSPAW sample collection at 86/110. Research testing underway at the Lung Hospital. DAT testing of 20 graded samples planned for Feb 25 and 27.
- **Feb 20, 2026** — BRIN agreed to audience meeting, will invite MoH, WHO, and University of Indonesia.
- **Ongoing** — Experiment priority shifted to drug resistance marker detection. KatG and FabG showing initial success, but rpoB (LNA-P3) assay sensitivity is the biggest technical challenge.

## Current Blockers & Risks

- **rpoB assay sensitivity** — The biggest technical risk. Rifampicin resistance detection (LNA-P3) shows weak curves even with medium-positive tongue swab samples. Team is investigating non-specific amplification, TS matrix inhibition, and primer optimization.
- **Hardware abort rate (~20%)** — Multiple failure modes: latex seal leaks, silicone flashing clogs, over-sensitive safety features. Clinical targets: <10% (RSPAW), <5% (R2D2).
- **R2D2 sample shipping** — Import letter issued, but dry ice courier logistics unresolved. Blocks R2D2 performance study (50 pts) and DST viability (50 pts).
- **Polymerase decision** — fTaq cheaper but less proven. Head-to-head comparison ongoing during RSPAW research testing.
- **Ramadan impact** — Shorter hospital hours may slow remaining sample collection.
- **RSPAW DAT deadline** — 20 graded samples must be tested by Feb 28. Testing this week (Feb 25, 27).

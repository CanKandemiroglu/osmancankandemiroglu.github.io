# PhD funding search — marine biogeochemistry and adjacent fields (retrieved 2026-09-07)

Eligibility-first survey of fully funded PhD scholarships, studentships and salaried positions for one candidate: German citizen, M.Sc. Marine Geosciences (Bremen, defended 23 March 2026), earlier M.Sc. Geosciences (Bochum, 2011), doctoral enrolment at Bochum 2016–2018 ended without a degree, English C1 (UNIcert III), German C1 (TestDaF), no IELTS/TOEFL. PhD only.

**Do not merge this folder into `main` without deciding whether it should be public.** This repository is served as osmancankandemiroglu.com; anything merged is published.

## Files

| File | Content |
|---|---|
| `output1_eligible_programmes.csv` | 94 rows: every programme he can apply to (ELIGIBLE / CONDITIONAL / UNCLEAR), with citizenship and prior-doctoral-enrolment clauses quoted verbatim, money actually covered and not covered, duration, deadline, portable vs tied, field fit (1 marine biogeochemistry · 2 organic geochemistry/biomarkers/CSIA · 3 marine microbiology/geomicrobiology · 4 marine geosciences/palaeoceanography · 5 astrobiology biosignature analytics), retrieval date. Every row is labelled SCHOLARSHIP / STUDENTSHIP / EMPLOYMENT. |
| `output2_deadline_calendar.csv` | 74 rows, sorted by date over the next 12 months: deadline, what must be in place before it (supervisor, admission, references, language test, proposal) and the lead time that moves the real deadline earlier. Rows with an empty `sort_date` are rolling or not yet published. |
| `output3_ineligible_programmes.csv` | 48 rows: programmes he cannot apply to (or that no longer exist), with the disqualifying clause quoted verbatim and its URL. |
| `output4_structural_notes_and_language.md` | (a) how PhD funding actually works in each of the seven regions, with income figures and tax status sourced; (b) the language-certificate question, university by university, with test costs and lead times. |
| `sources/` | The raw regional research notes behind the CSVs: every URL opened, every URL that could not be opened (HTTP 403/404/405/503, bot blocks), and longer verbatim extracts. |

## Rules applied
- Every URL in the CSVs was opened on 2026-09-07 (directly, or through a text-reader proxy where the host blocks automated fetches; the canonical URL is cited). No URL was constructed or guessed. "Not verified" means no page carrying the fact could be opened.
- Citizenship and prior-enrolment clauses are quoted, not paraphrased. Where two sources disagree, both are given.
- "Fully funded" was tested: fee-waiver-only schemes and stipend-only schemes are marked as not fully funded.
- Programmes whose next round is not yet announced carry the previous cycle's date marked "(previous cycle, indicative)".

## Headline findings
1. **Prior doctoral enrolment (Bochum 2016–18, no degree) is not a formal exclusion anywhere verified.** Every clause found turns on *holding* a doctorate or on time since the *last degree* or on progress in the *current* project. Genuine ambiguities to settle in writing: DAAD research grant ("Beginn des Promotionsstudiums ... nicht länger als drei Jahre"), FWO Belgium (18-month seniority cap, 3-year post-master's cap), CGRS D Canada (36-month cap "whether or not ... at the same institution"), Auckland (apply as new applicant, not transfer), Edinburgh Doctoral College ("first year of study"). Disclose it everywhere; several forms require transcripts for incomplete degrees.
2. **Citizenship kills the US and (old) Canadian federal fellowships** (NSF GRFP, Hertz, DOE CSGF, ARCS, NOAA Foster, NDSEG, AMS, Sea Grant, SMART). Vanier and NSERC PGS-D/CGS-D no longer exist; the successor CGRS D admits internationals only after registration in Canada (15 % quota). Commonwealth, Marshall and Rhodes (age) are closed.
3. **Age is a bar only at Hans-Böckler (40) and Rhodes.** KAS and HSS no longer publish age limits in their 2025 Richtlinien; Villigst explicitly admits over-35s with a written justification.
4. **DBU forbids re-application after a rejection** ("Die Ablehnung eines Stipendienantrags schließt eine erneute Bewerbung aus") — excluded.
5. **The single gating action is IELTS Academic 7.0/6.5** for every UK, US, Canadian, Australian and NZ application; UNIcert III is accepted only by the University of Bremen (hence MarMic). Caltech needs no English test but requires the GRE; URI accepts a CEFR B2 certificate (confirm UNIcert III in writing).
6. **Nearest hard deadlines:** UTAS/IMAS 1 Oct 2026; Studienstiftung call 1–14 Oct 2026; FNS 1–31 Oct 2026; NZ rounds 15 Oct – 1 Nov 2026; MIT–WHOI/UW/Scripps 1–2 Dec 2026; PBEEE pre-selection Sep–Nov 2026; Cambridge 8 Dec 2026; NERC DLAs 5–8 Jan 2027; KAS/HSS 15 Jan 2027; UBC 15 Jan 2027; MarMic 28 Feb 2027.

## Gaps left open (could not be verified)
- IMPRS MarMic: funding wording on its own site says "approximately 1400-1500 Euro per month" — likely stale; confirm the contract type.
- GEOMAR ISOS (no page found); DFG GEPRIS GRK list (JavaScript only); ETH Zurich doctoral rates (image table); Spain's national FPI call (AEI site 503); Research Ireland 2027 call status; UNSW Scientia PhD (404); CSIRO Industry PhD (404); WA-OIGC Curtin (domain does not resolve); GNS Science (bot-blocked); UEA, Bangor, Newcastle, Oxford Earth Sciences, Cardiff, QUB (bot-blocked or not located); Otago figures read via a proxy; Vanier's own site (503).
- Contact address: osmancankandemiroglu@proton.me

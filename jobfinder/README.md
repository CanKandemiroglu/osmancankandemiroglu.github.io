# jobfinder

Local finder for marine-science PhD positions. One `python run.py` per morning; read `out/queue.md`
on the phone, `out/positions.md` for everything open, `out/dashboard.html` on the laptop.
It only finds. It never applies, sends, or submits anything.

## Setup

```
cd jobfinder
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp jobfinder.example.toml jobfinder.toml           # optional; edit contact_email, keywords, sync branch
cp /path/to/profile.md profile.md                  # REQUIRED. The app only reads it.
python run.py
```

`profile.md` is the only source of facts about the candidate. Section ids drive everything
(`core/profile.py` docstring): §3a = own hands, §3b = taught, §3c = excluded, §4 = gate facts
(`highest_degree`, `work_authorization`, optional `wisszeitvg_remaining_months`), §7 = banned strings.
The run refuses to start without it. `tests/fixtures/profile_fixture.md` is invented test data.

## Daily run, in order

1. `registry/sources.csv` → `sources` table (the CSV is the truth; a source is fetched only if
   `active=1`, has an `http(s)` URL, `platform` has an adapter, and `robots_allows` is not `never`).
2. Stage 1: each adapter lists title / institution / deadline / URL. robots.txt is checked per host
   and cached 7 days; hosts with `robots_allows=never` are refused before any request.
   ≥ 2 s between requests to one host, one request per host at a time, every request logged
   (`logs/fetch.log` and the `fetch_log` table: host, status, bytes, elapsed).
3. Gates (§4): WissZeitVG entitlement, visa, PhD-required. FAIL → NO-GO, never scored.
   UNKNOWN → scored but flagged `GATE?` and never GO.
4. Keyword pre-filter (config `keywords`, search terms only) → Stage 2 full-text fetch for
   survivors only (cap `stage2_max`).
5. Scorer: keyword/rule (default) or `--scorer api` (Anthropic, one call per ad, prints the call
   count and waits for `YES`; `--confirm-api` skips the prompt). Output is a gap list, never a %.
6. Render `out/queue.md`, `out/positions.md`, `out/dashboard.html`.
7. `tools/verify_output.py` (pytest): no §7 string in any output, no API-key-looking string in
   anything staged. A hit fails the run before the commit.
8. Sync: `git add out/ registry/sources.csv jobfinder.db`, commit `run YYYY-MM-DD: n new, m open,
   k expired`, push. Unchanged tree → no commit. Failed push → logged, exit 0.

Flags: `--no-sync`, `--no-fetch` (re-score/re-render only), `--only id1,id2`, `--rescore`,
`--profile PATH`, `--today YYYY-MM-DD`.

## Adding the 218-row registry

Drop the rows into `registry/sources.csv` (same columns). Set `platform` to a name in
`adapters/__init__.py`. Unknown structure → `manual` (shown as a link). Never invent a URL: leave
`url` empty, `active=0`, and write the reason in `block_reason`.

## Adapters

| platform | status |
|---|---|
| peopleadmin, unige_wdportal, euraxess, kuleuven, csic_sede, rss, wordpress | verified on live pages 2026-09-07; fixtures in `tests/fixtures/` |
| szn_joomla | URL confirmed, structure not verifiable from the build sandbox → stub |
| workday, jobbnorge, successfactors, varbi, cnrs, pageup, reachmee, oracle_hcm, uc_recruit, taleo, emply, valtiolle, starfatorg | stubs, endpoints under separate research |
| manual | link only |

Schema: as specified, plus two bookkeeping columns on `postings` (`country`, `detail_fetched`)
and two tables (`robots_cache`, `fetch_log`).

## Tests

`python -m pytest -q tests tools/verify_output.py` (the second needs `JOBFINDER_PROFILE` or `profile.md`).

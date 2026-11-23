# NBA Live — historical season archive

The live NBA app is intentionally unchanged. Archiving runs on GitHub Actions and
stores its results on the **`nba-season-data` branch**, which is **not deployed to
GitHub Pages**. Visiting `nba-live/` does not download the season database.

## What gets saved

- `2026-27/season.sqlite` — **SQLite** (fast indexed lookups; no text scanning):
  - `games` — completed games and official final scores.
  - `team_games` — full-game team info and native ESPN team stats.
  - `team_periods` — each team's Q1–Q4, and overtime if played, including points,
    shots, rebounds, assists, turnovers, steals, blocks and fouls.
  - `player_games` — game box scores from ESPN.
  - `player_periods` — reconstructed per-player period statistics.
  - `scanned_dates` and `pending_games` — checkpointing and retries.
- `2026-27/raw/scoreboards/YYYYMMDD.json.gz` — original ESPN scoreboard responses.
- `2026-27/raw/games/GAME_ID.json.gz` — original ESPN game summaries, including
  play-by-play and box scores. These compressed files allow future reprocessing.
- `2026-27/manifest.json` — update timestamp, record counts, and pending games.
- `2026-27/validation.json` — full-season reconciliation report and per-metric disagreements with ESPN box scores.
- `stat_validations` table — per-team/player game box-score comparisons, queryable by metric and mismatch status.

**Data caveat:** Only final scores and per-quarter points (when ESPN linescores are
available) are taken from ESPN's published numbers. Per-quarter rebounds, FGs,
3PTs, FTs, fouls and player statistics are reconstructed from play-by-play.
Replayed values are tagged `quality='reconciled'` only when their *full-game*
aggregates match ESPN's published box scores for available metrics, or
`quality='mismatch'` when not. Even `reconciled` **does not prove** each
quarter's events are complete or correctly attributed. If ESPN omits a period's play-by-play, its derived values are `NULL`,
not zero. Raw data is kept so the parser can improve later without losing games.

## Automatic operation

The `Archive NBA 2026-27 Season` workflow runs twice a day and can also be
started via **Actions → Archive NBA 2026-27 Season → Run workflow**.
On its first run, it scans **October 20, 2026 onward**; after that it checks
only unscanned dates, the last four days, and pending failed games. It saves
completed regular-season games only (no future/preseason games), and skips
games already archived with available play-by-play. Thus the first run
backfills the season, and subsequent runs extend the archive without refetching
every game.

Partial failures do not destroy successful work: the workflow commits all
successful data, reports an error, and retries pending games next time.
The script requires only **Python 3.12 standard-library modules**.
No API key, server, cloud database, third-party Python package, or browser data
load is needed.

### Run locally

```bash
python -m unittest discover -s nba-live/archive -v
python nba-live/archive/collect.py --data-dir /path/to/separate/data-checkout
python nba-live/archive/reprocess.py --data-dir /path/to/separate/data-checkout
```

Pass `--force` to re-fetch/rebuild every game or `--today YYYY-MM-DD` for a
historical cutoff. `--max-games 20` is available for a deliberately small batch.
Keep `--force` off during normal ingestion; use it only to reprocess if the
reconstruction logic is corrected.

### Example SQLite query

```sql
SELECT round(avg(reb), 2) AS atl_q4_rebound_average, count(*) AS games
FROM team_periods
WHERE abbr = 'ATL' AND period = 4 AND reb IS NOT NULL;
```

Note that a season-wide query like this should exclude games whose derived
rebounds are incomplete or inaccurate. Review `2026-27/validation.json` and filter
`quality='reconciled'` for more trustworthy comparisons. This means all *available*
full-game checks passed; it is **not a guarantee** that a particular quarter is error-free. Before publishing an
analytical Explorer, validate the quarter splits against a trustworthy source.

## Scope and performance

- SQLite stores the structured statistics compactly and answers filtered
  questions through indexes. The compressed originals are *backup inputs*,
  not scanned for each query.
- GitHub Pages publishes the `main` branch, so separate `nba-season-data`
  branch commits do **not** trigger site redeploys or increase download size.
- Since ESPN's data source is unofficial, collection may sometimes fail;
  GitHub Actions logs and the archive manifest expose failures. Respect the
  provider's access policies and rate limits.

## Validation and historical recalculation

The new offline replay takes every saved `raw/games/*.json.gz` and computes
period stats again with the same structured ESPN shot values and primary/
secondary participant IDs used by NBA Live. It **does not request the entire
season from ESPN again**, and does not modify official final scores or original
compressed source files. It compares each game's reconstructed team and player
totals against ESPN's own final box score, storing per-stat matches/mismatches
in `stat_validations` and a searchable `validation.json` report. The process
runs automatically after each regular archive update. A 450-play real ESPN
fixture tests complete team and player reconciliation before any archive
write. Mismatches remain visible rather than silently repaired or hidden.

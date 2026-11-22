# NBA Recap — web-tools edition

A no-framework, no-build, mobile-first NBA scoreboard for GitHub Pages.

## What it does

- Opens a static Gruvbox HTML page immediately; shows a saved on-device snapshot if present.
- Displays **every final game with a tipoff in the rolling last 48 hours**, newest first. The list stays fast by rendering player tables only when a game is expanded.
- Tap a game to reveal **ESPN's complete game box score plus anyone missing from each team's current ESPN roster** (with DNP where appropriate), on both teams. Stats: MIN, PTS, REB, AST, +/−, STL, BLK, TO, FG, 2PT, 3PT, FT and calculated shooting percentages.
- East and West conference W-L standings, explicitly ranked best-to-worst by winning percentage.
- Entire interface scrolls vertically only; touch targets are large and navigation stays fixed at the bottom.
- Does **not** fetch ESPN directly from the phone. A scheduled workflow prepares one compact JSON snapshot.

## Deploy into StefanBee/web-tools

1. Copy the `nba-recap/` folder and `.github/workflows/update-nba-recap.yml` from this package to the **root** of your existing [`web-tools`](https://github.com/StefanBee/web-tools) repository. Keep the folder hierarchy intact.
2. Commit/push to `main`. In **Repository → Settings → Pages**, select **Source: GitHub Actions** instead of "Deploy from a branch." This workflow deploys your **entire existing `web-tools` homepage and tools**, not only NBA Recap. Fresh ESPN JSON is generated inside the workflow and deployed directly (no automated commits).
3. Go to **Actions → Update NBA Recap → Run workflow** for the first real snapshot and publish (a push to `main` also triggers it). Your URL will be `https://stefanbee.github.io/web-tools/nba-recap/` **after** the deployment succeeds.
4. On iPhone: open the URL in Safari → Share → **Add to Home Screen**.

The workflow deploys a Pages artifact directly rather than committing updated JSON to `main`. This avoids failed pushes when several jobs run close together. GitHub Pages should be set to **GitHub Actions**, not branch publishing.

The homepage in `web-tools/index.html` automatically discovers folders with `meta.json`, so NBA Recap also shows up in your tools list.

### Why the folders are arranged this way

GitHub requires workflow files to be stored in the repository-level `.github/workflows/` directory. The NBA Recap-specific Python updater lives inside `nba-recap/scripts/`, alongside the app and its JSON data. The workflow calls that script by path. This keeps NBA Recap self-contained except for GitHub’s mandatory automation configuration.

## Performance design

- 0 libraries, 0 frameworks, 0 web fonts, 0 third-party images, 0 build steps.
- One HTML document + one compact JSON data request on load; repeated opens paint from `localStorage` immediately, then refresh the JSON.
- Only one compact JSON fetch on iPhone. The scheduled refresh collects all final games from the last 48 hours, loads box scores in parallel, and cross-checks ESPN team rosters and optional current injury reports.
- On GitHub Pages, CDN caching and Actions schedule delays mean data will **not** be literally real time. The update timestamp is always shown.
- GitHub Actions uses only Python standard library (no `pip install`) and deploys the full static site explicitly; each run publishes a fresh snapshot regardless of Pages branch-build triggers.
- If the box-score request fails, a previous complete box score for that game is retained; the app notes when a new game is missing box-score data.
- Players who are listed on a **current team roster**, but missing from the individual game box score, are shown as DNP / not in game box score. Current injury reports are labeled **current**, because they don't establish why someone missed a past game. ESPN roster information may omit players or change after trades; don't treat a DNP label as an official historical injury designation.

## Edit game cap / defaults

- Rolling window: `WINDOW_HOURS = 48` in `nba-recap/scripts/update_nba.py`.
- All scorecards render immediately, but detailed player grids are created only when a game is tapped.
- Update schedule: `.github/workflows/update-nba-recap.yml`.

## Data source / limitations

ESPN's **undocumented**, unaffiliated API:

- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=GAME_ID`
- `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`

ESPN may change schemas, throttle calls, or stop supplying certain fields. Shooting percentages are calculated from made/attempted values, **not independently verified**. 2PT derives from overall FG minus 3PT. A player's `+/-` can be missing even when other stats exist. "Every player" means every name present in ESPN's game box score; inactives omitted by ESPN may not be listed.

**Testing status:** The HTML/JS and Python parsing were tested locally with synthetic sample data; live ESPN HTTP fetches were **not** testable in this execution environment. Use **Run workflow** to validate against the current live API after copying to GitHub.

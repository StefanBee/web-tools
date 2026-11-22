# NBA Recap — web-tools edition

A no-framework, no-build, mobile-first NBA scoreboard for GitHub Pages.

## What it does

- Opens a static Gruvbox HTML page immediately; shows a saved on-device snapshot if present.
- Displays the previous **NBA Eastern Time** game day's 3 most recent completed games, with an option for 2 more (5 maximum).
- Tap a game to reveal **every player supplied by ESPN's box score, on both teams** (including DNP entries). Stats: MIN, PTS, REB, AST, +/−, STL, BLK, TO, FG, 2PT, 3PT, FT and calculated shooting percentages.
- East and West conference W-L standings.
- Entire interface scrolls vertically only; touch targets are large and tabs stay at the top.
- Does **not** fetch ESPN directly from the phone. A scheduled workflow prepares one compact JSON snapshot.

## Deploy into StefanBee/web-tools

1. Copy the `nba-recap/` folder, `scripts/update_nba.py`, and `.github/workflows/update-nba-recap.yml` from this package to the **root** of your existing [`web-tools`](https://github.com/StefanBee/web-tools) repository. Keep the folder hierarchy intact.
2. Commit/push to `main`. In **Repository → Settings → Pages**, select **Source: GitHub Actions** instead of "Deploy from a branch." This workflow deploys your **entire existing `web-tools` homepage and tools**, not only NBA Recap.
3. Go to **Actions → Update NBA Recap → Run workflow** for the first real snapshot and publish (a push to `main` also triggers it). Your URL will be `https://stefanbee.github.io/web-tools/nba-recap/` **after** the deployment succeeds.
4. On iPhone: open the URL in Safari → Share → **Add to Home Screen**.

**If the workflow cannot commit:** Repository → Settings → Actions → General → Workflow permissions → Read and write permissions. Some repository/org policies restrict this option. The workflow uses an explicit Pages artifact deployment because pushes made by `GITHUB_TOKEN` do not themselves trigger Pages builds. GitHub Pages should be set to **GitHub Actions**, not branch publishing.

The homepage in `web-tools/index.html` automatically discovers folders with `meta.json`, so NBA Recap also shows up in your tools list.

## Performance design

- 0 libraries, 0 frameworks, 0 web fonts, 0 third-party images, 0 build steps.
- One HTML document + one compact JSON data request on load; repeated opens paint from `localStorage` immediately, then refresh the JSON.
- Only 5 per-game ESPN requests per scheduled refresh (parallel) + 1 scoreboard + 1 standings; neither blocks the iPhone browser.
- On GitHub Pages, CDN caching and Actions schedule delays mean data will **not** be literally real time. The update timestamp is always shown.
- GitHub Actions uses only Python standard library (no `pip install`) and deploys the full static site explicitly; each run publishes a fresh snapshot regardless of Pages branch-build triggers.
- If the box-score request fails, a previous complete box score for that game is retained; the app notes when a new game is missing box-score data.

## Edit game cap / defaults

- Max downloaded box scores: `MAX_GAMES = 5` in `scripts/update_nba.py`.
- First three shown: `games.slice(0,showAll ? 5 : 3)` in `nba-recap/index.html`.
- Update schedule: `.github/workflows/update-nba-recap.yml`.

## Data source / limitations

ESPN's **undocumented**, unaffiliated API:

- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=GAME_ID`
- `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`

ESPN may change schemas, throttle calls, or stop supplying certain fields. Shooting percentages are calculated from made/attempted values, **not independently verified**. 2PT derives from overall FG minus 3PT. A player's `+/-` can be missing even when other stats exist. "Every player" means every name present in ESPN's game box score; inactives omitted by ESPN may not be listed.

**Testing status:** The HTML/JS and Python parsing were tested locally with synthetic sample data; live ESPN HTTP fetches were **not** testable in this execution environment. Use **Run workflow** to validate against the current live API after copying to GitHub.

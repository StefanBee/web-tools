# NBA Season Data

Archived NBA game data. Source: ESPN (unofficial API). Managed by
[archive-nba-season.yml](https://github.com/StefanBee/web-tools/blob/main/.github/workflows/archive-nba-season.yml).
This branch is deliberately separate from GitHub Pages and does not slow down NBA Live.

- `2026-27/season.sqlite`: indexed game, team-quarter, player-quarter and box-score tables
- `2026-27/manifest.json`: ingestion counts and last run
- `2026-27/raw/scoreboards/*.json.gz`: original ESPN daily scoreboard JSON
- `2026-27/raw/games/*.json.gz`: original ESPN game summaries, including plays

**Accuracy:** Period points use ESPN linescores. Other period statistics are **derived**
from ESPN play-by-play and can be incomplete/inaccurate. Raw inputs are retained for
reprocessing. `quality='no_play_by_play'` and SQL `NULL` mean unavailable, not zero.

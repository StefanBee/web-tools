# NBA Live

A dense, keyboard-first NBA box score optimized for a half-width desktop window (~960 × 1080 px on a 1080p display), with no build tools, external JavaScript libraries, or server.

## Start

Open `nba-live/index.html` from GitHub Pages at https://stefanbee.github.io/web-tools/nba-live/ .

The repository homepage discovers `nba-live/meta.json` automatically.

## Controls

| Input | Effect |
| --- | --- |
| `h` / `←`, `l` / `→` | Move one statistic left/right |
| `j` / `↓`, `k` / `↑` | Move a row down/up; crossing a table boundary continues in the next/previous table |
| `Tab` | Switch grid: Team Statistics → Away → Home → Team Statistics; scroll the table heading into view |
| `Shift+Tab` | Switch grids in reverse order with the same automatic scrolling |
| `gg` / `Home` | Jump to first row |
| `G` / `End` | Jump to last row |
| `s` | Sort by the selected column; press again to reverse |
| Click column header | Sort by that statistic |
| `Ctrl+K` or `/` | dmenu-style search: players, games, periods, commands |
| `Escape` | Close command menu or restore grid focus |
| `Enter` on a selected player | Open that player’s current-quarter stats inspector; `Esc` returns to the same cell |
| `Ctrl+K` → player → `Enter` → `Enter` | Jump straight to the player, then open their current-quarter inspector |

The active cell is outlined in yellow. The entire active row and column have subtle highlights, and the active cell follows its *player ID* when sorting reshuffles rows. Team statistics is navigable, just like both player tables. When entering Team Statistics, the page scrolls to the top. The player-name column stays visible when a player table is scrolled horizontally.


## Current-quarter player inspector and scoring runs

- The inspector is intentionally **not a permanent panel**. Find a player through Ctrl+K (or `/`), press Enter to jump directly to their row, then press Enter again for the quarter inspector. Or open the inspector with Enter from any selected player in their team table.
- It displays that player's **current game period** statistics: PTS, REB, AST, FG, 3PT, FT, STL, BLK and turnovers, as reconstructed from ESPN's play-by-play event descriptions and athlete IDs. OT1/OT2 use their own periods. It updates as the same summary feed is refreshed every 12 seconds; the full-game tables are unchanged. An unavailable quarter feed shows an explicit message instead of invented values.
- Player-specific **minutes and plus-minus are deliberately excluded**, since they cannot reliably be calculated just from event records. Event attribution can be imperfect, particularly for secondary assists, steals and blocks. Treat these live splits as a convenience, not an official verified stat ledger.
- A compact **unanswered scoring run** appears beside the score at **8–0 or more**, including the team and run duration in *elapsed game-clock time* since the run's first basket. Runs may cross quarters and overtime periods. A basket by the opponent ends the streak; incomplete scoring events suppress the indicator.
- Run duration is derived from the latest ESPN clock snapshot, so it advances on fresh data updates, not by guessing that the game clock is continuously running while play is stopped. The main box score is fetched at the same rate as before, with no additional API requests for either feature.

## Live data and performance

- Direct browser calls to ESPN's unofficial `site.api.espn.com` endpoints; there are no tokens or API keys.
- The game's player box score is requested every **12 seconds** while the page is visible.
- Game discovery is refreshed every **45 seconds**, with the previous, current and next NBA Eastern Time dates searched.
- Current player data is a full-game tally **including overtime**; selecting NOW/Q1/Q2/Q3/Q4/ALL changes the **team** statistics period. If a game reaches overtime, OT1, OT2, etc. are inserted automatically and can also be selected through the command palette.
- The game header indicates halftime, quarter breaks, and timeouts when they can be inferred from ESPN game status and play-by-play. It also shows **team charged timeouts used** (e.g., `DET 4/7`, `BOS 2/7`). Each team is allotted 7 charged timeouts in regulation and **2 per overtime period**; each OT has its own `0/2` starting count. The app counts team timeout events in the ESPN play-by-play rather than treating all broadcast/official timeouts as team timeouts. Incomplete or missing play-by-play displays `—` instead of assuming zero. These unofficial live counts can lag or differ from official data; they are not a validated authoritative timeout ledger.
- Quarter-specific FG, 3PT, FT, REB, TO and PF are calculated from ESPN play-by-play. The current box score is not reconstructed from the plays. Quarter splits may be temporarily incomplete during a game, and missing play data is shown as a dash rather than invented. Official quarter points are taken from line scores when available.
- Game rosters are checked once per selected game, allowing players absent from the box-score feed to appear as DNP. Roster information reflects ESPN's current roster and is not definitive historical game participation or injury information.
- No timers fetch in background tabs; the tab catches up when foregrounded.
- Only the selected game is polled, not every game.
- The script is embedded into one HTML file, and the JSON comes directly from ESPN (not GitHub Actions). Nothing here depends on the NBA Recap updater.

## Limits

ESPN's endpoints are undocumented and may change, become unavailable or refuse cross-origin requests in some browsers. This app currently relies on browser-to-ESPN access; **production live reliability has not been verified in a real browser during an active NBA game**. The UI shows a feed error and retries without fabricating statistics. Data is *near-live*, not an official synchronized low-latency feed. Google or the broadcaster may occasionally show events sooner.

`Ctrl+K` can be intercepted by some browsers or browser extensions, so `/` is the reliable alternative. Full-screen/OS-reserved shortcuts remain under browser control.

The app does not store personal data; localStorage is only used to remember the last selected game.

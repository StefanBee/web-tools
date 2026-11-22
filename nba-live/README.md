# NBA Live

A dense, keyboard-first NBA box score optimized for a half-width desktop window (~960 × 1080 px on a 1080p display), with no build tools, external JavaScript libraries, or server.

## Start

Open `nba-live/index.html` from GitHub Pages at https://stefanbee.github.io/web-tools/nba-live/ .

The repository homepage discovers `nba-live/meta.json` automatically.

## Controls

| Input | Effect |
| --- | --- |
| `h` / `←`, `l` / `→` | Move one statistic left/right |
| `j` / `↓`, `k` / `↑` | Move one player down/up |
| `Tab` | Switch grid: Team Statistics → Away → Home → Team Statistics |
| `Shift+Tab` | Switch grids in reverse order |
| `gg` / `Home` | Jump to first row |
| `G` / `End` | Jump to last row |
| `s` | Sort by the selected column; press again to reverse |
| Click column header | Sort by that statistic |
| `Ctrl+K` or `/` | dmenu-style search: players, games, periods, commands |
| `Escape` | Close command menu or restore grid focus |
| `Enter` on a player | Search / jump to that player |

The active cell is outlined in yellow. The entire active row and column have subtle highlights, and the active cell follows its *player ID* when sorting reshuffles rows. Team statistics is navigable, just like both player tables.

## Live data and performance

- Direct browser calls to ESPN's unofficial `site.api.espn.com` endpoints; there are no tokens or API keys.
- The game's player box score is requested every **12 seconds** while the page is visible.
- Game discovery is refreshed every **45 seconds**, with the previous, current and next NBA Eastern Time dates searched.
- Current player data is a full-game tally; selecting NOW/Q1/Q2/Q3/Q4/ALL changes the **team** statistics period.
- Quarter-specific FG, 3PT, FT, REB, TO and PF are calculated from ESPN play-by-play. The current box score is not reconstructed from the plays. Quarter splits may be temporarily incomplete during a game, and missing play data is shown as a dash rather than invented. Official quarter points are taken from line scores when available.
- Game rosters are checked once per selected game, allowing players absent from the box-score feed to appear as DNP. Roster information reflects ESPN's current roster and is not definitive historical game participation or injury information.
- No timers fetch in background tabs; the tab catches up when foregrounded.
- Only the selected game is polled, not every game.
- The script is embedded into one HTML file, and the JSON comes directly from ESPN (not GitHub Actions). Nothing here depends on the NBA Recap updater.

## Limits

ESPN's endpoints are undocumented and may change, become unavailable or refuse cross-origin requests in some browsers. This app currently relies on browser-to-ESPN access; **production live reliability has not been verified in a real browser during an active NBA game**. The UI shows a feed error and retries without fabricating statistics. Data is *near-live*, not an official synchronized low-latency feed. Google or the broadcaster may occasionally show events sooner.

`Ctrl+K` can be intercepted by some browsers or browser extensions, so `/` is the reliable alternative. Full-screen/OS-reserved shortcuts remain under browser control.

The app does not store personal data; localStorage is only used to remember the last selected game.

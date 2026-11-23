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
| `1`–`4` with Team Statistics active | Show Q1–Q4 team statistics (pins the selected quarter) |
| `5` with Team Statistics active | Show ALL full-game team statistics |
| `0` with Team Statistics active | Jump to the current quarter and resume following it on live updates |
| `o`, then `1`–`9` with Team Statistics active | Select OT1–OT9 if that overtime period is present (press within 1.2 seconds) |
| Click column header | Sort by that statistic |
| `Ctrl+K` or `/` | dmenu-style search: players, games, periods, commands. While open, `Tab` / `Shift+Tab` cycles results (wraps around); `Enter` selects |
| `Escape` | Close command menu or restore grid focus |
| `Enter` on a selected player | Open the player-quarter inspector on the current quarter; `1`–`4` switch to Q1–Q4; `o` then `1`–`9` selects OT1–OT9 (existing direct `5`+ OT keys also work); `Esc` closes |
| `Ctrl+K` → player → `Enter` → `Enter` | Jump straight to the player, then open their current-quarter inspector |

The active cell is outlined in yellow. The entire active row and column have subtle highlights, and the active cell follows its *player ID* when sorting reshuffles rows. Team statistics is navigable, just like both player tables. When entering Team Statistics, the page scrolls to the top. The player-name column stays visible when a player table is scrolled horizontally.



## Live on-court indicator

During an in-progress game, a yellow **`*`** appears immediately after a player's name when ESPN's starter list and substitution history establish that the player is among the current five on court. The lineup is recomputed from the existing 12-second ESPN summary feed; **there are no additional network requests**. The marker is hidden before tipoff, for final games and at detected breaks. If starters, play-by-play, or a substitution are missing or inconsistent, the affected team has no markers rather than showing a guessed lineup. ESPN's unofficial play feed may lag or miss lineup changes; these marks are best-effort, not authoritative live tracking.

## Current-quarter player inspector and scoring runs

- The inspector is intentionally **not a permanent panel**. Find a player through Ctrl+K (or `/`), press Enter to jump directly to their row, then press Enter again for the quarter inspector. Or open the inspector with Enter from any selected player in their team table.
- The popup **opens on the current game quarter**, then supports **Q1–Q4** using desktop **`1`, `2`, `3`, `4`** shortcuts or quarter buttons on desktop and phone. Overtime buttons appear when the game reaches OT; press `o` then `1` for OT1, `o` then `2` for OT2, etc. (or use existing direct `5`–`9` period keys). Until you manually select a quarter, the popup follows the live game; manual selection remains fixed across refreshes. Each quarter shows PTS, REB, AST, FG, 3PT, FT, STL, BLK and turnovers from ESPN's structured play events and athlete IDs. Updates use the existing 12-second ESPN feed, and missing quarter play data shows an explicit message rather than invented values.
- Player-specific **minutes and plus-minus are deliberately excluded**, since they cannot reliably be calculated just from event records. Event attribution can be imperfect, particularly for secondary assists, steals and blocks. Treat these live splits as a convenience, not an official verified stat ledger.
- A compact **unanswered scoring run** appears beside the score at **8–0 or more**, including the team and run duration in *elapsed game-clock time* since the run's first basket. Runs may cross quarters and overtime periods. A basket by the opponent ends the streak; incomplete scoring events suppress the indicator.
- Run duration is derived from the latest ESPN clock snapshot, so it advances on fresh data updates, not by guessing that the game clock is continuously running while play is stopped. The main box score is fetched at the same rate as before, with no additional API requests for either feature.

## Phone controls

The same page now adapts to a narrow phone screen without changing the desktop layout.

- A **persistent yellow search button** in the bottom-right opens the full command palette and focuses the search input so the phone keyboard appears. Search for a game, player, period or action; tap a result. The palette also has a visible close button.
- The **AWAY / HOME / BOTH** bar remains accessible while scrolling. Select one roster for a compact view or BOTH to keep the two full rosters visible.
- **Tap any number/stat cell** to highlight its row and column, including the yellow outlined active cell. The selection tracks the same player when live data refreshes or sorting changes.
- **Tap a statistic header** to sort; tap again to reverse. **Tap a player name** to open the quarter inspector, then tap Q1–Q4 to switch. The popup initially selects the current game quarter.
- **Swipe the tables horizontally** to access every statistic. Player names and team abbreviations stay pinned on the left; the table layouts use narrow phone-sized columns.
- All existing keyboard shortcuts are retained for desktop or a hardware keyboard.


## Schedule command

- The **`all`** command (alias **`all-q`**) in the palette switches Team Statistics to **ALL** (the whole game). It is placed first in results for quick selection; `q1`, `q2`, `current`, etc. still work.

- Open **`/`** (or **`Ctrl+K`**) and type **`schedule`**; press Enter or tap the result.
- The overlay starts on the **next future game**, showing local dates and tipoff times according to your phone/computer's timezone. Earlier games appear above the selection, with final scores.
- **`j` / ↓** moves to the next game, **`k` / ↑** to the previous game. On phones use **↑ Older** and **↓ Newer**, swipe vertically, or tap a game to highlight it.
- **Enter** / **View game** opens the selected game's box score. **Escape**, **Close**, or tapping outside the dialog dismisses it.
- Data is only fetched **when the schedule opens**, with seven-day chunks cached per browser session. Browsing past the loaded dates fetches more, and failed multi-day ESPN requests fall back to individual dates. An older game remains selected when the main daily refresh runs.

## Team statistics accuracy

- **ALL reads each team's own full-game FG, 3PT, FT, rebounds, turnovers, and fouls from ESPN's team box score**, not combined totals or a play-by-play reconstruction. **FG includes 2PT plus 3PT**, so a separate **2PT** column is derived as `FG − 3PT` (both makes and attempts). The same 2PT breakdown appears in Q1–Q4/OT, based on that team's play events. Shooting stats fall back to summed official player box-score rows only when team totals are unavailable.
- The **NOW button has been removed**. Team Statistics opens on the actual current quarter (e.g. Q3 during Q3, Q4 during Q4) and follows quarter changes during live play unless you select a different period.
- **`/ current`** jumps directly to that actual quarter and resumes automatic quarter-following. **`/ q3`** explicitly selects Q3 and stays there even if the game advances.
- **ALL** stays selected across all refreshes and shows continuously updated full-game ESPN box-score totals (on the existing 12-second polling cycle). It never switches to another quarter automatically.
- **Q1–Q4/OT 3PT, FG, FT, rebounds, turnovers, and fouls are summed from ESPN's structured shot values, team and player IDs, and typed play events by period.** Available quarter figures are displayed even when ESPN's game-total box score doesn't match the reconstruction. In that case, a **yellow ≈** marks the affected category as approximate. Missing period data still shows **—**. `ALL` continues using ESPN's full-game box score. Quarter counts are best-effort, not verified official period box scores.
- Quarter points continue using ESPN's published linescores when available, including correct zero-point quarters.
- Existing archived season quarter splits have not been recalculated by this change; those derived values still need validation before being used in historical analytics.


- The current-quarter player popup now uses these same structured play events: `pointsAttempted` differentiates FT/2PT/3PT even for misses, primary athlete IDs credit shots, rebounds and turnovers, and second participant IDs credit assists, steals and blocks. An `≈` on a popup stat means its reconstructed full-game total disagrees with the main ESPN player box score. No extra requests are made.
- Verified against a real 450-play ESPN fixture (TOR–ORL): all 12 team FG/3PT/FT/REB/TOV/PF values and 312 player box-score fields reconcile. The fixture is included as a test asset, not downloaded by the live page.

- **Checked BOS @ GSW (2026-11-22, game 401910035):** The saved final ESPN team totals, all player box scores summed by team, and the four reconstructed quarter totals independently agree: Boston FG 32–83, 3PT 14–47, 2PT 18–36, FT 9–12; Golden State FG 33–83, 3PT 14–45, 2PT 19–38, FT 8–10. Boston's earlier reported 32–82 was not present in the saved final feed; the live-feed discrepancy cannot be reconstructed from that final snapshot.

## Live data and performance

- Direct browser calls to ESPN's unofficial `site.api.espn.com` endpoints; there are no tokens or API keys.
- The game's player box score is requested every **12 seconds** while the page is visible.
- Game discovery is refreshed every **45 seconds**, with the previous, current and next NBA Eastern Time dates searched.
- Current player data is a full-game tally **including overtime**; selecting Q1/Q2/Q3/Q4/ALL changes the **team** statistics period. If a game reaches overtime, OT1, OT2, etc. are inserted automatically and can also be selected through the command palette.
- The game header indicates halftime, quarter breaks, and timeouts when they can be inferred from ESPN game status and play-by-play. It also shows **team charged timeouts used** (e.g., `DET 4/7`, `BOS 2/7`). Each team is allotted 7 charged timeouts in regulation and **2 per overtime period**; each OT has its own `0/2` starting count. The app counts **dedicated team timeout play types**, not every event whose description contains the word “timeout.” In particular, successful coach's challenges can say a team **retains its timeout**, and these challenge/review events are not counted as additional timeouts. Incomplete or missing play-by-play displays `—` instead of assuming zero. These unofficial live counts can lag or differ from official data; they are not a validated authoritative timeout ledger.
- Quarter-specific FG, 3PT, FT, REB, TO and PF are calculated from ESPN play-by-play. The current box score is not reconstructed from the plays. Quarter splits may be temporarily incomplete during a game, and missing play data is shown as a dash rather than invented. Official quarter points are taken from line scores when available.
- Game rosters are checked once per selected game, allowing players absent from the box-score feed to appear as DNP. Roster information reflects ESPN's current roster and is not definitive historical game participation or injury information.
- No timers fetch in background tabs; the tab catches up when foregrounded.
- Only the selected game is polled, not every game.
- The script is embedded into one HTML file, and the JSON comes directly from ESPN (not GitHub Actions). Nothing here depends on the NBA Recap updater.

## Limits

ESPN's endpoints are undocumented and may change, become unavailable or refuse cross-origin requests in some browsers. This app currently relies on browser-to-ESPN access; **production live reliability has not been verified in a real browser during an active NBA game**. The UI shows a feed error and retries without fabricating statistics. Data is *near-live*, not an official synchronized low-latency feed. Google or the broadcaster may occasionally show events sooner.

`Ctrl+K` can be intercepted by some browsers or browser extensions, so `/` is the reliable alternative. Full-screen/OS-reserved shortcuts remain under browser control.

The app does not store personal data; localStorage is only used to remember the last selected game.

#!/usr/bin/env python3
"""Build a tiny, dependency-free NBA snapshot for nba-recap on GitHub Pages.

Uses ESPN's unofficial public endpoints. Run with Python 3.11+.
Do not include example scores: a failed fetch preserves previously published data.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "nba-recap" / "data" / "latest.json"
API = "https://site.api.espn.com/apis/"
HEADERS = {"User-Agent": "NBA-Recap/1.0 (+GitHub-Pages-personal-project)", "Accept": "application/json"}
NY = ZoneInfo("America/New_York")
WINDOW_HOURS = 48


def get_json(url: str) -> dict:
    error = None
    for attempt in range(3):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=16) as res:
                return json.load(res)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"Could not fetch {url}: {error}")


def load_previous() -> dict:
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def simple_team(row: dict) -> dict:
    team = row.get("team") or {}
    return {
        "id": str(team.get("id", "")),
        "name": str(team.get("name") or team.get("shortDisplayName") or team.get("displayName") or "Team"),
        "abbr": str(team.get("abbreviation") or "NBA"),
        "score": str(row.get("score", "0")),
    }


def final_games_for_date(day: str) -> list[dict]:
    response = get_json(f"{API}site/v2/sports/basketball/nba/scoreboard?dates={day}")
    finals = []
    for event in response.get("events") or []:
        status = (event.get("status") or {}).get("type") or {}
        if not (status.get("completed") is True or status.get("name") == "STATUS_FINAL"):
            continue
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        lookup = {r.get("homeAway"): r for r in competitors}
        if not lookup.get("home") or not lookup.get("away"):
            continue
        stamp = event.get("date") or competition.get("date") or ""
        try:
            tip = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(NY)
            time_label = tip.strftime("%-I:%M %p ET")
        except (ValueError, TypeError):
            time_label = ""
        finals.append({
            "id": str(event.get("id", "")),
            "stamp": stamp,
            "time": time_label,
            "home": simple_team(lookup["home"]),
            "away": simple_team(lookup["away"]),
        })
    finals.sort(key=lambda game: game["stamp"], reverse=True)
    return finals


def pick_recent_games(now: datetime) -> list[dict]:
    # Rolling 48-hour window, using actual UTC tipoff times instead of NBA dates.
    cutoff = now - timedelta(hours=WINDOW_HOURS)
    first = cutoff.astimezone(NY).date()
    last = now.astimezone(NY).date()
    days = [(first + timedelta(days=n)).strftime("%Y%m%d")
            for n in range((last - first).days + 1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        chunks = list(pool.map(final_games_for_date, days))
    recent = []
    for chunk in chunks:
        for game in chunk:
            try:
                tipoff = datetime.fromisoformat(game["stamp"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if cutoff <= tipoff <= now:
                recent.append(game)
    recent.sort(key=lambda game: game["stamp"], reverse=True)
    # No artificial 3- or 5-game limit: show every finished game in the window.
    return recent


def stat_for(stats: dict, *keys: str) -> str:
    for key in keys:
        value = stats.get(key)
        if value is not None and value != "":
            return str(value)
    return "—"


def parse_player(entry: dict, labels: list[str]) -> dict:
    raw_stats = entry.get("stats") or []
    by_name = {str(k).strip().upper(): v for k, v in zip(labels, raw_stats)}
    athlete = entry.get("athlete") or {}
    dnp = bool(entry.get("didNotPlay") or athlete.get("didNotPlay") or not raw_stats)
    return {
        "id": str(athlete.get("id") or ""),
        "name": str(athlete.get("displayName") or athlete.get("fullName") or "Unknown player"),
        "played": not dnp,
        "reason": str(entry.get("reason") or athlete.get("reason") or "DNP") if dnp else "",
        "min": stat_for(by_name,"MIN"),
        "pts": stat_for(by_name,"PTS"),
        "reb": stat_for(by_name,"REB","TOT"),
        "ast": stat_for(by_name,"AST"),
        "pm": stat_for(by_name,"+/-","PLUSMINUS","PM"),
        "fg": stat_for(by_name,"FG"),
        "three": stat_for(by_name,"3PT","3P"),
        "ft": stat_for(by_name,"FT"),
        "stl": stat_for(by_name,"STL"),
        "blk": stat_for(by_name,"BLK"),
        "to": stat_for(by_name,"TO","TOV"),
    }


def roster_athletes(node):
    """Accept ESPN's flat or position-grouped roster arrays."""
    if isinstance(node, list):
        for item in node:
            yield from roster_athletes(item)
    elif isinstance(node, dict):
        if node.get("id") and (node.get("displayName") or node.get("fullName")):
            yield node
        for key in ("items", "athletes", "players"):
            if key in node:
                yield from roster_athletes(node[key])


@lru_cache(maxsize=64)
def team_roster(team_id: str) -> list[dict]:
    raw = get_json(f"{API}site/v2/sports/basketball/nba/teams/{team_id}/roster")
    athletes = {}
    for athlete in roster_athletes(raw.get("athletes") or []):
        aid = str(athlete.get("id") or "")
        if aid:
            athletes[aid] = {"id": aid, "name": str(athlete.get("displayName")
                                                  or athlete.get("fullName"))}
    return list(athletes.values())


@lru_cache(maxsize=64)
def team_injuries(team_id: str) -> dict:
    # Optional current injury information. It is not a historical game-day report.
    url = f"{API}site/v2/sports/basketball/nba/teams/{team_id}/injuries"
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=7) as response:
            raw = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    result = {}
    for item in raw.get("injuries") or []:
        if not isinstance(item, dict):
            continue
        athlete = item.get("athlete") or item.get("player") or {}
        if not isinstance(athlete, dict):
            continue
        aid = str(athlete.get("id") or "")
        name = str(athlete.get("displayName") or athlete.get("fullName") or "")
        values = []
        for key in ("status", "type", "shortComment"):
            value = item.get(key)
            if isinstance(value, dict):
                value = value.get("displayName") or value.get("name") or value.get("type")
            if isinstance(value, str) and value.strip() and not value.strip().upper().startswith("INJURY_STATUS_"):
                values.append(value.strip())
        details = item.get("details") or {}
        if isinstance(details, dict):
            description = details.get("detail") or details.get("type")
            if isinstance(description, str) and description.strip():
                values.append(description.strip())
        summary = " · ".join(dict.fromkeys(values))[:120]
        if summary:
            if aid:
                result["id:" + aid] = summary
            if name:
                result["name:" + name.casefold()] = summary
    return result


def game_injuries(raw: dict) -> dict:
    """Read injury statuses attached to the specific game summary, if supplied."""
    result = {}
    for block in raw.get("injuries") or []:
        if not isinstance(block, dict):
            continue
        team = block.get("team") or {}
        team_id = str(team.get("id") or block.get("teamId") or "")
        entries = block.get("injuries") or block.get("athletes") or []
        if not team_id or not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or item.get("player") or {}
            if not isinstance(athlete, dict):
                continue
            aid = str(athlete.get("id") or "")
            name = str(athlete.get("displayName") or athlete.get("fullName") or "")
            pieces = []
            for key in ("status", "type", "shortComment"):
                value = item.get(key)
                if isinstance(value, dict):
                    value = value.get("displayName") or value.get("name") or value.get("type")
                if isinstance(value, str) and value.strip() and not value.strip().upper().startswith("INJURY_STATUS_"):
                    pieces.append(value.strip())
            details = item.get("details") or {}
            if isinstance(details, dict):
                detail = details.get("detail") or details.get("type")
                if isinstance(detail, str) and detail.strip():
                    pieces.append(detail.strip())
            description = " · ".join(dict.fromkeys(pieces))[:120]
            if not description:
                continue
            if aid:
                result[(team_id, "id:" + aid)] = description
            if name:
                result[(team_id, "name:" + name.casefold())] = description
    return result


def add_missing_players(rosters: dict, team_id: str, game_notes: dict) -> None:
    players = rosters.setdefault(team_id, [])
    try:
        known = team_roster(team_id)
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print(f"WARN: Unable to load team {team_id} roster: {exc}", file=sys.stderr)
        return

    # Current injury reports are supplementary only; do not present them
    # as confirmed reasons for why somebody missed a past game.
    injuries = team_injuries(team_id)
    seen_ids = {str(p.get("id")) for p in players if p.get("id")}
    seen_names = {str(p.get("name") or "").casefold() for p in players}
    for athlete in known:
        aid, name = athlete["id"], athlete["name"]
        if aid in seen_ids or name.casefold() in seen_names:
            continue
        game_note = game_notes.get((team_id, "id:" + aid)) or game_notes.get((team_id, "name:" + name.casefold()))
        injury = injuries.get("id:" + aid) or injuries.get("name:" + name.casefold())
        reason = game_note if game_note else (
            ("Current report: " + injury) if injury else "Reason not listed")
        players.append({
            "id": aid, "name": name, "played": False, "dnp": True,
            "reason": reason,
        })
        seen_ids.add(aid)
        seen_names.add(name.casefold())


def get_boxscore(game: dict, previous_games: dict) -> dict:
    event_id = game["id"]
    old = previous_games.get(event_id) or {}
    try:
        raw = get_json(f"{API}site/v2/sports/basketball/nba/summary?event={event_id}")
        rosters = {}
        for row in (raw.get("boxscore") or {}).get("players") or []:
            team_id = str((row.get("team") or {}).get("id") or "")
            if not team_id:
                continue
            players = rosters.setdefault(team_id, [])
            seen = {player["name"] for player in players}
            for group in row.get("statistics") or []:
                labels = group.get("names") or group.get("labels") or []
                for item in group.get("athletes") or []:
                    p = parse_player(item, labels)
                    if p["name"] not in seen:
                        players.append(p)
                        seen.add(p["name"])
        expected = [game["home"]["id"], game["away"]["id"]]
        game_notes = game_injuries(raw)
        for team_id in expected:
            add_missing_players(rosters, team_id, game_notes)
        # Do not call an incomplete response a full box score.
        if all(rosters.get(team_id) for team_id in expected):
            game["rosters"] = rosters
            game["boxscoreReady"] = True
        else:
            raise ValueError("Incomplete player box score")
    except (RuntimeError, ValueError) as exc:
        print(f"WARN: {event_id}: {exc}", file=sys.stderr)
        game["rosters"] = old.get("rosters") or {}
        game["boxscoreReady"] = bool(old.get("boxscoreReady"))
    return game


def parse_standings(raw: dict) -> list[dict]:
    groups = {}

    def visit(node: dict) -> None:
        name = str(node.get("name") or node.get("displayName") or "").lower()
        conference = "East" if "eastern" in name else "West" if "western" in name else ""
        entries = (node.get("standings") or {}).get("entries") or []
        if conference and entries:
            teams = []
            for entry in entries:
                team = entry.get("team") or {}
                stats = {s.get("name"): s.get("displayValue") or s.get("value") for s in entry.get("stats") or []}
                wins = stats.get("wins", "0")
                losses = stats.get("losses", "0")
                pct = stats.get("winPercent")
                if pct is None:
                    try:
                        total = float(wins) + float(losses)
                        pct = f"{float(wins)/total:.3f}" if total else ".000"
                    except (ValueError,TypeError):
                        pct = "—"
                try:
                    pct = f"{float(pct):.3f}".lstrip("0")
                except (ValueError, TypeError):
                    pct = str(pct)
                teams.append({"name": str(team.get("displayName") or team.get("name") or "Team"),
                              "abbr": str(team.get("abbreviation") or ""),
                              "w": str(wins), "l": str(losses), "pct": pct})
            teams.sort(key=lambda t: (-float(t["pct"]) if t["pct"] != "—" else 0,
                                      -int(float(t["w"])), int(float(t["l"]))))
            groups[conference] = {"name": conference, "teams": teams}
        for child in node.get("children") or []:
            visit(child)

    visit(raw)
    return [groups[c] for c in ("East", "West") if c in groups]


def build() -> None:
    previous = load_previous()
    now = datetime.now(timezone.utc)
    games = pick_recent_games(now)
    old_games = {str(g.get("id")): g for g in previous.get("games") or []}
    if games:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(get_boxscore, game, old_games): game["id"]
                       for game in games}
            results = {futures[f]: f.result() for f in as_completed(futures)}
            games = [results[game["id"]] for game in games]
    try:
        standings = parse_standings(get_json(f"{API}v2/sports/basketball/nba/standings"))
        if len(standings) != 2 or any(len(group["teams"]) < 10 for group in standings):
            raise ValueError("Incomplete conference standings response")
    except (RuntimeError, ValueError) as exc:
        print(f"WARN: Standings: {exc}", file=sys.stderr)
        standings = previous.get("standings") or []

    if not games and not standings:
        raise RuntimeError("No NBA data available; not publishing an empty snapshot")
    day = now.astimezone(NY).date().isoformat()
    core = {"date": day, "windowHours": WINDOW_HOURS,
            "games": games, "standings": standings}
    if core == {key: previous.get(key) for key in core}:
        print("No changes to games or standings; keeping existing snapshot.")
        return
    new_data = {"date": day, "windowHours": WINDOW_HOURS,
                "updated": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "games": games, "standings": standings}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix(".tmp")
    temp.write_text(json.dumps(new_data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    os.replace(temp, OUT)
    print(f"Snapshot updated: last {WINDOW_HOURS}h, {len(games)} games, "
          f"{len(standings)} conferences; {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    build()

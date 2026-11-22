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
MAX_GAMES = 5


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


def pick_game_day(now: datetime) -> tuple[str, list[dict]]:
    # US Eastern calendar day: a late-night tip-off stays with its NBA date.
    eastern_today = now.astimezone(NY).date()
    for days_ago in range(1, 6):
        day = (eastern_today - timedelta(days=days_ago)).strftime("%Y%m%d")
        finals = final_games_for_date(day)
        if finals:
            return f"{day[:4]}-{day[4:6]}-{day[6:]}", finals[:MAX_GAMES]
    return "", []


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
        expected = [game["home"]["id"],game["away"]["id"]]
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
            groups[conference] = {"name": conference, "teams": teams}
        for child in node.get("children") or []:
            visit(child)

    visit(raw)
    return [groups[c] for c in ("East", "West") if c in groups]


def build() -> None:
    previous = load_previous()
    now = datetime.now(timezone.utc)
    day, games = pick_game_day(now)
    if not games and previous.get("games"):
        print("No recent completed games; retaining last night's saved games.")
        games = previous["games"]
        day = previous.get("date") or ""
    else:
        old_games = {str(g.get("id")): g for g in previous.get("games") or []}
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(get_boxscore, game, old_games): game["id"] for game in games}
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
    core = {"date":day or None,"games":games,"standings":standings}
    old_core = {key: previous.get(key) for key in core}
    if core == old_core:
        print("No changes to games or standings; keeping existing snapshot.")
        return
    new_data = {"date":core["date"],"updated":now.isoformat(timespec="seconds").replace("+00:00","Z"),
                "games":games,"standings":standings}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix(".tmp")
    temp.write_text(json.dumps(new_data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    os.replace(temp,OUT)
    print(f"Snapshot updated: {day}, {len(games)} games, {len(standings)} conferences; {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    build()

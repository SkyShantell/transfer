import asyncio
import csv
import json
import os
import smtplib
import io
import sys
import re
import urllib.parse
import unicodedata
import unicodedata
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo
import urllib.request
import urllib.error
import time
import random
import ssl
try:
    import psycopg2
except Exception:
    psycopg2 = None

from playwright.async_api import async_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import AuthorizedSession

from login import login, load_env


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://props.cash/"
STORAGE_STATE_PATH = os.path.join(BASE_DIR, "storage_state.json")
CONFIG_PATH = os.path.join(BASE_DIR, "props_config.json")
RESULTS_PATH = os.path.join(BASE_DIR, "props_results.json")
RESULTS_CSV_PATH = os.path.join(BASE_DIR, "props_results.csv")
ROLLING_PROP_LIST_CSV_PATH = os.path.join(BASE_DIR, "rolling_prop_list.csv")
ROLLING_PROP_LIST_FULL_CSV_PATH = os.path.join(BASE_DIR, "rolling_prop_list_full.csv")
L10_RANKINGS_CSV_PATH = os.path.join(BASE_DIR, "l10_rankings.csv")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]
TEMPLATE_IDS = {
    "NFL": "10uTYDkRYoN0O48Hwobxe8Sdib_QTgQTlHKYon1Vq06A",
    "NBA": "1NOKNZOCNvUPmRnkFWDYSOmGvrS6mKeYIRhGGKfrauEU",
    "WNBA": "1SXhmCWWE6AxV1fyv0-5uoEahQdCGf1ZVLH1IFQsQJWc",
    "NHL": "1ujkKKJuG6_XjZQRoIciPctVwIDiptDBpiuS70zU4T-w",
    "MLB": "1FzsbyO36Es2NgZgQrLN0zWIVXU1Hy-hAS64a9TiLatU",
}
FOLDER_PREFIXES = {
    "NFL": "NFL Cheatsheets",
    "NBA": "NBA Cheatsheets",
    "WNBA": "WNBA Cheatsheets",
    "NHL": "NHL Cheatsheets",
    "MLB": "MLB Cheatsheets",
}
NBA_LOOKUP_SHEET_ID = "1sM1aMiHdiTzj22PKvVhtFZzVlbxkCB2HNMYgQf16-wg"
NHL_LOOKUP_SHEET_ID = "1lWIv2h2bppJ555yl2T_IorbEEbQLcCorTHm4dJDnF38"
NFL_LOOKUP_SHEET_ID = "1pnw75HrHccHhzxoeqLbAdc_kPZo0RB-l4EWbAxUosys"
MLB_LOOKUP_SHEET_ID = (os.environ.get("MLB_LOOKUP_SHEET_ID") or "").strip()
MLB_LOOKUP_PLAYER_TAB = (os.environ.get("MLB_LOOKUP_PLAYER_TAB") or "MLB Player").strip()
MLB_LOOKUP_TEAM_TAB = (os.environ.get("MLB_LOOKUP_TEAM_TAB") or "MLB TEAMS").strip()
DEFAULT_NOTIFY_EMAIL = "rafik.khelifa.toudjine@gmail.com"
LEAGUE_LOOKUP_SHEETS = {
    "nfl": {
        "sheet_id": NFL_LOOKUP_SHEET_ID,
        "tab": "Player IDs",
        "name_col": "Player Name",
        "team_col": "Team Name",
        "id_col": "Player ID",
        "img_col": "Player IMG Link",
        "headshot_path": "nfl",
    },
    "nba": {
        "sheet_id": NBA_LOOKUP_SHEET_ID,
        "tab": "Player",
        "name_col": "Player Name",
        "team_col": "Team ID",
        "id_col": "Player ID",
        "img_col": "Player IMG link",
        "headshot_path": "nba",
    },
    "wnba": {
        "sheet_id": NBA_LOOKUP_SHEET_ID,
        "tab": "Player",
        "name_col": "Player Name",
        "team_col": "Team ID",
        "id_col": "Player ID",
        "img_col": "Player IMG link",
        "headshot_path": "wnba",
    },
    "nhl": {
        "sheet_id": NHL_LOOKUP_SHEET_ID,
        "tab": "Player",
        "name_col": "Player Name",
        "team_col": "Team ID",
        "id_col": "Player ID",
        "img_col": "Player IMG link",
        "headshot_path": "nhl",
    },
    "mlb": {
        "sheet_id": MLB_LOOKUP_SHEET_ID,
        "tab": MLB_LOOKUP_PLAYER_TAB,
        "name_col": "Player Name",
        "team_col": "Team ID",
        "id_col": "Player ID",
        "img_col": "Player IMG link",
        "headshot_path": "mlb",
    },
}
TEAM_LOOKUP_SHEETS = {
    "nfl": {
        "sheet_id": NFL_LOOKUP_SHEET_ID,
        "tab": "Team IDs",
        "name_col": "Team Name",
        "id_col": "Team ID",
        "img_col": "Team IMG Link",
    },
    "nba": {
        "sheet_id": NBA_LOOKUP_SHEET_ID,
        "tab": "TEAMS",
        "name_col": "Team Name",
        "id_col": "Team ID",
        "img_col": "Team IMG Link",
    },
    "wnba": {
        "sheet_id": NBA_LOOKUP_SHEET_ID,
        "tab": "TEAMS",
        "name_col": "Team Name",
        "id_col": "Team ID",
        "img_col": "Team IMG Link",
    },
    "nhl": {
        "sheet_id": NHL_LOOKUP_SHEET_ID,
        "tab": "TEAMS",
        "name_col": "Team Name",
        "id_col": "Team ID",
        "img_col": "Team IMG Link",
    },
    "mlb": {
        "sheet_id": MLB_LOOKUP_SHEET_ID,
        "tab": MLB_LOOKUP_TEAM_TAB,
        "name_col": "Team Name",
        "id_col": "Team ID",
        "img_col": "Team IMG Link",
    },
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def prop_url(cfg: dict, league_key: str, prop_value: str) -> str:
    base = cfg["base_url"].rstrip("/")
    league = cfg["leagues"][league_key]
    return f"{base}/{league['path']}?prop={prop_value}"


def clean_text(text: str) -> str:
    return " ".join(text.split())


def map_stat_name(league: str, prop_value: str) -> str | None:
    nfl_map = {
        "anytimeTD": "Anytime Touchdowns",
        "passTD": "Passing Touchdowns",
        "rushTD": "Rushing Touchdowns",
        "passYards": "Passing Yards",
        "rushYards": "Rushing Yards",
        "recYards": "Receiving Yards",
        "rushAndRecYards": "Rush + Receiving Yards",
        "passAndRushYards": "Pass + Rush Yards",
        "receptions": "Receptions",
        "passInt": "Interceptions",
        "passAttempts": "Pass Attempts",
        "rushAttempts": "Rushing Attempts",
        "passCompletions": "Pass Completions",
        "kickingPoints": "Kicking Points",
        "kickingFG": "Field Goals",
        "tackles": "Tackles",
        "assists": "Assists",
        "tacklesAndAssists": "Tackles + Assists",
        "sacks": "Sacks",
    }
    nba_map = {
        "points": "Points",
        "assists": "Assist",
        "rebounds": "Rebounds",
        "reboundsAssists": "Rebounds + Assist",
        "pointsReboundsAssists": "Points + Rebounds + Assist",
        "pointsRebounds": "Points + Rebounds",
        "pointsAssists": "Points + Assist",
        "fg3PtMade": "3PTM",
        "doubleDouble": "Double Double",
        "tripleDouble": "Triple Double",
        "turnovers": "Turnovers",
        "stealsAndBlocks": "Steals + Blocks",
        "steals": "Steals",
        "blocks": "Blocks",
        "firstBasket": "1st Basket",
        "fgAtt": "FG Attempts",
        "fgMade": "FG Made",
        "freeThrowMade": "Free Throws",
        "fg3PtAtt": "3PTA",
    }
    nhl_map = {
        "shotsOnGoal": "Shots on Goal",
        "points": "Points",
        "goals": "Goals",
        "powerplayPoints": "PP PTS",
        "assists": "Assists",
        "blockedShots": "Blocked Shots",
        "saves": "Saves",
        "goalsAllowed": "Goals Allowed",
        "hits": "Hits",
        "faceoffWins": "Faceoff Wins",
    }
    mlb_map = {
        "strikeouts": "Strikeouts",
        "outs": "Outs",
        "walks": "Walks",
        "hitsAllowed": "Hits Allowed",
        "earnedRuns": "Earned Runs",
        "hits": "Hits",
        "totalBases": "Total Bases",
        "hitsRunsRbis": "Hits + Runs + RBI",
        "battingStrikeouts": "Batting Ks",
        "battingWalks": "Batting BBs",
        "singles": "Singles",
        "doubles": "Doubles",
        "homeRuns": "Home Runs",
        "rbi": "RBI",
        "runs": "Runs",
    }
    league_map = {
        "nfl": nfl_map,
        "nba": nba_map,
        "wnba": nba_map,
        "nhl": nhl_map,
        "mlb": mlb_map,
    }
    return league_map.get(league, {}).get(prop_value)


def parse_percent(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_decimal(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    if text.startswith("+"):
        text = text[1:]
    try:
        return float(text)
    except ValueError:
        return None


def _db_enabled() -> bool:
    val = (os.environ.get("DB_ENABLE") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _db_connect():
    if not _db_enabled():
        return None
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed but DB_ENABLE=true")
    host = (os.environ.get("DB_HOST") or "").strip()
    port = int((os.environ.get("DB_PORT") or "5432").strip())
    name = (os.environ.get("DB_NAME") or "").strip()
    user = (os.environ.get("DB_USER") or "").strip()
    password = (os.environ.get("DB_PASSWORD") or "").strip().strip("'").strip('"')
    sslmode = (os.environ.get("DB_SSLMODE") or "require").strip()
    if not host or not name or not user or not password:
        raise RuntimeError("Missing DB_* env vars")
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=name,
        user=user,
        password=password,
        sslmode=sslmode,
        connect_timeout=10,
    )
    conn.autocommit = False
    return conn


def propscash_target_date() -> str:
    override = (
        os.environ.get("PROPSCASH_DATE")
        or os.environ.get("AI_DATE")
        or os.environ.get("RUN_DATE")
    )
    if override and override.strip():
        return override.strip()
    tz_name = (os.environ.get("APP_TZ") or "America/New_York").strip()
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()


def requested_scrape_leagues(cfg: dict) -> list[str]:
    configured = list((cfg.get("leagues") or {}).keys())
    raw = (os.environ.get("PROPSCASH_LEAGUES") or os.environ.get("RUN_LEAGUES") or "").strip()
    if not raw:
        return configured
    requested = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return [league for league in requested if league in configured]


def active_scrape_leagues(cfg: dict, log=print) -> list[str]:
    requested = requested_scrape_leagues(cfg)
    if not requested:
        return []
    if not _db_enabled():
        log(f"[calendar] DB disabled; running configured leagues: {', '.join(requested)}")
        return requested

    target_date = propscash_target_date()
    conn = None
    try:
        conn = _db_connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT lower(league)
                FROM games_calendar
                WHERE game_date = %s
                  AND lower(league) = ANY(%s)
                GROUP BY lower(league)
                ORDER BY lower(league)
                """,
                (target_date, requested),
            )
            active = {row[0] for row in cur.fetchall()}
    finally:
        if conn:
            conn.close()

    selected = [league for league in requested if league in active]
    skipped = [league for league in requested if league not in active]
    log(f"[calendar] target_date={target_date} active_leagues={', '.join(selected) or 'none'}")
    if skipped:
        log(f"[calendar] skipped no-game leagues: {', '.join(skipped)}")
    return selected


def parse_mlb_player_display(value: str) -> str:
    text = str(value or "").strip()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    text = re.sub(r"\s+[A-Z]{2,4}$", "", text).strip()
    return text


def propscash_row_player(row: dict, league: str) -> str:
    # API-normalized rows always use PLAYER. Keep the old MLB/DOM fallbacks so
    # historical result files can still be processed.
    value = row.get("PLAYER") or row.get("Player") or row.get("player") or ""
    if not value and league == "mlb":
        value = row.get("") or ""
    return parse_mlb_player_display(value) if league == "mlb" else str(value).strip()


def propscash_row_line(row: dict, league: str) -> str:
    value = row.get("L")
    if (value is None or value == "") and league == "mlb":
        value = row.get("ODDS")
    return str(value or "").strip()


def propscash_row_hit_pct(row: dict, league: str) -> str:
    value = row.get("L10")
    if (value is None or value == "") and league == "mlb":
        # Legacy MLB table layout placed the hit rate under PLAYER.
        value = row.get("PLAYER")
    return str(value or "").strip()


def propscash_row_over_odds(row: dict, league: str) -> str:
    value = row.get("O")
    if (value is None or value == "") and league == "mlb":
        value = row.get("HIT RATES")
    return str(value or "").strip()


def propscash_row_under_odds(row: dict, league: str) -> str:
    value = row.get("U")
    if (value is None or value == "") and league == "mlb":
        value = row.get("PROJ") or row.get("U Odds")
    return str(value or "").strip()


def db_insert_run_start(log, mode: str | None = None) -> int | None:
    if not _db_enabled():
        return None
    conn = None
    try:
        conn = _db_connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (source_bot, mode, sport, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("propscash", mode, "multi", "running"),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        log(f"[db] run started id={run_id}")
        return run_id
    except Exception as exc:
        if conn:
            conn.rollback()
        log(f"[db] run start failed: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def db_update_run_finish(log, run_id: int | None, status: str, error_message: str | None = None) -> None:
    if not _db_enabled() or not run_id:
        return
    conn = None
    try:
        conn = _db_connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE runs
                SET status = %s, finished_at = NOW(), error_message = %s
                WHERE id = %s
                """,
                (status, error_message, run_id),
            )
        conn.commit()
        log(f"[db] run finished id={run_id} status={status}")
    except Exception as exc:
        if conn:
            conn.rollback()
        log(f"[db] run finish update failed: {exc}")
    finally:
        if conn:
            conn.close()


def db_mark_run_data_ready(log, run_id: int | None) -> None:
    if not _db_enabled() or not run_id:
        return
    conn = None
    try:
        conn = _db_connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE runs
                SET status = 'success', error_message = NULL
                WHERE id = %s
                """,
                (run_id,),
            )
        conn.commit()
        log(f"[db] scrape data ready id={run_id} status=success")
    except Exception as exc:
        if conn:
            conn.rollback()
        log(f"[db] scrape data-ready update failed: {exc}")
    finally:
        if conn:
            conn.close()


def db_insert_propscash_rows(log, run_id: int | None, all_results: list[dict]) -> None:
    if not _db_enabled() or not all_results:
        return
    conn = None
    payload = []
    try:
        for item in all_results:
            league = str(item.get("league") or "").strip().lower()
            league_up = league.upper() if league else ""
            prop_value = str(item.get("prop") or "").strip()
            source_url = str(item.get("url") or "").strip()
            raw_headers = item.get("headers") or []
            prop_label = map_stat_name(league, prop_value) or prop_value

            for row in item.get("rows", []):
                player_raw = propscash_row_player(row, league)
                player_name = normalize_display_name(player_raw) if player_raw else ""
                line_raw = propscash_row_line(row, league)
                l10_raw = propscash_row_hit_pct(row, league)
                l20_raw = str(row.get("L20") or "").strip()
                h2h_raw = str(row.get("H2H") or "").strip()
                l5_raw = str(row.get("L5") or "").strip()
                szn_raw = str(row.get("SZN") or "").strip()
                over_raw = propscash_row_over_odds(row, league)
                under_raw = propscash_row_under_odds(row, league)

                l10 = parse_percent(l10_raw)
                h2h = parse_percent(h2h_raw)
                szn = parse_percent(szn_raw)
                vals = [v for v in (szn, l10, h2h) if v is not None]
                model_avg = (sum(vals) / len(vals)) if vals else None

                payload.append(
                    (
                        run_id,
                        "propscash",
                        league,
                        league_up,
                        None,  # mode
                        prop_label,  # category
                        prop_value,  # selected_prop (raw)
                        player_name,
                        None,  # player_id
                        prop_label,
                        parse_decimal(line_raw),
                        parse_percent(l5_raw),
                        l10,
                        parse_percent(l20_raw),
                        h2h,
                        szn,
                        model_avg,
                        parse_decimal(over_raw),
                        parse_decimal(under_raw),
                        source_url,
                        json.dumps(raw_headers, ensure_ascii=False),
                        json.dumps(row, ensure_ascii=False),
                        player_raw or None,
                        line_raw or None,
                        l10_raw or None,
                        l20_raw or None,
                        h2h_raw or None,
                    )
                )

        conn = _db_connect()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO props_rows (
                    run_id, source_bot, sport, league, mode, category, selected_prop,
                    player_name, player_id, prop, prop_line, l5, l10, l20, h2h, szn, model_avg,
                    over_odds, under_odds, source_url, raw_headers, raw_row, player_raw,
                    line_raw, hit_l10_raw, hit_l20_raw, hit_h2h_raw
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::jsonb, %s::jsonb, %s,
                    %s, %s, %s, %s
                )
                """,
                payload,
            )
        conn.commit()
        log(f"[db] inserted {len(payload)} props_rows from PropsCash")
    except Exception as exc:
        if conn:
            conn.rollback()
        log(f"[db] insert props_rows failed: {exc}")
    finally:
        if conn:
            conn.close()


def get_google_credentials(sa_json_path: str) -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(
        sa_json_path, scopes=GOOGLE_SCOPES
    )


def col_to_a1(index: int) -> str:
    result = ""
    idx = index + 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def build_headshot_url(headshot_path: str, player_id: str) -> str:
    pid = str(player_id).strip()
    return (
        "https://a.espncdn.com/combiner/i?img=/i/headshots/"
        f"{headshot_path}/players/full/{pid}.png&w=350&h=254"
    )


def normalize_search_name(name: str) -> str:
    text = normalize_display_name(name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip()


def extract_team_abbr_and_position(raw_name: str) -> tuple[str | None, str | None]:
    text = str(raw_name or "")
    if "|" not in text:
        return None, None
    left, right = text.split("|", 1)
    position = right.strip().split()[0] if right.strip() else None
    tokens = left.strip().split()
    team_abbr = tokens[-1] if tokens else None
    if team_abbr and team_abbr.isalpha() and 2 <= len(team_abbr) <= 4:
        return team_abbr.upper(), position
    return None, position


def normalize_team_name(name: str) -> str:
    text = str(name or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def build_team_id_map(values: list[list[str]], name_col: str, id_col: str) -> dict:
    if not values:
        return {}
    header = values[0]
    rows = values[1:]
    try:
        name_idx = header.index(name_col)
        id_idx = header.index(id_col)
    except ValueError:
        return {}
    mapping = {}
    for row in rows:
        if len(row) <= max(name_idx, id_idx):
            continue
        name = normalize_team_name(row[name_idx])
        if not name:
            continue
        mapping[name] = str(row[id_idx]).strip()
    return mapping


async def fetch_espn_player_id(page, league: str, player_name: str) -> str | None:
    search_name = normalize_search_name(player_name)
    await page.goto("https://www.espn.com/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1000)
    try:
        search_button = page.get_by_role("button", name=re.compile("search", re.I))
        if await search_button.count() > 0:
            await search_button.first.click()
        search_box = page.get_by_role("textbox", name=re.compile("search", re.I))
        await search_box.first.fill(search_name)
        await search_box.first.press("Enter")
    except Exception:
        query = urllib.parse.quote(search_name)
        search_url = f"https://www.espn.com/search/results?q={query}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1500)

    hrefs = await page.eval_on_selector_all(
        "a[href*='/player/_/id/']",
        "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
    )
    if not hrefs:
        return None

    league_tag = f"/{league}/player/_/id/"
    candidates = [h for h in hrefs if league_tag in h] or hrefs
    for href in candidates:
        match = re.search(r"/player/_/id/(\d+)", href)
        if match:
            return match.group(1)
    return None


async def fetch_espn_team_name(page, league: str, player_id: str) -> str | None:
    url = f"https://www.espn.com/{league}/player/_/id/{player_id}"
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1500)
    team_link = page.locator(".PlayerHeader__Team_Info a").first
    if await team_link.count() > 0:
        text = (await team_link.inner_text()).strip()
        return text or None
    html = await page.content()
    match = re.search(r'"team":\{[^}]*"displayName":"([^"]+)"', html)
    if match:
        return match.group(1)
    return None


async def update_missing_player_ids_and_images(
    sa_json_path: str, target_names: dict | None = None
) -> dict:
    credentials = get_google_credentials(sa_json_path)
    sheets = build("sheets", "v4", credentials=credentials)
    summary = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        for league, cfg in LEAGUE_LOOKUP_SHEETS.items():
            if not cfg.get("sheet_id") or not cfg.get("tab"):
                continue
            values = read_lookup_sheet_values(
                sheets,
                cfg["sheet_id"],
                cfg["tab"],
                player_lookup_headers(cfg),
                create=True,
            )
            if not values:
                continue
            header = values[0]
            rows = values[1:]
            try:
                name_idx = header.index(cfg["name_col"])
                id_idx = header.index(cfg["id_col"])
                img_idx = header.index(cfg["img_col"])
            except ValueError:
                continue

            league_targets = {}
            if target_names and league in target_names:
                league_targets = dict(target_names[league])
            if not league_targets:
                continue
            print(f"[missing-ids] {league.upper()}: checking {len(league_targets)} players")

            existing = {}
            for row_offset, row in enumerate(rows, start=2):
                if len(row) <= name_idx:
                    continue
                name_raw = str(row[name_idx]).strip()
                if not name_raw:
                    continue
                existing[clean_name(name_raw)] = (row_offset, row)

            team_cfg = TEAM_LOOKUP_SHEETS.get(league)
            team_map = {}
            if team_cfg and team_cfg.get("sheet_id") and team_cfg.get("tab"):
                team_values = read_lookup_sheet_values(
                    sheets,
                    team_cfg["sheet_id"],
                    team_cfg["tab"],
                    team_lookup_headers(team_cfg),
                    create=True,
                )
                team_map = build_team_id_map(team_values, team_cfg["name_col"], team_cfg["id_col"])

            updates = []
            appended_rows = []
            updated_players = []

            candidate_keys = list(league_targets.keys())
            existing_keys = list(existing.keys())
            for idx, name_key in enumerate(sorted(candidate_keys), start=1):
                row_info = existing.get(name_key)
                if not row_info and existing_keys:
                    match_key = best_fuzzy_match(name_key, existing_keys)
                    row_info = existing.get(match_key) if match_key else None
                row_offset = None
                row = None
                display_name = None
                if row_info:
                    row_offset, row = row_info
                    display_name = str(row[name_idx]).strip()
                else:
                    display_name = normalize_display_name(league_targets.get(name_key, name_key))
                    row_offset = None

                print(f"[missing-ids] {league.upper()} {idx}/{len(candidate_keys)}: {display_name}")

                # If the player already exists in the sheet, do nothing.
                if row_offset:
                    continue

                raw_name = league_targets.get(name_key, name_key)
                team_abbr, position = extract_team_abbr_and_position(raw_name)
                try:
                    player_id = await fetch_espn_player_id(page, league, display_name)
                except Exception as exc:
                    print(f"[missing-ids]   ! ESPN lookup error for {display_name}: {exc}")
                    continue
                if not player_id:
                    print(f"[missing-ids]   ! ESPN not found for {display_name}")
                    continue
                try:
                    team_name = await fetch_espn_team_name(page, league, player_id)
                except Exception as exc:
                    print(f"[missing-ids]   ! ESPN team lookup error for {display_name}: {exc}")
                    team_name = None
                team_id = ""
                if team_name and team_map:
                    team_id = team_map.get(normalize_team_name(team_name), "")
                img_url = build_headshot_url(cfg["headshot_path"], player_id)

                new_row = [""] * max(len(header), img_idx + 1)
                new_row[name_idx] = display_name
                new_row[id_idx] = player_id
                new_row[img_idx] = img_url
                if "Position" in header and position:
                    pos_idx = header.index("Position")
                    if pos_idx < len(new_row):
                        new_row[pos_idx] = position
                if "Team Name" in header and team_name:
                    team_name_idx = header.index("Team Name")
                    if team_name_idx < len(new_row):
                        new_row[team_name_idx] = team_name
                if "Team ID" in header and team_id:
                    team_id_idx = header.index("Team ID")
                    if team_id_idx < len(new_row):
                        new_row[team_id_idx] = team_id
                appended_rows.append(new_row)
                print("[missing-ids]   ✓ appended new row")

                updated_players.append(display_name)
                await page.wait_for_timeout(500)

            if appended_rows:
                sheets.spreadsheets().values().append(
                    spreadsheetId=cfg["sheet_id"],
                    range=quote_sheet_tab(cfg["tab"]),
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": appended_rows},
                ).execute()
                print(f"[missing-ids] {league.upper()}: appended {len(appended_rows)} rows")

            if updated_players:
                summary[league] = updated_players

        await browser.close()

    return summary

def build_rolling_prop_rows(all_results: list[dict]) -> list[dict]:
    rows = []
    for payload in all_results:
        league = payload.get("league")
        prop_value = payload.get("prop")
        stat_name = map_stat_name(league, prop_value)
        if not stat_name:
            continue

        over_candidates = []
        under_candidates = []
        for row in payload.get("rows", []):
            player = propscash_row_player(row, league)
            line = propscash_row_line(row, league)
            hit_pct = propscash_row_hit_pct(row, league)
            hit_pct_val = parse_percent(hit_pct)
            over_odds = propscash_row_over_odds(row, league)
            under_odds = propscash_row_under_odds(row, league)

            sport = str(league or "").upper()

            if player and over_odds and hit_pct_val is not None and hit_pct_val >= 60:
                over_candidates.append(
                    (
                        hit_pct_val,
                        {
                            "Sport": sport,
                            "Game Date": "",
                            "Event ID": "",
                            "Stat Category": stat_name,
                            "Player Name": player,
                            "Over/Under": "O",
                            "Line": line,
                            "Odds": over_odds,
                            "Home Team": "",
                            "Away Team": "",
                            "Hit %": hit_pct,
                        },
                    )
                )

            if player and under_odds and hit_pct_val is not None and hit_pct_val <= 40:
                under_candidates.append(
                    (
                        hit_pct_val,
                        {
                            "Sport": sport,
                            "Game Date": "",
                            "Event ID": "",
                            "Stat Category": stat_name,
                            "Player Name": player,
                            "Over/Under": "U",
                            "Line": line,
                            "Odds": under_odds,
                            "Home Team": "",
                            "Away Team": "",
                            "Hit %": hit_pct,
                        },
                    )
                )

        over_candidates.sort(key=lambda item: item[0], reverse=True)
        under_candidates.sort(key=lambda item: item[0])

        rows.extend([row for _, row in over_candidates[:20]])
        rows.extend([row for _, row in under_candidates[:20]])

    return rows


def build_rolling_prop_rows_full(all_results: list[dict]) -> list[dict]:
    rows = []
    for payload in all_results:
        league = payload.get("league")
        prop_value = payload.get("prop")
        stat_name = map_stat_name(league, prop_value)
        if not stat_name:
            continue

        for row in payload.get("rows", []):
            player = propscash_row_player(row, league)
            line = propscash_row_line(row, league)
            hit_pct = propscash_row_hit_pct(row, league)
            over_odds = propscash_row_over_odds(row, league)
            under_odds = propscash_row_under_odds(row, league)

            sport = str(league or "").upper()

            if player and over_odds:
                rows.append(
                    {
                        "Sport": sport,
                        "Game Date": "",
                        "Event ID": "",
                        "Stat Category": stat_name,
                        "Player Name": player,
                        "Over/Under": "O",
                        "Line": line,
                        "Odds": over_odds,
                        "Home Team": "",
                        "Away Team": "",
                        "Hit %": hit_pct,
                    }
                )

            if player and under_odds:
                rows.append(
                    {
                        "Sport": sport,
                        "Game Date": "",
                        "Event ID": "",
                        "Stat Category": stat_name,
                        "Player Name": player,
                        "Over/Under": "U",
                        "Line": line,
                        "Odds": under_odds,
                        "Home Team": "",
                        "Away Team": "",
                        "Hit %": hit_pct,
                    }
                )

    return rows


def build_l10_rankings(rows: list[dict]) -> list[dict]:
    rankings = []
    for row in rows:
        ou = row.get("Over/Under", "")
        hit_pct_raw = row.get("Hit %", "")
        hit_pct = parse_percent(hit_pct_raw)
        if hit_pct is None:
            continue

        ou_upper = str(ou).upper()
        final_pct = None
        if ou_upper == "O":
            if 60 <= hit_pct <= 100:
                final_pct = hit_pct
        elif ou_upper == "U":
            if 0 <= hit_pct <= 40:
                final_pct = 100 - hit_pct

        if final_pct is None:
            continue

        rankings.append(
            {
                "Stat": row.get("Stat Category", ""),
                "OverUnder": ou,
                "Player Name": row.get("Player Name", ""),
                "Odds": row.get("Odds", ""),
                "Line": row.get("Line", ""),
                "HitRateDecimal": round(final_pct / 100, 4),
            }
        )

    return rankings


def upload_csv_to_sheet(csv_path: str, sheet_id: str, tab_name: str, sa_json_path: str) -> None:
    credentials = get_google_credentials(sa_json_path)
    service = build("sheets", "v4", credentials=credentials)
    sheet_range = f"{tab_name}!A1"

    with open(csv_path, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        values = [row for row in reader]

    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=tab_name,
        body={},
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    print(f"Uploaded {os.path.basename(csv_path)} to sheet tab '{tab_name}'.")


def normalize_display_name(name: str) -> str:
    text = str(name or "").strip()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    parts = text.split()
    if parts:
        last = parts[-1]
        if last.isupper() and 2 <= len(last) <= 4:
            text = " ".join(parts[:-1])
        else:
            suffix = ""
            if len(last) >= 3:
                tail = last[-4:]
                if tail.isupper():
                    for i in range(2, 5):
                        if len(last) >= i and last[-i:].isupper():
                            prefix = last[:-i]
                            if prefix and prefix[-1].islower():
                                suffix = last[-i:]
                                text = " ".join(parts[:-1] + [prefix])
                                break
    return text.strip()


def clean_name(name: str) -> str:
    text = str(name or "")
    text = text.split("|", 1)[0]
    text = text.replace(".", "").replace("'", "").replace("-", "")
    parts = []
    for token in text.split():
        if token.lower() in {"jr", "sr", "ii", "iii", "iv"}:
            continue
        parts.append(token)
    return " ".join(parts).strip().lower()


def levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[m][n]


def last_name_of(name: str) -> str:
    parts = str(name or "").strip().split()
    return parts[-1] if parts else ""


def best_fuzzy_match(target: str, candidates: list[str]) -> str | None:
    t = str(target or "")
    t_last = last_name_of(t)
    best = None
    best_score = 0.0
    for candidate in candidates:
        if t_last and last_name_of(candidate) != t_last:
            continue
        dist = levenshtein(t, candidate)
        score = 1 - dist / max(len(t), len(candidate))
        if score > best_score:
            best_score = score
            best = candidate
    return best if best_score >= 0.88 else None


def get_player_match(player_map: dict, names: list[str], lookup: str) -> dict | None:
    if lookup in player_map:
        return player_map[lookup]
    match = best_fuzzy_match(lookup, names)
    return player_map.get(match) if match else None


ESPN_PLAYER_ASSET_CACHE: dict[tuple[str, str], dict] = {}


def get_espn_player_assets(league: str, player_name: str) -> dict:
    league = str(league or "").lower().strip()
    display_name = normalize_display_name(player_name)
    cache_key = (league, clean_name(display_name))
    if not league or not cache_key[1]:
        return {}
    if cache_key in ESPN_PLAYER_ASSET_CACHE:
        return ESPN_PLAYER_ASSET_CACHE[cache_key]

    url = (
        "https://site.web.api.espn.com/apis/common/v3/search?"
        + urllib.parse.urlencode(
            {
                "region": "us",
                "lang": "en",
                "query": display_name,
                "limit": "8",
                "mode": "prefix",
                "type": "player",
            }
        )
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
    except Exception:
        ESPN_PLAYER_ASSET_CACHE[cache_key] = {}
        return {}

    candidates = [
        item
        for item in data.get("items", [])
        if str(item.get("league", "")).lower() == league
    ]
    if not candidates:
        candidates = [
            item
            for item in data.get("items", [])
            if f"/{league}/player/" in json.dumps(item.get("links", []))
        ]

    target = cache_key[1]
    by_name = {clean_name(item.get("displayName", "")): item for item in candidates}
    item = by_name.get(target)
    if not item and by_name:
        match = best_fuzzy_match(target, list(by_name.keys()))
        item = by_name.get(match) if match else None
    if not item:
        ESPN_PLAYER_ASSET_CACHE[cache_key] = {}
        return {}

    player_id = str(item.get("id", "")).strip()
    headshot = item.get("headshot") or {}
    player_img = headshot.get("href") or (build_headshot_url(league, player_id) if player_id else "")
    team_logo = ""
    for relationship in item.get("teamRelationships", []) or []:
        logos = relationship.get("core", {}).get("logos", []) or []
        default_logo = next(
            (
                logo.get("href", "")
                for logo in logos
                if "default" in (logo.get("rel") or []) and logo.get("href", "").startswith("http")
            ),
            "",
        )
        team_logo = default_logo or next(
            (logo.get("href", "") for logo in logos if logo.get("href", "").startswith("http")),
            "",
        )
        if team_logo:
            break

    assets = {"img": player_img, "team_logo": team_logo}
    ESPN_PLAYER_ASSET_CACHE[cache_key] = assets
    return assets


def read_sheet_values(service, sheet_id: str, tab: str) -> list[list[str]]:
    ranges = [tab]
    quoted_tab = quote_sheet_tab(tab)
    if quoted_tab not in ranges:
        ranges.append(quoted_tab)

    last_exc = None
    for range_name in ranges:
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [])
        except Exception as exc:
            last_exc = exc
            if "unable to parse range" not in str(exc).lower():
                raise
    if last_exc:
        raise last_exc
    return []


def quote_sheet_tab(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


def lookup_headers(*columns: str) -> list[str]:
    headers = []
    for column in columns:
        if column and column not in headers:
            headers.append(column)
    return headers


def player_lookup_headers(cfg: dict) -> list[str]:
    return lookup_headers(
        cfg.get("name_col", ""),
        cfg.get("team_col", ""),
        cfg.get("id_col", ""),
        cfg.get("img_col", ""),
        "Position",
        "Team Name",
    )


def team_lookup_headers(cfg: dict) -> list[str]:
    return lookup_headers(
        cfg.get("name_col", ""),
        cfg.get("id_col", ""),
        cfg.get("img_col", ""),
    )


def is_missing_sheet_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "unable to parse range" in msg
        or "requested entity was not found" in msg
        or "does not exist" in msg
    )


def ensure_sheet_tab(service, sheet_id: str, tab: str) -> None:
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()
    except Exception as exc:
        if "already exists" not in str(exc).lower():
            raise


def read_lookup_sheet_values(
    service,
    sheet_id: str,
    tab: str,
    headers: list[str],
    create: bool = False,
) -> list[list[str]]:
    if not sheet_id or not tab:
        return []
    try:
        values = read_sheet_values(service, sheet_id, tab)
    except Exception as exc:
        if not create:
            return []
        if not is_missing_sheet_error(exc):
            raise
        ensure_sheet_tab(service, sheet_id, tab)
        values = []

    if not create:
        return values

    if not values:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{quote_sheet_tab(tab)}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
        return [headers]

    current_headers = list(values[0])
    missing_headers = [header for header in headers if header not in current_headers]
    if missing_headers:
        updated_headers = current_headers + missing_headers
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{quote_sheet_tab(tab)}!A1",
            valueInputOption="RAW",
            body={"values": [updated_headers]},
        ).execute()
        values[0] = updated_headers

    return values


def build_player_map(values: list[list[str]], name_col: str, team_col: str, img_col: str) -> dict:
    if not values:
        return {}
    header = values[0]
    rows = values[1:]
    idx = {name: header.index(name) for name in header if name in {name_col, team_col, img_col}}
    name_idx = idx.get(name_col)
    team_idx = idx.get(team_col)
    img_idx = idx.get(img_col)
    if name_idx is None or team_idx is None or img_idx is None:
        return {}
    mapping = {}
    for row in rows:
        if len(row) <= max(name_idx, team_idx, img_idx):
            continue
        name = clean_name(row[name_idx])
        if not name:
            continue
        mapping[name] = {"team": row[team_idx], "img": row[img_idx]}
    return mapping


def build_team_map(values: list[list[str]], key_col: str, img_col: str) -> dict:
    if not values:
        return {}
    header = values[0]
    rows = values[1:]
    idx = {name: header.index(name) for name in header if name in {key_col, img_col}}
    key_idx = idx.get(key_col)
    img_idx = idx.get(img_col)
    if key_idx is None or img_idx is None:
        return {}
    mapping = {}
    for row in rows:
        if len(row) <= max(key_idx, img_idx):
            continue
        key = str(row[key_idx]).strip()
        if not key:
            continue
        mapping[key] = row[img_idx] if len(row) > img_idx else ""
    return mapping


def load_player_lookup_assets(
    sheets, league: str
) -> tuple[dict, list[str], dict]:
    player_cfg = LEAGUE_LOOKUP_SHEETS.get(league, {})
    team_cfg = TEAM_LOOKUP_SHEETS.get(league, {})
    players = {}
    teams = {}

    if player_cfg.get("sheet_id") and player_cfg.get("tab"):
        players = build_player_map(
            read_lookup_sheet_values(
                sheets,
                player_cfg["sheet_id"],
                player_cfg["tab"],
                player_lookup_headers(player_cfg),
            ),
            player_cfg["name_col"],
            player_cfg["team_col"],
            player_cfg["img_col"],
        )

    if team_cfg.get("sheet_id") and team_cfg.get("tab"):
        teams = build_team_map(
            read_lookup_sheet_values(
                sheets,
                team_cfg["sheet_id"],
                team_cfg["tab"],
                team_lookup_headers(team_cfg),
            ),
            team_cfg["id_col"] if player_cfg.get("team_col") == team_cfg.get("id_col") else team_cfg["name_col"],
            team_cfg["img_col"],
        )

    return players, list(players.keys()), teams


def build_slide_groups(rolling_rows: list[dict], sa_json_path: str) -> dict:
    credentials = get_google_credentials(sa_json_path)
    sheets = build("sheets", "v4", credentials=credentials)

    nba_players, nba_names, nba_teams = load_player_lookup_assets(sheets, "nba")
    wnba_players, wnba_names, wnba_teams = load_player_lookup_assets(sheets, "wnba")
    nhl_players, nhl_names, nhl_teams = load_player_lookup_assets(sheets, "nhl")
    nfl_players, nfl_names, nfl_teams = load_player_lookup_assets(sheets, "nfl")
    mlb_players, mlb_names, mlb_teams = load_player_lookup_assets(sheets, "mlb")

    groups: dict = {}
    for row in rolling_rows:
        sport = str(row.get("Sport", "")).upper().strip()
        category = row.get("Stat Category", "")
        ou = str(row.get("Over/Under", "")).upper().strip()
        if not sport or not category or ou not in {"O", "U"}:
            continue

        raw_player = str(row.get("Player Name", "")).strip()
        if not raw_player:
            continue

        display_name = normalize_display_name(raw_player)
        lookup_name = clean_name(display_name)

        hit_pct = parse_percent(row.get("Hit %", ""))
        if hit_pct is None:
            continue
        hr_val = hit_pct if ou == "O" else 100 - hit_pct
        hr_text = f"{round(hr_val)}%"

        player_img = ""
        team_logo = ""
        if sport == "NBA":
            match = get_player_match(nba_players, nba_names, lookup_name)
            if match:
                player_img = match.get("img", "")
                team_logo = nba_teams.get(str(match.get("team", "")), "")
        elif sport == "WNBA":
            match = get_player_match(wnba_players, wnba_names, lookup_name)
            if match:
                player_img = match.get("img", "")
                team_logo = wnba_teams.get(str(match.get("team", "")), "")
        elif sport == "NHL":
            match = get_player_match(nhl_players, nhl_names, lookup_name)
            if match:
                player_img = match.get("img", "")
                team_logo = nhl_teams.get(str(match.get("team", "")), "")
        elif sport == "NFL":
            match = get_player_match(nfl_players, nfl_names, lookup_name)
            if match:
                player_img = match.get("img", "")
                team_logo = nfl_teams.get(str(match.get("team", "")), "")
        elif sport == "MLB":
            match = get_player_match(mlb_players, mlb_names, lookup_name)
            if match:
                player_img = match.get("img", "")
                team_logo = mlb_teams.get(str(match.get("team", "")), "")
            if not player_img:
                assets = get_espn_player_assets("mlb", display_name)
                player_img = assets.get("img", "")
                team_logo = team_logo or assets.get("team_logo", "")

        entry = {
            "player_name": display_name,
            "line": row.get("Line", ""),
            "odds": row.get("Odds", ""),
            "hr": hr_text,
            "player_image_url": player_img,
            "team_logo_url": team_logo,
        }

        if sport not in groups:
            groups[sport] = {}
        if category not in groups[sport]:
            groups[sport][category] = {"OVER": [], "UNDER": []}
        side = "OVER" if ou == "O" else "UNDER"
        groups[sport][category][side].append(entry)

    return groups


def get_slide_image_tags(presentation: dict) -> dict:
    slide = presentation.get("slides", [])[0] if presentation.get("slides") else None
    if not slide:
        return {}
    tag_map = {}
    for element in slide.get("pageElements", []):
        obj_id = element.get("objectId")
        if not obj_id:
            continue
        description = element.get("description", "") or ""
        title = element.get("title", "") or ""
        tag = description.strip() or title.strip()
        if tag:
            tag_map[tag] = obj_id
    return tag_map


def presentation_has_unresolved_placeholders(presentation: dict) -> bool:
    def contains_placeholder(value) -> bool:
        if isinstance(value, str):
            return "{{" in value or "}}" in value
        if isinstance(value, list):
            return any(contains_placeholder(item) for item in value)
        if isinstance(value, dict):
            return any(contains_placeholder(item) for item in value.values())
        return False

    return contains_placeholder(presentation.get("slides", []))


def create_or_get_folder(drive, name: str, parent_id: str | None) -> str:
    query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
    safe_name = name.replace("'", "\\'")
    query += f" and name='{safe_name}'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    result = drive.files().list(
        q=query,
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = drive.files().create(
        body=metadata, fields="id", supportsAllDrives=True
    ).execute()
    return folder["id"]


def ensure_folder_shared(drive, folder_id: str) -> None:
    try:
        drive.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        return


def chunk_entries(entries: list[dict], size: int) -> list[list[dict]]:
    return [entries[i : i + size] for i in range(0, len(entries), size)]


def is_public_image_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                return True
    except Exception:
        pass

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                return True
    except Exception:
        return False
    return False


def short_error(exc: Exception) -> str:
    msg = str(exc).splitlines()[0]
    return msg[:220] + ("..." if len(msg) > 220 else "")


def download_thumbnail_with_retry(
    authed_session,
    content_url: str,
    file_name: str,
    attempts: int = 5,
) -> bytes | None:
    for attempt in range(attempts):
        try:
            response = authed_session.get(content_url, timeout=60)
        except Exception as exc:
            if attempt == attempts - 1:
                print(
                    f"    ! Thumbnail download failed after {attempts} attempts for "
                    f"{file_name}: {short_error(exc)}"
                )
                return None
            delay = 2.5 + attempt * 2.0 + random.uniform(0, 1.0)
            print(
                f"    ! thumbnail download for {file_name} transient error, "
                f"retrying in {delay:.1f}s: {short_error(exc)}"
            )
            time.sleep(delay)
            continue

        if response.status_code == 200:
            return response.content
        if response.status_code not in {408, 429, 500, 502, 503, 504}:
            print(f"    ! Thumbnail download failed for {file_name}: HTTP {response.status_code}")
            return None
        if attempt == attempts - 1:
            print(
                f"    ! Thumbnail download failed after {attempts} attempts for "
                f"{file_name}: HTTP {response.status_code}"
            )
            return None
        delay = 10.0 if response.status_code == 429 else 2.5 + attempt * 2.0
        print(
            f"    ! thumbnail download for {file_name} returned HTTP {response.status_code}, "
            f"retrying in {delay:.1f}s"
        )
        time.sleep(delay)
    return None


def generate_pngs_from_slides(groups: dict, sa_json_path: str) -> dict:
    credentials = get_google_credentials(sa_json_path)
    drive = build("drive", "v3", credentials=credentials)
    slides = build("slides", "v1", credentials=credentials)
    authed_session = AuthorizedSession(credentials)

    parent_folder_id = os.environ.get("GOOGLE_DRIVE_PARENT_ID")
    date_string = datetime.now().strftime("%m/%d/%Y").lstrip("0").replace("/0", "/")
    telegram_queue: list[tuple[str, bytes]] = []

    def execute_with_retry(request_factory, label: str, attempts: int = 5):
        for attempt in range(attempts):
            try:
                return request_factory().execute()
            except Exception as exc:
                msg = str(exc)
                is_retryable = (
                    isinstance(exc, TimeoutError)
                    or "timed out" in msg.lower()
                    or "TIMEOUT" in msg
                    or "429" in msg
                    or "RATE_LIMIT_EXCEEDED" in msg
                    or "503" in msg
                    or "500" in msg
                    or isinstance(exc, ssl.SSLEOFError)
                    or "EOF occurred in violation of protocol" in msg
                )
                if not is_retryable or attempt == attempts - 1:
                    raise
                is_rate_limited = (
                    "429" in msg
                    or "RATE_LIMIT_EXCEEDED" in msg
                    or "WriteRequestsPerMinutePerUser" in msg
                )
                delay = (
                    65.0 + attempt * 5.0 + random.uniform(0, 2.0)
                    if is_rate_limited
                    else 2.5 + attempt * 2.0 + random.uniform(0, 1.0)
                )
                print(f"    ! {label} transient error, retrying in {delay:.1f}s: {exc}")
                time.sleep(delay)

    summary = {"folders": {}, "png_count": 0}
    for sport, categories in groups.items():
        if sport not in TEMPLATE_IDS:
            continue
        folder_name = f"{FOLDER_PREFIXES[sport]} {date_string}"
        print(f"Generating PNGs for {sport} into '{folder_name}'...")
        folder_id = create_or_get_folder(drive, folder_name, parent_folder_id)
        ensure_folder_shared(drive, folder_id)
        summary["folders"][sport] = folder_id

        for category, sides in categories.items():
            for side in ("OVER", "UNDER"):
                entries = sides.get(side, [])
                if not entries:
                    continue
                pages = chunk_entries(entries, 20)
                for page_idx, page_entries in enumerate(pages, start=1):
                    page_num = f" ({page_idx})" if len(pages) > 1 else ""
                    file_name = f"{sport} - {side} {category}{page_num}"
                    print(f"  - {file_name} ({len(page_entries)} players)")

                    copied = execute_with_retry(
                        lambda: drive.files().copy(
                            fileId=TEMPLATE_IDS[sport],
                            body={"name": file_name, "parents": [folder_id]},
                            fields="id",
                            supportsAllDrives=True,
                        ),
                        f"copy template for {file_name}",
                    )
                    presentation_id = copied["id"]

                    presentation = execute_with_retry(
                        lambda: slides.presentations().get(presentationId=presentation_id),
                        f"load presentation for {file_name}",
                    )
                    slide_id = presentation.get("slides", [])[0].get("objectId")
                    image_tags = get_slide_image_tags(presentation)

                    text_requests = []
                    image_requests = []
                    text_requests.append(
                        {
                            "replaceAllText": {
                                "containsText": {"text": "{{title}}", "matchCase": True},
                                "replaceText": date_string,
                            }
                        }
                    )
                    text_requests.append(
                        {
                            "replaceAllText": {
                                "containsText": {"text": "{{subtitle}}", "matchCase": True},
                                "replaceText": f"{side} {category}",
                            }
                        }
                    )

                    for idx in range(1, 21):
                        entry = page_entries[idx - 1] if idx <= len(page_entries) else None
                        player_name = entry.get("player_name", "") if entry else ""
                        line = entry.get("line", "") if entry else ""
                        odds = entry.get("odds", "") if entry else ""
                        odds_str = str(odds or "")
                        if odds_str and not odds_str.startswith(("-", "+")):
                            odds_str = f"+{odds_str}"
                        hr = entry.get("hr", "") if entry else ""

                        replacements = {
                            f"{{{{PlayerName{idx}}}}}": player_name,
                            f"{{{{PropLine{idx}}}}}": line,
                            f"{{{{Odds{idx}}}}}": odds_str,
                            f"{{{{HR{idx}}}}}": hr,
                        }
                        for placeholder, value in replacements.items():
                            text_requests.append(
                                {
                                    "replaceAllText": {
                                        "containsText": {"text": placeholder, "matchCase": True},
                                        "replaceText": value,
                                    }
                                }
                            )

                        player_tag = f"player{idx}"
                        team_tag = f"team{idx}"
                        player_obj = image_tags.get(player_tag)
                        team_obj = image_tags.get(team_tag)
                        player_url = entry.get("player_image_url", "").strip() if entry else ""
                        team_url = entry.get("team_logo_url", "").strip() if entry else ""

                        if player_obj:
                            if is_public_image_url(player_url):
                                image_requests.append(
                                    {
                                        "replaceImage": {
                                            "imageObjectId": player_obj,
                                            "url": player_url,
                                        }
                                    }
                                )
                            else:
                                image_requests.append({"deleteObject": {"objectId": player_obj}})
                        if team_obj:
                            if is_public_image_url(team_url):
                                image_requests.append(
                                    {
                                        "replaceImage": {
                                            "imageObjectId": team_obj,
                                            "url": team_url,
                                        }
                                    }
                                )
                            else:
                                image_requests.append({"deleteObject": {"objectId": team_obj}})

                    try:
                        execute_with_retry(
                            lambda: slides.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": text_requests},
                            ),
                            f"text batchUpdate for {file_name}",
                        )
                    except Exception as exc:
                        print(f"    ! Slide text update failed; skipping PNG for {file_name}: {exc}")
                        continue

                    skipped_images = 0

                    def delete_image_placeholder(image_request: dict) -> None:
                        object_id = image_request.get("replaceImage", {}).get("imageObjectId")
                        if not object_id:
                            return
                        try:
                            execute_with_retry(
                                lambda object_id=object_id: slides.presentations().batchUpdate(
                                    presentationId=presentation_id,
                                    body={"requests": [{"deleteObject": {"objectId": object_id}}]},
                                ),
                                f"delete failed image placeholder for {file_name}",
                                attempts=2,
                            )
                        except Exception as delete_exc:
                            print(f"    ! Failed image cleanup for {file_name}: {short_error(delete_exc)}")

                    for image_idx, image_request in enumerate(image_requests, start=1):
                        try:
                            execute_with_retry(
                                lambda image_request=image_request: slides.presentations().batchUpdate(
                                    presentationId=presentation_id,
                                    body={"requests": [image_request]},
                                ),
                                f"image update {image_idx}/{len(image_requests)} for {file_name}",
                            )
                        except Exception as exc:
                            skipped_images += 1
                            delete_image_placeholder(image_request)
                            print(f"    ! Image skipped for {file_name}: {short_error(exc)}")

                    if skipped_images:
                        print(f"    ✓ Slide updated for {file_name} (skipped {skipped_images} bad image(s))")
                    else:
                        print(f"    ✓ Slide updated for {file_name}")
                    time.sleep(2.0)

                    verified_presentation = execute_with_retry(
                        lambda: slides.presentations().get(presentationId=presentation_id),
                        f"verify placeholders for {file_name}",
                    )
                    if presentation_has_unresolved_placeholders(verified_presentation):
                        print(f"    ! Unresolved placeholders remain; skipping PNG for {file_name}")
                        continue

                    thumbnail = execute_with_retry(
                        lambda: slides.presentations()
                        .pages()
                        .getThumbnail(
                            presentationId=presentation_id,
                            pageObjectId=slide_id,
                            thumbnailProperties_thumbnailSize="LARGE",
                        ),
                        f"getThumbnail for {file_name}",
                    )
                    content_url = thumbnail.get("contentUrl")
                    if not content_url:
                        continue

                    png_bytes = download_thumbnail_with_retry(
                        authed_session,
                        content_url,
                        file_name,
                    )
                    if not png_bytes:
                        continue
                    media = MediaIoBaseUpload(io.BytesIO(png_bytes), mimetype="image/png")
                    execute_with_retry(
                        lambda: drive.files().create(
                            body={"name": f"{file_name}.png", "parents": [folder_id]},
                            media_body=media,
                            fields="id",
                            supportsAllDrives=True,
                        ),
                        f"upload PNG for {file_name}",
                    )
                    print(f"    ✓ PNG uploaded: {file_name}.png")
                    summary["png_count"] += 1
                    telegram_queue.append((f"{file_name}.png", png_bytes))
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if os.environ.get("TELEGRAM_SEND_PNGS", "0") == "1" and token and chat_id and telegram_queue:
        try:
            from telegrambot import send_telegram_photos
        except Exception as exc:
            print(f"[telegram] import failed: {exc}")
        else:
            print(f"[telegram] sending {len(telegram_queue)} pngs...")
            send_telegram_photos(token, chat_id, telegram_queue)
    return summary


def maybe_send_email(subject: str, body: str) -> None:
    sender = os.environ.get("GMAIL_USER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender or not app_password:
        return
    notify_env = os.environ.get("NOTIFY_EMAILS", "").strip()
    if notify_env:
        recipients = [addr.strip() for addr in notify_env.split(",") if addr.strip()]
    else:
        recipients = [DEFAULT_NOTIFY_EMAIL]
    if not recipients:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, app_password)
        smtp.send_message(msg)


async def is_logged_in(page) -> bool:
    login_button = page.get_by_role("button", name=re.compile(r"^Login$", re.IGNORECASE))
    deadline = time.monotonic() + 30

    # The redesigned board still has a table, but table presence is no longer a
    # reliable authentication signal. Prefer Auth0 browser state and use the
    # visible Login button as an explicit logged-out signal.
    while time.monotonic() < deadline:
        try:
            if await login_button.count() and await login_button.first.is_visible():
                return False
        except Exception:
            pass

        try:
            auth_storage = await page.evaluate(
                """() => {
                    const keys = [...Object.keys(localStorage), ...Object.keys(sessionStorage)];
                    return keys.some(k => k.toLowerCase().includes('auth0'));
                }"""
            )
            if auth_storage:
                return True
        except Exception:
            pass

        await page.wait_for_timeout(250)
    return False


def storage_state_auth_expires_at(path: str) -> float | None:
    try:
        with open(path, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, ValueError, TypeError):
        return None

    expirations = []
    for origin in state.get("origins", []):
        for item in origin.get("localStorage", []):
            if "auth0spajs" not in str(item.get("name") or ""):
                continue
            try:
                payload = json.loads(item.get("value") or "{}")
                expires_at = float(payload.get("expiresAt"))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if expires_at > 1_000_000_000_000:
                expires_at /= 1000
            expirations.append(expires_at)

    return min(expirations) if expirations else None


def storage_state_needs_refresh(
    path: str,
    *,
    now: float | None = None,
    minimum_ttl_seconds: int = 3600,
) -> bool:
    expires_at = storage_state_auth_expires_at(path)
    if expires_at is None:
        return True
    current_time = time.time() if now is None else now
    return expires_at <= current_time + max(0, minimum_ttl_seconds)


PROPSCASH_API_HEADERS = ["authorization", "accept", "content-type", "origin", "referer", "user-agent"]
PROPSCASH_NORMALIZED_HEADERS = ["PLAYER", "L", "L5", "L10", "L20", "H2H", "SZN", "O", "U"]


def _dynamic_hitrates_request_matches(request, league_key: str, prop_value: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(request.url)
        if parsed.netloc.lower() != "api.props.cash":
            return False
        expected_path = f"/{league_key.lower()}/dynamic-hitrates"
        if parsed.path.lower() != expected_path:
            return False
        query = urllib.parse.parse_qs(parsed.query)
        requested_prop = (query.get("propType") or [""])[0]
        return requested_prop == prop_value
    except Exception:
        return False


async def _api_headers_from_browser_request(request) -> dict:
    headers = await request.all_headers()
    allowed = set(PROPSCASH_API_HEADERS)
    result = {
        key: value
        for key, value in headers.items()
        if key.lower() in allowed or key.lower().startswith("x-")
    }
    if not result.get("authorization"):
        # Header names from Playwright are normally lowercase, but keep this
        # defensive in case that behavior changes.
        auth = next((v for k, v in headers.items() if k.lower() == "authorization"), None)
        if auth:
            result["authorization"] = auth
    if not result.get("authorization"):
        raise RuntimeError("PropsCash API request did not contain an Authorization bearer header")
    return result


def _build_dynamic_hitrates_url(
    template_url: str,
    *,
    prop_value: str,
    side: str,
    page_number: int,
    limit: int = 50,
) -> str:
    parsed = urllib.parse.urlsplit(template_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "overUnder": side,
            "range": "l10",
            "page": str(page_number),
            "limit": str(limit),
            "sortBy": "l10Rate",
            "sortOrder": "desc",
            "games": "l10",
            "propType": prop_value,
        }
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


async def _fetch_propscash_json(context, url: str, headers: dict) -> dict:
    response = await context.request.get(url, headers=headers, timeout=60000)
    if not response.ok:
        raise RuntimeError(f"PropsCash API returned HTTP {response.status} for {urllib.parse.urlsplit(url).path}")
    try:
        payload = await response.json()
    except Exception as exc:
        raise RuntimeError("PropsCash API returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("PropsCash API returned an unexpected JSON response shape")
    return payload


async def _fetch_dynamic_hitrates_pages(
    context,
    template_url: str,
    headers: dict,
    *,
    prop_value: str,
    side: str,
) -> list[dict]:
    all_items = []
    page_number = 1
    max_pages = int(os.environ.get("PROPSCASH_MAX_API_PAGES", "100"))

    while page_number <= max_pages:
        api_url = _build_dynamic_hitrates_url(
            template_url,
            prop_value=prop_value,
            side=side,
            page_number=page_number,
        )
        payload = await _fetch_propscash_json(context, api_url, headers)
        items = payload.get("data") or []
        if not isinstance(items, list):
            raise RuntimeError("PropsCash dynamic-hitrates 'data' field is not a list")
        all_items.extend(item for item in items if isinstance(item, dict))

        pagination = payload.get("pagination") or {}
        has_next = bool(pagination.get("hasNextPage")) if isinstance(pagination, dict) else False
        if not has_next:
            break
        if not items:
            raise RuntimeError("PropsCash pagination reported another page but returned no data")
        page_number += 1
    else:
        raise RuntimeError(f"PropsCash pagination exceeded safety limit of {max_pages} pages")

    return all_items


def _item_identity(item: dict, *, include_line: bool = True) -> tuple:
    player_key = item.get("id") or item.get("playerId") or item.get("name") or ""
    parts = [str(player_key), str(item.get("gameId") or ""), str(item.get("prop") or "")]
    if include_line:
        parts.append(str(item.get("line") if item.get("line") is not None else ""))
    return tuple(parts)


def _percent_value(item: dict, label: str, fallback_key: str) -> str:
    value = None
    stats = item.get("preCalculatedStats") or {}
    if isinstance(stats, dict):
        bucket = stats.get(label) or {}
        if isinstance(bucket, dict):
            value = bucket.get("value")
    if value is None:
        value = item.get(fallback_key)
    if value is None or value == "":
        return ""
    try:
        numeric = float(value)
        value_text = str(int(numeric)) if numeric.is_integer() else str(numeric)
    except (TypeError, ValueError):
        value_text = str(value).strip().rstrip("%")
    return f"{value_text}%" if value_text else ""


def _odds_value(item: dict | None) -> str:
    if not item:
        return ""
    value = item.get("odds")
    return "" if value is None else str(value).strip()


def _normalize_dynamic_hitrates(over_items: list[dict], under_items: list[dict]) -> dict:
    under_full = {_item_identity(item, include_line=True): item for item in under_items}
    under_base = {}
    for item in under_items:
        under_base.setdefault(_item_identity(item, include_line=False), item)

    rows = []
    for item in over_items:
        under_item = under_full.get(_item_identity(item, include_line=True))
        if under_item is None:
            under_item = under_base.get(_item_identity(item, include_line=False))

        line_value = item.get("line")
        row = {
            "PLAYER": str(item.get("name") or "").strip(),
            "L": "" if line_value is None else str(line_value).strip(),
            "L5": _percent_value(item, "L5", "l5Rate"),
            "L10": _percent_value(item, "L10", "l10Rate"),
            "L20": _percent_value(item, "L20", "l20Rate"),
            "H2H": _percent_value(item, "H2H", "h2hRate"),
            "SZN": _percent_value(item, "SZN", "currentSeason"),
            "O": _odds_value(item),
            "U": _odds_value(under_item),
        }
        if row["PLAYER"]:
            rows.append(row)

    return {"headers": list(PROPSCASH_NORMALIZED_HEADERS), "rows": rows}


async def scrape_prop_from_api(page, url: str, league_key: str, prop_value: str) -> dict:
    request_info = None
    try:
        async with page.expect_request(
            lambda request: _dynamic_hitrates_request_matches(request, league_key, prop_value),
            timeout=45000,
        ) as pending_request:
            await goto_with_retry(page, url)
        request_info = await pending_request.value
    except Exception as exc:
        login_button = page.get_by_role("button", name=re.compile(r"^Login$", re.IGNORECASE))
        if await login_button.count() and await login_button.first.is_visible():
            raise RuntimeError("PropsCash session expired while loading prop data") from exc
        raise RuntimeError(
            f"Did not observe PropsCash dynamic-hitrates request for {league_key}/{prop_value}"
        ) from exc

    api_headers = await _api_headers_from_browser_request(request_info)
    template_url = request_info.url
    context = page.context

    over_items = await _fetch_dynamic_hitrates_pages(
        context,
        template_url,
        api_headers,
        prop_value=prop_value,
        side="over",
    )

    try:
        under_items = await _fetch_dynamic_hitrates_pages(
            context,
            template_url,
            api_headers,
            prop_value=prop_value,
            side="under",
        )
    except Exception as exc:
        # Overs can still be useful if the under-side endpoint temporarily fails.
        print(f"[scrape] under-side API failed for {league_key}/{prop_value}: {exc}")
        under_items = []

    normalized = _normalize_dynamic_hitrates(over_items, under_items)
    print(
        f"[scrape] {league_key.upper()} {prop_value}: "
        f"{len(over_items)} over rows, {len(under_items)} under rows, "
        f"{len(normalized['rows'])} normalized rows"
    )
    return normalized


async def goto_with_retry(page, url: str, attempts: int = 3, timeout_ms: int = 90000) -> None:
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except Exception as exc:
            if attempt >= attempts:
                raise
            print(f"Page.goto failed ({attempt}/{attempts}) for {url}: {exc}")
            await page.wait_for_timeout(2000)


async def visit_league_props(page, cfg: dict, league_key: str) -> list[dict]:
    league = cfg["leagues"][league_key]
    results = []
    for prop in league["props"]:
        url = prop_url(cfg, league_key, prop["value"])
        api_data = None
        for attempt in range(1, 3):
            try:
                api_data = await scrape_prop_from_api(page, url, league_key, prop["value"])
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                print(
                    f"[scrape] API scrape failed for {league_key}/{prop['value']} "
                    f"on attempt {attempt}/2; retrying: {exc}"
                )
                try:
                    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    pass
                await page.wait_for_timeout(1500)

        payload = {
            "league": league_key,
            "prop": prop["value"],
            "url": url,
            **api_data,
        }
        # Avoid dumping bearer tokens or raw authenticated API requests.
        print(
            json.dumps(
                {
                    "league": payload["league"],
                    "prop": payload["prop"],
                    "url": payload["url"],
                    "rows": len(payload.get("rows", [])),
                },
                ensure_ascii=True,
            )
        )
        results.append(payload)

    return results


async def main() -> None:
    load_env()
    run_start = datetime.now().isoformat(timespec="seconds")
    print(f"=== RUN START {run_start} ===")
    run_status = "unknown"
    run_error = None
    run_id = db_insert_run_start(print)
    storage_state = STORAGE_STATE_PATH if os.path.exists(STORAGE_STATE_PATH) else None
    auth_min_ttl = int(os.environ.get("PROPSCASH_AUTH_MIN_TTL_SECONDS", "3600"))
    if storage_state and storage_state_needs_refresh(
        storage_state,
        minimum_ttl_seconds=auth_min_ttl,
    ):
        print("[auth] Saved PropsCash session is expired or near expiry; refreshing login before scrape.")
        storage_state = None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()
        await goto_with_retry(page, BASE_URL)

        try:
            all_results = []
            if await is_logged_in(page):
                print("Already logged in.")
                maybe_send_email(
                    "PropsCash: login already active",
                    "Session is already logged in; scraping will proceed.",
                )
            else:
                print("Not logged in. Running login flow...")
                await context.close()
                await browser.close()
                try:
                    await login()
                except Exception as exc:
                    maybe_send_email(
                        "PropsCash: login failed",
                        f"Login failed with error: {exc}",
                    )
                    raise
                maybe_send_email(
                    "PropsCash: login success",
                    "Login completed successfully; scraping will proceed.",
                )
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(storage_state=STORAGE_STATE_PATH)
                page = await context.new_page()
                await page.goto(BASE_URL, wait_until="domcontentloaded")

            cfg = load_config()
            scrape_leagues = active_scrape_leagues(cfg, print)
            if not scrape_leagues:
                print("[calendar] No active PropsCash leagues; writing empty outputs.")
            for league_key in scrape_leagues:
                all_results.extend(await visit_league_props(page, cfg, league_key))

            with open(RESULTS_PATH, "w", encoding="utf-8") as results_file:
                json.dump(all_results, results_file, ensure_ascii=True, indent=2)

            fieldnames = ["league", "prop", "url"]
            for payload in all_results:
                for header in payload.get("headers", []):
                    if header and header not in fieldnames:
                        fieldnames.append(header)

            with open(RESULTS_CSV_PATH, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                for payload in all_results:
                    for row in payload.get("rows", []):
                        record = {"league": payload["league"], "prop": payload["prop"], "url": payload["url"]}
                        record.update({key: value for key, value in row.items() if key})
                        writer.writerow(record)
            db_insert_propscash_rows(print, run_id, all_results)

            rolling_full_rows = build_rolling_prop_rows_full(all_results)
            rolling_rows = build_rolling_prop_rows(all_results)
            rolling_headers = [
                "Sport",
                "Game Date",
                "Event ID",
                "Stat Category",
                "Player Name",
                "Over/Under",
                "Line",
                "Odds",
                "Home Team",
                "Away Team",
                "Hit %",
            ]
            with open(ROLLING_PROP_LIST_FULL_CSV_PATH, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=rolling_headers)
                writer.writeheader()
                for row in rolling_full_rows:
                    writer.writerow(row)
            with open(ROLLING_PROP_LIST_CSV_PATH, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=rolling_headers)
                writer.writeheader()
                for row in rolling_rows:
                    writer.writerow(row)

            l10_rows = build_l10_rankings(rolling_rows)
            l10_headers = ["Stat", "OverUnder", "Player Name", "Odds", "Line", "HitRateDecimal"]
            with open(L10_RANKINGS_CSV_PATH, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=l10_headers)
                writer.writeheader()
                for row in l10_rows:
                    writer.writerow(row)

            sheet_id = os.environ.get("GOOGLE_SHEET_ID")
            sa_json_path = os.environ.get("GOOGLE_SA_JSON")
            if sheet_id:
                sheet_id = sheet_id.strip()
            if sa_json_path:
                sa_json_path = sa_json_path.strip()
            if sheet_id and sa_json_path:
                upload_csv_to_sheet(ROLLING_PROP_LIST_CSV_PATH, sheet_id, "Rolling Prop List", sa_json_path)
                upload_csv_to_sheet(L10_RANKINGS_CSV_PATH, sheet_id, "L10Rankings", sa_json_path)
                print("Sheet uploads completed.")
                missing_targets = {"nfl": {}, "nba": {}, "wnba": {}, "nhl": {}, "mlb": {}}
                for row in rolling_rows:
                    sport = str(row.get("Sport", "")).upper().strip()
                    name = str(row.get("Player Name", "")).strip()
                    if not name:
                        continue
                    key = {"NFL": "nfl", "NBA": "nba", "WNBA": "wnba", "NHL": "nhl", "MLB": "mlb"}.get(sport)
                    if key:
                        lookup_key = clean_name(normalize_display_name(name))
                        missing_targets[key][lookup_key] = name
                try:
                    missing_updates = await update_missing_player_ids_and_images(
                        sa_json_path, target_names=missing_targets
                    )
                except Exception as exc:
                    print(f"[missing-ids] non-fatal error; continuing to PNG export: {exc}")
                    missing_updates = {}
                if missing_updates:
                    added_lines = []
                    for league_key, names in missing_updates.items():
                        league_label = league_key.upper()
                        added_lines.append(f"{league_label}: {', '.join(names)}")
                    body = "Added missing ESPN player IDs and images:\n\n" + "\n".join(added_lines)
                    maybe_send_email("PropsCash: missing IDs updated", body)
                maybe_send_email(
                    "PropsCash: scraper complete",
                    "Scrape finished and outputs were generated. PNG export starting.",
                )
                run_status = "success"
                db_mark_run_data_ready(print, run_id)
                if os.environ.get("ENABLE_PNG_EXPORT", "1") == "1":
                    try:
                        slide_groups = build_slide_groups(rolling_rows, sa_json_path)
                        png_summary = generate_pngs_from_slides(slide_groups, sa_json_path)
                    except Exception as exc:
                        run_error = f"PNG export failed after successful scrape: {exc}"
                        print(f"[png] {run_error}")
                        maybe_send_email(
                            "PropsCash: PNG export failed",
                            "Scraping and data uploads completed successfully, but PNG export "
                            f"failed with error: {exc}",
                        )
                    else:
                        folder_lines = []
                        for sport, folder_id in png_summary.get("folders", {}).items():
                            folder_lines.append(
                                f"{sport}: https://drive.google.com/drive/folders/{folder_id}"
                            )
                        if folder_lines:
                            body = "PNG export completed.\n\nFolders:\n" + "\n".join(folder_lines)
                        else:
                            body = "PNG export completed."
                        body += f"\n\nPNGs created: {png_summary.get('png_count', 0)}"
                        maybe_send_email("PropsCash: PNG export complete", body)
            run_status = "success"
        except Exception as exc:
            run_status = "failed"
            run_error = str(exc)
            maybe_send_email(
                "PropsCash: scraper failed",
                f"Scraper failed with error: {exc}",
            )
            raise
        finally:
            run_end = datetime.now().isoformat(timespec="seconds")
            print(f"=== RUN END {run_end} status={run_status} ===")
            db_update_run_finish(print, run_id, run_status, run_error)
            if run_status == "success" and run_id:
                try:
                    from aws_export import queue_and_start_export

                    queue_and_start_export(run_id, log=print)
                except Exception as exc:
                    print(
                        f"[aws-export] non-fatal integration failure for run {run_id}: "
                        f"{type(exc).__name__}"
                    )
            await context.close()
            await browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fill-missing-ids":
        load_env()
        sport_filter = sys.argv[2].upper().strip() if len(sys.argv) > 2 else ""
        sa_json_path = os.environ.get("GOOGLE_SA_JSON")
        if sa_json_path:
            sa_json_path = sa_json_path.strip()
        if not sa_json_path:
            raise RuntimeError("GOOGLE_SA_JSON is not set.")

        async def _run_missing_ids() -> None:
            target_names = {"nfl": {}, "nba": {}, "wnba": {}, "nhl": {}, "mlb": {}}
            if os.path.exists(ROLLING_PROP_LIST_CSV_PATH):
                with open(ROLLING_PROP_LIST_CSV_PATH, "r", encoding="utf-8", newline="") as csv_file:
                    reader = csv.DictReader(csv_file)
                    for row in reader:
                        sport = str(row.get("Sport", "")).upper().strip()
                        if sport_filter and sport != sport_filter:
                            continue
                        name = str(row.get("Player Name", "")).strip()
                        if not name:
                            continue
                        key = {"NFL": "nfl", "NBA": "nba", "WNBA": "wnba", "NHL": "nhl", "MLB": "mlb"}.get(sport)
                        if key:
                            lookup_key = clean_name(normalize_display_name(name))
                            target_names[key][lookup_key] = name
            updates = await update_missing_player_ids_and_images(
                sa_json_path, target_names=target_names
            )
            if updates:
                lines = []
                for league_key, names in updates.items():
                    lines.append(f"{league_key.upper()}: {', '.join(names)}")
                body = "Added missing ESPN player IDs and images:\n\n" + "\n".join(lines)
                maybe_send_email("PropsCash: missing IDs updated", body)
                print("[missing-ids] email sent")
                print(body)
            else:
                print("No missing IDs/images found.")

        asyncio.run(_run_missing_ids())
    elif len(sys.argv) > 1 and sys.argv[1] == "generate-pngs":
        load_env()
        sport_filter = sys.argv[2].upper().strip() if len(sys.argv) > 2 else ""
        sa_json_path = os.environ.get("GOOGLE_SA_JSON")
        if sa_json_path:
            sa_json_path = sa_json_path.strip()
        if not sa_json_path:
            raise RuntimeError("GOOGLE_SA_JSON is not set.")
        if not os.path.exists(ROLLING_PROP_LIST_CSV_PATH):
            raise RuntimeError(f"{ROLLING_PROP_LIST_CSV_PATH} does not exist.")

        with open(ROLLING_PROP_LIST_CSV_PATH, "r", encoding="utf-8", newline="") as csv_file:
            rolling_rows = list(csv.DictReader(csv_file))
        if sport_filter:
            rolling_rows = [
                row
                for row in rolling_rows
                if str(row.get("Sport", "")).upper().strip() == sport_filter
            ]
        if not rolling_rows:
            raise RuntimeError(f"No rolling rows found for {sport_filter or 'all sports'}.")

        slide_groups = build_slide_groups(rolling_rows, sa_json_path)
        if sport_filter:
            slide_groups = {sport_filter: slide_groups.get(sport_filter, {})}
        png_summary = generate_pngs_from_slides(slide_groups, sa_json_path)
        print(f"PNG export completed. PNGs created: {png_summary.get('png_count', 0)}")
    else:
        asyncio.run(main())

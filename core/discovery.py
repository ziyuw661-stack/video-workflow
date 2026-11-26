"""Personal YouTube metadata and snapshots. No video downloads."""
import csv
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

UTC = dt.timezone.utc
API = "https://www.googleapis.com/youtube/v3/"


def stamp():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def api(endpoint, key, **params):
    for attempt in range(4):
        try:
            with urlopen(API + endpoint + "?" + urlencode({"key": key, **params}), timeout=30) as response:
                return json.load(response).get("items", [])
        except HTTPError as error:
            if error.code not in (500, 502, 503, 504) or attempt == 3:
                raise ValueError(f"YouTube {endpoint} HTTP {error.code}; check permission or quota") from None
        except (URLError, TimeoutError):
            if attempt == 3:
                raise ValueError(f"YouTube {endpoint} network failure") from None
        time.sleep(2 ** attempt)
    raise AssertionError


def youtube(profile, key):
    region = profile["region"]
    age = dt.datetime.now(UTC) - dt.timedelta(days=profile.get("lookback_days", 90))
    keywords = profile.get("keywords", [])
    channels = profile.get("channel_ids", [])
    found = {}
    for keyword in keywords:
        for row in api("search", key, part="snippet", q=keyword, type="video", regionCode=region,
                       maxResults=profile.get("collect_limit", 8), publishedAfter=age.isoformat(timespec="seconds")):
            found.setdefault(row["id"]["videoId"], set()).add(keyword)
    for channel in channels:
        for row in api("channels", key, part="contentDetails", id=channel):
            playlist = row["contentDetails"]["relatedPlaylists"]["uploads"]
            for item in api("playlistItems", key, part="contentDetails", playlistId=playlist,
                            maxResults=profile.get("collect_limit", 8)):
                found.setdefault(item["contentDetails"]["videoId"], set()).add("channel:" + channel)
    trends = {}
    if profile.get("most_popular"):
        for item in api("videos", key, part="snippet,statistics,contentDetails", chart="mostPopular",
                        regionCode=region, maxResults=profile.get("collect_limit", 8)):
            trends[item["id"]] = item
            found.setdefault(item["id"], set()).add("mostPopular")
    ids = [key for key in found if key not in trends]
    for i in range(0, len(ids), 50):
        for item in api("videos", key, part="snippet,statistics,contentDetails", id=",".join(ids[i:i+50])):
            trends[item["id"]] = item
    out = []
    for identity, item in trends.items():
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        out.append(dict(platform="youtube", video_id=identity, title=snippet["title"],
                        channel=snippet["channelTitle"], channel_id=snippet["channelId"],
                        url="https://www.youtube.com/watch?v=" + identity, published=snippet.get("publishedAt"),
                        duration=item.get("contentDetails", {}).get("duration"), keywords=sorted(found[identity]),
                        views=_num(stats.get("viewCount")), likes=_num(stats.get("likeCount")),
                        comments=_num(stats.get("commentCount"))))
    return out


def _num(value):
    return int(value) if value not in (None, "", "unknown") and str(value).isdigit() else None


def get_db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            platform TEXT, video_id TEXT, first_seen TEXT, updated_at TEXT, payload TEXT,
            state TEXT DEFAULT 'unreviewed', score REAL, confidence REAL, production_id TEXT,
            PRIMARY KEY(platform, video_id));
        CREATE TABLE IF NOT EXISTS snapshots (
            platform TEXT, video_id TEXT, collected_at TEXT, views INTEGER, likes INTEGER, comments INTEGER,
            PRIMARY KEY(platform, video_id, collected_at));
    """)
    return db


def ingest(db, rows):
    with db:
        now = stamp()
        for row in rows:
            if not row.get("video_id") or not row.get("platform") or not row.get("url"):
                continue
            key = (row["platform"], row["video_id"])
            db.execute("""INSERT INTO topics(platform,video_id,first_seen,updated_at,payload)
                VALUES(?,?,?,?,?) ON CONFLICT(platform,video_id) DO UPDATE
                SET updated_at=excluded.updated_at,payload=excluded.payload""", (*key, now, now, json.dumps(row, ensure_ascii=False)))
            db.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?)",
                       (*key, now, _num(row.get("views")), _num(row.get("likes")), _num(row.get("comments"))))


WEIGHTS = {"match": .30, "relative": .25, "growth": .15, "recency": .10, "originality": .10, "feasible": .10}


def assess(db, reviews, threshold=70):
    with db:
        for review in reviews:
            key = (review["platform"], review["video_id"])
            values = {k: review.get(k) for k in WEIGHTS}
            if any(v is not None and (type(v) not in (int, float) or not 0 <= v <= 100) for v in values.values()):
                raise ValueError("Topic scores must be between 0 and 100")
            coverage = sum(WEIGHTS[k] for k, v in values.items() if v is not None)
            score = sum(WEIGHTS[k] * v for k, v in values.items() if v is not None) / coverage if coverage else None
            good = (review.get("source_allowed") is True and (values["match"] or 0) >= 60
                    and values["originality"] is not None and values["feasible"] is not None
                    and coverage >= .5 and score is not None and score >= threshold
                    and not review.get("near_duplicate"))
            cur = db.execute("""UPDATE topics SET state=CASE WHEN state='produced' THEN state ELSE ? END,
                              score=?,confidence=? WHERE platform=? AND video_id=?""",
                             ("qualified" if good else "needs_review", score, coverage, *key))
            if cur.rowcount != 1:
                raise ValueError("Topic review does not match a collected ID")


def get_topic(db):
    row = db.execute("""SELECT * FROM topics WHERE state='qualified'
                         ORDER BY score DESC,updated_at DESC,platform,video_id LIMIT 1""").fetchone()
    return {**json.loads(row["payload"]), "score": row["score"], "confidence": row["confidence"]} if row else None


def export(db, folder, date):
    from openpyxl import Workbook
    folder.mkdir(parents=True, exist_ok=True)
    all_rows = list(db.execute("SELECT * FROM topics ORDER BY first_seen DESC,score DESC,video_id"))
    by_date = lambda row: dt.datetime.fromisoformat(row["first_seen"]).astimezone(date.tzinfo).date() == date.date()
    subsets = {"选题总库": all_rows, "今日新增": [r for r in all_rows if by_date(r)],
               "今日推荐": sorted((r for r in all_rows if r["state"] == "qualified"),
                                key=lambda row: row["score"], reverse=True), "已制作": [r for r in all_rows if r["state"] == "produced"]}
    fields = ("platform", "video_id", "title", "channel", "url", "published", "duration", "views", "likes", "comments",
              "first_seen", "updated_at", "keywords", "score", "confidence", "state", "production_id")
    for filename, rows in subsets.items():
        wb = Workbook()
        ws = wb.active
        ws.append(fields)
        ws.freeze_panes = "A2"
        for row in rows:
            payload = json.loads(row["payload"])
            meta = dict(row)
            values = [meta.get(key, payload.get(key)) for key in fields]
            ws.append([", ".join(v) if isinstance(v, list) else v for v in values])
            for cell in ws[ws.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"  # Untrusted video titles never become formulas.
        ws.auto_filter.ref = ws.dimensions
        descriptor, tmp = tempfile.mkstemp(dir=folder, suffix=".xlsx")
        os.close(descriptor)
        try:
            wb.save(tmp)
            os.replace(tmp, folder / (filename + ".xlsx"))
        finally:
            Path(tmp).unlink(missing_ok=True)

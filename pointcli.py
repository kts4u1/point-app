#!/usr/bin/env python3
"""앱테크 출석/포인트 체크리스트 CLI.

자동으로 클릭하지 않고, 오늘 할 일을 알려주고 사용자가 직접 한 뒤 기록한다.
데이터는 SQLite(기본 ~/.pointcli.db, POINTCLI_DB 환경변수로 변경)에 저장한다.
"""
import argparse
import os
import sqlite3
import sys
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urlparse

DB_PATH = os.environ.get("POINTCLI_DB", os.path.expanduser("~/.pointcli.db"))

# 웹 검색으로 확인한 서비스. 적립 조건/금액은 앱 공지에서 직접 확인할 것.
SEED = [
    # name, task, est_won_per_day, expire_days(0=미확인), note
    ("토스", "만보기 적립(1만보 기준 하루 최대 약 140원)", 140, 0, ""),
    ("캐시업", "출석체크", 0, 0, "네이버페이/상품권 교환"),
    ("지니어트", "출석/걷기/기록으로 젤리 적립", 0, 31, "미사용 젤리는 다음 달 소멸"),
    ("리워드플랫폼", "출석체크 및 미션", 0, 0, "출금 조건 미확인"),
    ("캐시워크", "걸음 수 적립(하루 1만보까지)", 0, 365, "[미검증] 유효기간 1년은 블로그 1건 기준, 앱 약관 확인"),
    ("네이버페이", "출석/이벤트 포인트", 0, 0, "소멸 규정 미확인, 적립 내역 화면에서 확인"),
]

# 실제로 열리고 robots.txt가 허용함을 확인한 피드(2026-10-09). 사이트 약관은 직접 확인할 것.
SEED_FEEDS = [
    "https://www.ppomppu.co.kr/rss.php?id=coupon",  # 뽐뿌 쿠폰/앱테크성 글
    "https://www.ppomppu.co.kr/rss.php?id=event",  # 뽐뿌 이벤트 게시판
]


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS service(
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            task TEXT NOT NULL DEFAULT '출석체크',
            est_won INTEGER NOT NULL DEFAULT 0,
            expire_days INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS log(
            id INTEGER PRIMARY KEY,
            service_id INTEGER NOT NULL REFERENCES service(id),
            day TEXT NOT NULL,
            won INTEGER NOT NULL DEFAULT 0,
            UNIQUE(service_id, day));
        CREATE TABLE IF NOT EXISTS feed(
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS event(
            id INTEGER PRIMARY KEY,
            feed_id INTEGER NOT NULL REFERENCES feed(id),
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            seen TEXT NOT NULL);
        """
    )
    cols = {r["name"] for r in con.execute("PRAGMA table_info(service)")}
    if "expire_days" not in cols:  # 기존 DB 마이그레이션
        con.execute("ALTER TABLE service ADD COLUMN expire_days INTEGER NOT NULL DEFAULT 0")
    return con


def find(con, name):
    row = con.execute("SELECT * FROM service WHERE name=?", (name,)).fetchone()
    if not row:
        sys.exit(f"등록되지 않은 서비스: {name}")
    return row


def cmd_init(con, a):
    n = 0
    for name, task, est, exp, note in SEED:
        cur = con.execute(
            "INSERT OR IGNORE INTO service(name,task,est_won,expire_days,note) "
            "VALUES(?,?,?,?,?)",
            (name, task, est, exp, note),
        )
        n += cur.rowcount
    for url in SEED_FEEDS:
        con.execute("INSERT OR IGNORE INTO feed(url) VALUES(?)", (url,))
    con.commit()
    print(f"{n}개 서비스 추가 (이미 있던 항목은 유지), 기본 피드 {len(SEED_FEEDS)}개 등록")


def cmd_add(con, a):
    try:
        con.execute(
            "INSERT INTO service(name,task,est_won,expire_days,note) VALUES(?,?,?,?,?)",
            (a.name, a.task, a.est, a.expire_days, a.note),
        )
    except sqlite3.IntegrityError:
        sys.exit(f"이미 있는 서비스: {a.name}")
    con.commit()
    print(f"추가: {a.name}")


def cmd_remove(con, a):
    s = find(con, a.name)
    con.execute("UPDATE service SET active=0 WHERE id=?", (s["id"],))
    con.commit()
    print(f"비활성화: {a.name}")


def cmd_today(con, a):
    today = date.today().isoformat()
    rows = con.execute(
        """SELECT s.*, (SELECT 1 FROM log l WHERE l.service_id=s.id AND l.day=?) AS done
           FROM service s WHERE s.active=1 ORDER BY s.est_won DESC, s.name""",
        (today,),
    ).fetchall()
    if not rows:
        print("등록된 서비스가 없습니다. `pointcli.py init` 또는 `add`를 실행하세요.")
        return
    pending = [r for r in rows if not r["done"]]
    print(f"[{today}] 남은 일 {len(pending)} / 전체 {len(rows)}")
    for r in rows:
        mark = "x" if r["done"] else " "
        extra = f"  ~{r['est_won']}원" if r["est_won"] else ""
        note = f"  ({r['note']})" if r["note"] else ""
        print(f" [{mark}] {r['name']}: {r['task']}{extra}{note}")


def cmd_done(con, a):
    s = find(con, a.name)
    day = a.date or date.today().isoformat()
    con.execute(
        "INSERT INTO log(service_id,day,won) VALUES(?,?,?) "
        "ON CONFLICT(service_id,day) DO UPDATE SET won=excluded.won",
        (s["id"], day, a.won),
    )
    con.commit()
    print(f"기록: {a.name} {day} +{a.won}원")


def cmd_stats(con, a):
    since = (date.today() - timedelta(days=a.days - 1)).isoformat()
    rows = con.execute(
        """SELECT s.name, COUNT(l.id) AS days, COALESCE(SUM(l.won),0) AS won
           FROM service s LEFT JOIN log l ON l.service_id=s.id AND l.day>=?
           WHERE s.active=1 GROUP BY s.id ORDER BY won DESC, days DESC""",
        (since,),
    ).fetchall()
    print(f"최근 {a.days}일")
    total = 0
    for r in rows:
        total += r["won"]
        print(f"  {r['name']}: {r['days']}일, {r['won']}원")
    print(f"합계: {total}원")


def cmd_edit(con, a):
    s = find(con, a.name)
    fields = {"task": a.task, "est_won": a.est, "expire_days": a.expire_days, "note": a.note}
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        sys.exit("바꿀 항목(--task/--est/--expire-days/--note)을 지정하세요.")
    sets = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE service SET {sets} WHERE id=?", (*fields.values(), s["id"]))
    con.commit()
    print(f"수정: {a.name}")


def expiring_rows(con, within, today=None):
    """적립일+유효기간이 오늘~within일 사이인 적립 건을 만료일 순으로 반환."""
    today = today or date.today()
    out = []
    rows = con.execute(
        """SELECT s.name, s.expire_days, l.day, l.won FROM log l
           JOIN service s ON s.id=l.service_id
           WHERE s.active=1 AND s.expire_days>0 AND l.won>0"""
    ).fetchall()
    for r in rows:
        exp = date.fromisoformat(r["day"]) + timedelta(days=r["expire_days"])
        left = (exp - today).days
        if 0 <= left <= within:
            out.append((exp, left, r["name"], r["won"]))
    return sorted(out)


def cmd_expiring(con, a):
    rows = expiring_rows(con, a.within)
    if not rows:
        print(f"{a.within}일 내 소멸 예정 적립금 없음 (유효기간을 모르는 서비스는 제외)")
        return
    for exp, left, name, won in rows:
        print(f"  {exp} (D-{left}) {name}: {won}원")
    print(f"합계: {sum(r[3] for r in rows)}원")


def parse_feed(xml_text):
    """RSS 2.0 / Atom에서 (title, link) 목록을 뽑는다."""
    root = ET.fromstring(xml_text)
    items = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = ""
        for c in el:
            t = c.tag.rsplit("}", 1)[-1]
            if t == "title":
                title = (c.text or "").strip()
            elif t == "link":
                link = (c.get("href") or c.text or "").strip()
        if title and link:
            items.append((title, link))
    return items


UA = "pointcli/0.1 (personal event checker)"


def robots_allows(url):
    """robots.txt를 우리 User-Agent로 받아 확인한다.
    404 등은 규칙 없음(허용), 401/403/5xx/연결실패는 보수적으로 불허."""
    u = urlparse(url)
    robots = f"{u.scheme}://{u.netloc}/robots.txt"
    req = urllib.request.Request(robots, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code not in (401, 403) and e.code < 500
    except OSError:
        return False
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(UA, url)


def fetch(url):
    """robots.txt가 허용할 때만 가져온다. 거부되면 PermissionError."""
    if not robots_allows(url):
        raise PermissionError("robots.txt가 수집을 허용하지 않음")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def cmd_feed(con, a):
    if a.action == "add":
        if not a.url:
            sys.exit("추가할 피드 URL을 지정하세요.")
        try:
            con.execute("INSERT INTO feed(url) VALUES(?)", (a.url,))
        except sqlite3.IntegrityError:
            sys.exit("이미 등록된 피드")
        con.commit()
        print(f"피드 추가: {a.url}")
    else:
        for r in con.execute("SELECT url FROM feed ORDER BY id"):
            print(r["url"])


KEYWORDS = ("출석", "이벤트", "포인트", "적립", "쿠폰", "리워드")


def collect(con, fetcher=fetch, keywords=KEYWORDS):
    new = 0
    for f in con.execute("SELECT * FROM feed").fetchall():
        try:
            items = parse_feed(fetcher(f["url"]))
        except Exception as e:  # 피드 하나가 실패해도 나머지는 계속
            print(f"! {f['url']}: {e}", file=sys.stderr)
            continue
        for title, link in items:
            if keywords and not any(k in title for k in keywords):
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO event(feed_id,title,link,seen) VALUES(?,?,?,?)",
                (f["id"], title, link, date.today().isoformat()),
            )
            new += cur.rowcount
    con.commit()
    return new


def cmd_collect(con, a):
    print(f"새 이벤트 {collect(con)}건")


def cmd_export_events(con, a):
    """앱(app/index.html)이 읽는 events.json을 만든다."""
    import json

    rows = con.execute(
        "SELECT title, link, seen FROM event ORDER BY id DESC LIMIT ?", (a.limit,)
    ).fetchall()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=1)
    print(f"{len(rows)}건 -> {a.out}")


def cmd_events(con, a):
    rows = con.execute(
        "SELECT title, link, seen FROM event ORDER BY id DESC LIMIT ?", (a.limit,)
    ).fetchall()
    if not rows:
        print("수집된 이벤트 없음. `feed add URL` 후 `collect`를 실행하세요.")
    for r in rows:
        print(f"  [{r['seen']}] {r['title']}\n      {r['link']}")


def morning_report(con, within=14, limit=10, fetcher=fetch):
    """수집 -> 오늘 할 일 -> 소멸 임박 -> 새 이벤트를 한 텍스트로 만든다."""
    import contextlib
    import io

    last = con.execute("SELECT COALESCE(MAX(id),0) FROM event").fetchone()[0]
    collect(con, fetcher=fetcher)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_today(con, None)
        print()
        print(f"[소멸 임박 {within}일 이내]")
        cmd_expiring(con, argparse.Namespace(within=within))
        new = con.execute(
            "SELECT title, link FROM event WHERE id>? ORDER BY id DESC LIMIT ?",
            (last, limit),
        ).fetchall()
        print()
        print(f"[새 이벤트 {len(new)}건]")
        for r in new:
            print(f"  {r['title']}\n      {r['link']}")
    return buf.getvalue()


def send_telegram(text, token, chat_id):
    import json

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15).read()


def cmd_morning(con, a):
    text = morning_report(con, a.within, a.limit)
    print(text)
    token = os.environ.get("POINTCLI_TG_TOKEN")
    chat = os.environ.get("POINTCLI_TG_CHAT")
    if a.telegram:
        if not (token and chat):
            sys.exit("POINTCLI_TG_TOKEN, POINTCLI_TG_CHAT 환경변수가 필요합니다.")
        send_telegram(text, token, chat)
        print("텔레그램 전송 완료")


def cmd_cron(con, a):
    hh, mm = a.at.split(":")
    here = os.path.dirname(os.path.abspath(__file__))
    log = os.path.expanduser("~/.pointcli.log")
    tg = " --telegram" if a.telegram else ""
    print("# `crontab -e`로 아래 줄을 추가하세요 (평일/주말 매일 실행)")
    if a.telegram:
        print("# 텔레그램 사용 시 crontab 맨 위에 POINTCLI_TG_TOKEN=..., POINTCLI_TG_CHAT=... 도 추가")
    print(f"{int(mm)} {int(hh)} * * * cd {here} && {sys.executable} pointcli.py morning{tg} >> {log} 2>&1")


def build_parser():
    p = argparse.ArgumentParser(prog="pointcli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="조사한 기본 서비스 목록 추가").set_defaults(fn=cmd_init)
    x = sub.add_parser("add", help="서비스 추가")
    x.add_argument("name")
    x.add_argument("--task", default="출석체크")
    x.add_argument("--est", type=int, default=0, help="하루 예상 수익(원)")
    x.add_argument("--expire-days", type=int, default=0, help="적립 후 유효일수(0=모름)")
    x.add_argument("--note", default="")
    x.set_defaults(fn=cmd_add)
    x = sub.add_parser("edit", help="서비스 정보 수정")
    x.add_argument("name")
    x.add_argument("--task")
    x.add_argument("--est", type=int)
    x.add_argument("--expire-days", type=int)
    x.add_argument("--note")
    x.set_defaults(fn=cmd_edit)
    x = sub.add_parser("expiring", help="소멸 임박 적립금")
    x.add_argument("--within", type=int, default=30)
    x.set_defaults(fn=cmd_expiring)
    x = sub.add_parser("feed", help="이벤트 수집용 RSS/Atom 피드 관리")
    x.add_argument("action", choices=["add", "list"])
    x.add_argument("url", nargs="?")
    x.set_defaults(fn=cmd_feed)
    sub.add_parser("collect", help="피드에서 이벤트 수집").set_defaults(fn=cmd_collect)
    x = sub.add_parser("morning", help="아침 리포트(수집+오늘 할 일+소멸 임박+새 이벤트)")
    x.add_argument("--within", type=int, default=14)
    x.add_argument("--limit", type=int, default=10)
    x.add_argument("--telegram", action="store_true", help="텔레그램으로도 전송")
    x.set_defaults(fn=cmd_morning)
    x = sub.add_parser("cron", help="매일 자동 실행용 crontab 줄 출력")
    x.add_argument("--at", default="08:00", help="HH:MM (기본 08:00)")
    x.add_argument("--telegram", action="store_true")
    x.set_defaults(fn=cmd_cron)
    x = sub.add_parser("export-events", help="앱용 events.json 내보내기")
    x.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "events.json"))
    x.add_argument("--limit", type=int, default=30)
    x.set_defaults(fn=cmd_export_events)
    x = sub.add_parser("events", help="수집된 이벤트 보기")
    x.add_argument("--limit", type=int, default=20)
    x.set_defaults(fn=cmd_events)
    x = sub.add_parser("remove", help="서비스 비활성화")
    x.add_argument("name")
    x.set_defaults(fn=cmd_remove)
    sub.add_parser("today", help="오늘 할 일").set_defaults(fn=cmd_today)
    x = sub.add_parser("done", help="오늘 완료 기록")
    x.add_argument("name")
    x.add_argument("--won", type=int, default=0, help="받은 금액(원)")
    x.add_argument("--date", help="YYYY-MM-DD (기본 오늘)")
    x.set_defaults(fn=cmd_done)
    x = sub.add_parser("stats", help="수익 통계")
    x.add_argument("--days", type=int, default=30)
    x.set_defaults(fn=cmd_stats)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    con = connect()
    try:
        a.fn(con, a)
    finally:
        con.close()


if __name__ == "__main__":
    main()

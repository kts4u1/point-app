import importlib

import pytest


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("POINTCLI_DB", str(tmp_path / "t.db"))
    import pointcli

    return importlib.reload(pointcli)


def test_flow(cli, capsys):
    cli.main(["init"])
    cli.main(["init"])  # idempotent
    cli.main(["done", "토스", "--won", "140"])
    capsys.readouterr()
    cli.main(["today"])
    out = capsys.readouterr().out
    assert "[x] 토스" in out and "[ ] 캐시업" in out
    cli.main(["stats", "--days", "7"])
    assert "합계: 140원" in capsys.readouterr().out


def test_unknown_service(cli):
    with pytest.raises(SystemExit):
        cli.main(["done", "없는곳"])


RSS = """<rss><channel>
<item><title>10월 출석 이벤트</title><link>https://e.com/1</link><pubDate>Fri, 09 Oct 2026 10:00:00 +0900</pubDate></item>
<item><title>무관한 공지</title><link>https://e.com/2</link></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>포인트 2배</title><link href="https://e.com/3"/><updated>2026-10-08T01:00:00Z</updated></entry></feed>"""


def test_parse_feed(cli):
    assert cli.parse_feed(RSS)[0] == ("10월 출석 이벤트", "https://e.com/1", "2026-10-09")
    assert cli.parse_feed(ATOM) == [("포인트 2배", "https://e.com/3", "2026-10-08")]
    assert cli.parse_feed(RSS)[1][2] == ""  # 날짜가 없으면 빈 문자열


def test_collect_filters_and_dedups(cli):
    cli.main(["feed", "add", "https://e.com/rss"])
    con = cli.connect()
    assert cli.collect(con, fetcher=lambda u: RSS) == 1  # 키워드 일치 1건만
    assert cli.collect(con, fetcher=lambda u: RSS) == 0  # 중복 제외
    con.close()


def test_collect_survives_bad_feed(cli):
    cli.main(["feed", "add", "https://e.com/rss"])
    con = cli.connect()

    def boom(u):
        raise PermissionError("robots")

    assert cli.collect(con, fetcher=boom) == 0
    con.close()


def test_expiring(cli, capsys):
    from datetime import date, timedelta

    cli.main(["init"])
    day = (date.today() - timedelta(days=340)).isoformat()
    cli.main(["done", "캐시워크", "--won", "100", "--date", day])  # 365일 -> D-25
    cli.main(["done", "토스", "--won", "50", "--date", day])  # 유효기간 모름 -> 제외
    capsys.readouterr()
    cli.main(["expiring", "--within", "30"])
    out = capsys.readouterr().out
    assert "캐시워크: 100원" in out and "토스" not in out


def test_edit(cli, capsys):
    cli.main(["init"])
    cli.main(["edit", "네이버페이", "--expire-days", "180"])
    con = cli.connect()
    assert con.execute("SELECT expire_days FROM service WHERE name='네이버페이'").fetchone()[0] == 180
    con.close()
    with pytest.raises(SystemExit):
        cli.main(["edit", "네이버페이"])


def _fake_urlopen(cli, monkeypatch, robots):
    import io
    import urllib.error

    def fake(req, timeout=0):
        if isinstance(robots, int):
            raise urllib.error.HTTPError(req.full_url, robots, "x", {}, None)
        return io.BytesIO(robots.encode())

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake)


def test_robots_rules(cli, monkeypatch):
    _fake_urlopen(cli, monkeypatch, "User-agent: *\nDisallow: /private\n")
    assert cli.robots_allows("https://a.com/rss")
    assert not cli.robots_allows("https://a.com/private/rss")


@pytest.mark.parametrize("code,ok", [(404, True), (403, False), (401, False), (503, False)])
def test_robots_http_errors(cli, monkeypatch, code, ok):
    _fake_urlopen(cli, monkeypatch, code)
    assert cli.robots_allows("https://a.com/rss") is ok


def test_morning_report_only_new_events(cli):
    cli.main(["init"])
    con = cli.connect()
    con.execute("DELETE FROM feed")
    con.execute("INSERT INTO feed(url) VALUES('https://e.com/rss')")
    con.commit()
    first = cli.morning_report(con, fetcher=lambda u: RSS)
    assert "[새 이벤트 1건]" in first and "10월 출석 이벤트" in first
    assert "남은 일" in first and "소멸 임박" in first
    second = cli.morning_report(con, fetcher=lambda u: RSS)
    assert "[새 이벤트 0건]" in second  # 이미 본 이벤트는 다시 안 나옴
    con.close()


def test_cron_line(cli, capsys):
    cli.main(["cron", "--at", "07:30"])
    out = capsys.readouterr().out
    assert "30 7 * * * cd " in out and "pointcli.py morning" in out


def test_export_events(cli, tmp_path):
    import json

    cli.main(["feed", "add", "https://e.com/rss"])
    con = cli.connect()
    cli.collect(con, fetcher=lambda u: RSS)
    con.close()
    out = tmp_path / "events.json"
    cli.main(["export-events", "--out", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["title"] == "10월 출석 이벤트" and data[0]["link"] == "https://e.com/1"


def test_norm_date(cli):
    assert cli.norm_date("Fri, 09 Oct 2026 23:30:00 +0900") == "2026-10-09"
    assert cli.norm_date("2026-10-08T01:00:00Z") == "2026-10-08"
    assert cli.norm_date("어제") == "" and cli.norm_date(None) == ""


def test_merge_events_accumulates_and_dedups(cli):
    from datetime import date

    today = date(2026, 10, 9)
    old = [{"title": "A", "link": "l1", "seen": "2026-10-01", "published": "2026-10-01", "source": "뽐뿌"},
           {"title": "낡은글", "link": "l0", "seen": "2026-05-01", "published": "", "source": ""}]
    fresh = [{"title": "A(수정)", "link": "l1", "seen": "2026-10-09", "published": "", "source": "x"},
             {"title": "B", "link": "l2", "seen": "2026-10-09", "published": "2026-10-09", "source": "뽐뿌"}]
    out = cli.merge_events(old, fresh, keep_days=90, limit=10, today=today)
    assert [e["link"] for e in out] == ["l2", "l1"]  # 최신순, 90일 지난 l0은 제거
    a = [e for e in out if e["link"] == "l1"][0]
    assert a["seen"] == "2026-10-01" and a["title"] == "A"  # 최초 발견일/제목 유지
    assert cli.merge_events(old, fresh, limit=1, today=today)[0]["link"] == "l2"


def test_export_merge_and_source(cli, tmp_path):
    import json

    cli.main(["feed", "add", "https://e.com/rss", "--label", "예시"])
    con = cli.connect()
    cli.collect(con, fetcher=lambda u: RSS)
    con.close()
    out = tmp_path / "ev.json"
    out.write_text(json.dumps([{"title": "예전 글", "link": "https://e.com/old", "seen": "2026-10-01",
                                "published": "2026-10-01", "source": "예시"}]), encoding="utf-8")
    cli.main(["export-events", "--out", str(out), "--merge", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert {e["link"] for e in data} == {"https://e.com/old", "https://e.com/1"}
    assert data[0]["source"] == "예시" and data[0]["published"] == "2026-10-09"
    # 깨진 기존 파일은 무시하고 새로 시작
    out.write_text("not json", encoding="utf-8")
    cli.main(["export-events", "--out", str(out), "--merge", str(out)])
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 1


def test_feeds_file(cli, tmp_path, monkeypatch):
    f = tmp_path / "feeds.txt"
    f.write_text("# 주석\n\nhttps://a.com/rss 내 블로그\nftp://bad 무시\nhttps://b.com/rss\n", encoding="utf-8")
    assert cli.read_feeds_file(str(f)) == [("https://a.com/rss", "내 블로그"), ("https://b.com/rss", "b.com")]
    monkeypatch.setattr(cli, "FEEDS_FILE", str(f))
    cli.main(["init"])
    con = cli.connect()
    urls = {r["url"]: r["label"] for r in con.execute("SELECT url,label FROM feed")}
    assert urls["https://a.com/rss"] == "내 블로그"
    assert urls["https://www.ppomppu.co.kr/rss.php?id=coupon"] == "뽐뿌 쿠폰"
    con.close()

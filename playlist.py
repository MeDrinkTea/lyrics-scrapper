#!/usr/bin/env python3
"""
Spotify playlist/album -> tracks.tsv

    python playlist.py https://open.spotify.com/playlist/XXXX
    python playlist.py https://open.spotify.com/album/XXXX -o my.tsv
    python playlist.py <url> --all-artists

Пишет TSV:  первый_артист <TAB> название
(ровно тот формат, который ждёт scrape_lyrics.py --tracks)

Анонимный токен берётся со страницы embed — аккаунт Spotify не нужен.
"""

import argparse
import json
import re
import sys
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

KINDS = ("playlist", "album", "track")


def parse_target(value: str):
    """URL или голый id -> (kind, id)."""
    value = value.strip()
    for kind in KINDS:
        m = re.search(rf"{kind}[/:]([A-Za-z0-9]{{22}})", value)
        if m:
            return kind, m.group(1)
    m = re.match(r"^(spotify:)?(?:playlist|album|track):([A-Za-z0-9]{22})$", value)
    if m:
        return m.group(1) or "playlist", m.group(2)
    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return "playlist", value
    raise SystemExit(f"не разобрал ссылку: {value}")


def get_token(sess, kind, pid):
    url = f"https://open.spotify.com/embed/{kind}/{pid}"
    r = sess.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>', r.text)
    if not m:
        raise SystemExit("не нашёл __NEXT_DATA__ на странице embed")
    data = json.loads(m.group(1))
    state = data["props"]["pageProps"]["state"]

    token = state["settings"]["session"]["accessToken"]
    entity = (state.get("data") or {}).get("entity") or {}
    return token, entity


def api_get(sess, url, token, params):
    """GET с обработкой 429/401/5xx."""
    for attempt in range(6):
        r = sess.get(url, headers={"Authorization": "Bearer " + token},
                     params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            raise PermissionError("token expired")
        if r.status_code in (429, 500, 502, 503, 504):
            wait = int(r.headers.get("Retry-After") or 0) or (2 ** attempt)
            print(f"  {r.status_code}, жду {wait} с", file=sys.stderr)
            time.sleep(wait)
            continue
        raise SystemExit(f"Spotify API {r.status_code}: {r.text[:200]}")
    raise SystemExit("Spotify API: не дождался ответа")


def iter_tracks(sess, kind, pid):
    token, entity = get_token(sess, kind, pid)
    name = entity.get("name") or pid
    total = entity.get("trackCount") or len(entity.get("trackList") or [])
    print(f"[*] {name} — {total or '?'} треков", file=sys.stderr)

    if kind == "track":
        t = entity.get("track") or entity
        yield t
        return

    offset = 0
    while True:
        url = f"https://api.spotify.com/v1/{kind}s/{pid}/tracks"
        try:
            page = api_get(sess, url, token, {"limit": 100, "offset": offset})
        except PermissionError:
            token, _ = get_token(sess, kind, pid)
            page = api_get(sess, url, token, {"limit": 100, "offset": offset})

        items = page.get("items") or []
        for item in items:
            # в плейлистах трек обёрнут в {"track": {...}}, в альбомах — нет
            yield (item.get("track") or item) if "track" in item else item

        if not page.get("next") or not items:
            break
        offset += len(items)
        print(f"  {offset}…", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Spotify playlist/album -> TSV треклист")
    ap.add_argument("url", help="ссылка на плейлист или альбом")
    ap.add_argument("-o", "--out", default="tracks.tsv")
    ap.add_argument("--all-artists", action="store_true",
                    help="писать всех артистов через запятую, а не только первого")
    args = ap.parse_args()

    kind, pid = parse_target(args.url)
    sess = requests.Session()

    rows, skipped = [], 0
    for t in iter_tracks(sess, kind, pid):
        if not t or t.get("is_local"):
            skipped += 1
            continue
        title = (t.get("name") or "").strip()
        artists = [a.get("name", "").strip() for a in (t.get("artists") or [])]
        artists = [a for a in artists if a]
        if not title or not artists:
            skipped += 1
            continue
        artist = ", ".join(artists) if args.all_artists else artists[0]
        rows.append(f"{artist}\t{title}")

    if not rows:
        raise SystemExit("ничего не собрал — плейлист пуст или приватный")

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")

    print(f"[+] {len(rows)} треков -> {args.out}", file=sys.stderr)
    if skipped:
        print(f"[!] пропущено (локальные/битые): {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Spotify playlist -> Genius lyrics -> plain text file.

Usage:
    python scrape_lyrics.py <playlist_url_or_id> [-o lyrics.txt]

Output: one lyric line per line, no section headers, no titles, no artists.
Tracks whose lyrics could not be found are written to <output>.missing.txt
"""

import argparse
import json
import os
import re
import sys
import time
import threading
import html as htmllib
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}

CACHE_FILE = "lyrics_cache.json"

# Genius throttles hard. Keep a global minimum interval between requests.
_MIN_INTERVAL = 0.6
_lock = threading.Lock()
_last_call = [0.0]


def throttle():
    with _lock:
        now = time.monotonic()
        wait = _last_call[0] + _MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


# ---------------------------------------------------------------- spotify ----

def playlist_id(url_or_id: str) -> str:
    m = re.search(r"playlist[/:]([A-Za-z0-9]{22})", url_or_id)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", url_or_id):
        return url_or_id
    raise SystemExit(f"cannot parse playlist id from: {url_or_id}")


def spotify_token(pid: str, sess: requests.Session) -> str:
    r = sess.get(f"https://open.spotify.com/embed/playlist/{pid}",
                 headers=HEADERS, timeout=30)
    r.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>', r.text)
    if not m:
        raise SystemExit("no __NEXT_DATA__ in embed page")
    data = json.loads(m.group(1))
    return data["props"]["pageProps"]["state"]["settings"]["session"]["accessToken"]


def fetch_tracks(pid: str, sess: requests.Session):
    token = spotify_token(pid, sess)
    auth = {"Authorization": f"Bearer {token}"}
    tracks, offset = [], 0
    while True:
        r = sess.get(
            f"https://api.spotify.com/v1/playlists/{pid}/tracks",
            headers=auth,
            params={"limit": 100, "offset": offset,
                    "fields": "items(track(name,artists(name),type)),next"},
            timeout=30,
        )
        if r.status_code == 401:
            token = spotify_token(pid, sess)
            auth = {"Authorization": f"Bearer {token}"}
            continue
        r.raise_for_status()
        page = r.json()
        for item in page.get("items") or []:
            t = item.get("track") or {}
            if not t.get("name") or t.get("type") == "episode":
                continue
            artists = [a["name"] for a in (t.get("artists") or []) if a.get("name")]
            if not artists:
                continue
            tracks.append({"title": t["name"], "artists": artists})
        if not page.get("next"):
            break
        offset += 100
    return tracks


# ------------------------------------------------------------------ genius ---

SECTION_RE = re.compile(r"^\s*[\[\(][^\]\)]*[\]\)]\s*$")
NOISE = {"you might also like", "embed", "read more", "lyrics", ""}
EMBED_RE = re.compile(r"^\s*\d*\s*Embed\s*$", re.I)
CONTRIB_RE = re.compile(r"^\s*\d*\s*Contributors?\s*", re.I)
TRANSL_RE = re.compile(r"^\s*Translations?(English|Español|Deutsch|Français)?\s*$", re.I)
HEADER_END_RE = re.compile(r"(Lyrics\s*$)|(^\s*\[\s*Текст песни)|(^\s*\[\s*Verse 1)", re.I)
# Genius song descriptions get injected into the lyrics container and always
# end with a "Read More" link.
DESCRIPTION_RE = re.compile(r"Read More\s*$", re.I)
BLOCK_TAGS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "ul", "ol", "section", "blockquote"}


def render(node) -> str:
    """Walk the lyrics node, turning <br> and block boundaries into newlines."""
    from bs4 import NavigableString, Tag
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "br":
                out.append("\n")
            elif child.name in BLOCK_TAGS:
                out.append("\n")
                out.append(render(child))
                out.append("\n")
            elif child.name in ("script", "style"):
                continue
            else:
                out.append(render(child))
    return "".join(out)


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(feat[^)]*\)|\[feat[^\]]*\]|\(ft\.[^)]*\)", " ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def clean_query(title: str, artist: str) -> str:
    t = re.sub(r"\s*[\(\[][^\)\]]*(feat|ft\.|prod|remix|version|live|remaster)[^\)\]]*[\)\]]",
               " ", title, flags=re.I)
    return f"{artist} {t}".strip()


def genius_search(query: str, sess: requests.Session):
    r = None
    for attempt in range(4):
        throttle()
        r = sess.get("https://genius.com/api/search/multi",
                     params={"per_page": 5, "q": query},
                     headers=HEADERS, timeout=30)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    if r is None or r.status_code != 200:
        raise requests.HTTPError(f"search failed: {r.status_code if r is not None else 'no response'}")
    hits = []
    for section in r.json().get("response", {}).get("sections", []):
        if section.get("type") not in ("song", "top_hit"):
            continue
        for h in section.get("hits", []):
            res = h.get("result") or {}
            if res.get("_type") != "song" or not res.get("url"):
                continue
            hits.append({
                "url": res["url"],
                "title": res.get("title") or "",
                "full_title": res.get("full_title") or "",
                "artist": (res.get("primary_artist") or {}).get("name") or "",
            })
    return hits


def pick(hits, title, artists):
    from difflib import SequenceMatcher
    nt = norm(title)
    best, best_score = None, -1.0
    for h in hits:
        cand = norm(h["title"])
        score = SequenceMatcher(None, nt, cand).ratio()
        if nt and (nt in cand or cand in nt):
            score += 0.35
        for a in artists:
            na = norm(a)
            if na and na in norm(h["artist"] + " " + h["full_title"]):
                score += 0.30
                break
        if score > best_score:
            best, best_score = h, score
    return best if best_score >= 0.45 else None


def fetch_lyrics(url: str, sess: requests.Session) -> str:
    for attempt in range(3):
        try:
            throttle()
            r = sess.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError("retries exhausted")

    soup = BeautifulSoup(r.text, "html.parser")
    containers = soup.select('div[data-lyrics-container="true"]')
    if not containers:
        containers = soup.select("div.lyrics")
    if not containers:
        return ""

    chunks = []
    for c in containers:
        chunks.append(render(c))
    raw = "\n".join(chunks)
    raw = htmllib.unescape(raw)
    return raw


def clean_lyrics(raw: str) -> list:
    lines = []
    for line in raw.split("\n"):
        line = line.replace("\u200b", "").replace("\xa0", " ").strip()
        if not line:
            continue
        lines.append(line)

    # Drop the Genius header block: "N Contributors", "Translations", "English",
    # "<Song> Lyrics", then the "[Текст песни «...»]" line right after it.
    cut = None
    for i, line in enumerate(lines[:8]):
        if re.search(r"Lyrics\s*$", line, re.I) or re.match(r"^\s*\[\s*Текст песни", line, re.I):
            cut = i
            break
    if cut is not None:
        lines = lines[cut + 1:]
    else:
        while lines and (CONTRIB_RE.match(lines[0]) or TRANSL_RE.match(lines[0])
                         or lines[0].lower() in NOISE):
            lines.pop(0)

    out = []
    for line in lines:
        if SECTION_RE.match(line):
            continue
        if line.lower() in NOISE:
            continue
        if EMBED_RE.match(line):
            continue
        if CONTRIB_RE.match(line) and len(line) < 40:
            continue
        if TRANSL_RE.match(line):
            continue
        if DESCRIPTION_RE.search(line):
            continue
        out.append(line)
    return out


def resolve(track, sess):
    artist, title = track["artists"][0], track["title"]
    hit = None
    hits = genius_search(clean_query(title, artist), sess)
    if hits:
        hit = pick(hits, title, track["artists"])
    if not hit:
        hits = genius_search(title, sess)
        hit = pick(hits, title, track["artists"]) if hits else None
    if not hit:
        return track, []
    raw = fetch_lyrics(hit["url"], sess)
    return track, clean_lyrics(raw)


# -------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("playlist", nargs="?")
    ap.add_argument("-t", "--tracks", help="TSV file: artist<TAB>title per line")
    ap.add_argument("-o", "--out", default="lyrics.txt")
    ap.add_argument("-w", "--workers", type=int, default=3)
    ap.add_argument("--retry-empty", action="store_true",
                    help="re-fetch tracks that previously returned no lyrics")
    args = ap.parse_args()

    sess = requests.Session()
    if args.tracks:
        tracks = []
        with open(args.tracks, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2 or not parts[1].strip():
                    continue
                tracks.append({"artists": [parts[0].strip()], "title": parts[1].strip()})
        print(f"[*] {len(tracks)} tracks from {args.tracks}", file=sys.stderr)
    elif args.playlist:
        pid = playlist_id(args.playlist)
        print(f"[*] playlist {pid}", file=sys.stderr)
        tracks = fetch_tracks(pid, sess)
        print(f"[*] {len(tracks)} tracks", file=sys.stderr)
    else:
        raise SystemExit("need a playlist URL or --tracks TSV")

    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            cache = {}

    if args.retry_empty:
        todo = [t for t in tracks if not cache.get(f"{t['title']}|{t['artists'][0]}")]
    else:
        todo = [t for t in tracks if f"{t['title']}|{t['artists'][0]}" not in cache]
    print(f"[*] {len(todo)} to fetch, {len(tracks) - len(todo)} cached", file=sys.stderr)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(resolve, t, sess): t for t in todo}
        for fut in as_completed(futures):
            t = futures[fut]
            key = f"{t['title']}|{t['artists'][0]}"
            done += 1
            try:
                _, lines = fut.result()
            except Exception as e:
                print(f"  ! {key}: {e}", file=sys.stderr)
                continue
            cache[key] = lines
            print(f"  [{done}/{len(todo)}] {len(lines):4d} lines  {key}", file=sys.stderr)
            if done % 10 == 0:
                json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)

    json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)

    all_lines, missing = [], []
    for t in tracks:
        key = f"{t['title']}|{t['artists'][0]}"
        lines = cache.get(key) or []
        if lines:
            all_lines.extend(lines)
        else:
            missing.append(f"{', '.join(t['artists'])} - {t['title']}")

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(all_lines) + "\n")

    miss_path = args.out + ".missing.txt"
    with open(miss_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(missing) + ("\n" if missing else ""))

    print(f"[+] {len(all_lines)} lines -> {args.out}", file=sys.stderr)
    print(f"[+] {len(missing)} tracks without lyrics -> {miss_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

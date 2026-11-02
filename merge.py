#!/usr/bin/env python3
"""Merge lyrics from the requests-run cache and the browser-run export
into one plain-text file, in playlist order."""

import json
import os
import re
import sys

CACHE = "lyrics_cache.json"
BROWSER = "browser_lyrics.json"
TRACKS = "tracks.tsv"
OUT = "lyrics.txt"


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"! cannot read {path}: {e}", file=sys.stderr)
        return {}


# Lines Genius injects that are not lyrics.
DROP_RES = [
    re.compile(r"Read More\s*$", re.I),
    re.compile(r"^\s*[\[\(][^\]\)]*[\]\)]\s*$"),
    re.compile(r"^(you might also like|embed|read more|lyrics)$", re.I),
    re.compile(r"^\s*\d*\s*Embed\s*$", re.I),
]


def sanitize(lines):
    out = []
    for line in lines:
        line = line.replace("\u200b", "").replace("\xa0", " ").strip()
        if not line:
            continue
        if any(rx.search(line) for rx in DROP_RES):
            continue
        out.append(line)
    return out


def main():
    cache = load(CACHE)
    browser = load(BROWSER)

    tracks = []
    with open(TRACKS, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            p = line.split("\t")
            if len(p) >= 2 and p[1].strip():
                tracks.append((p[0].strip(), p[1].strip()))

    out, missing, from_browser = [], [], 0
    for artist, title in tracks:
        lines = cache.get(f"{title}|{artist}")
        if not lines:
            lines = browser.get(f"{artist}|{title}")
            if lines:
                from_browser += 1
        if lines:
            out.extend(sanitize(lines))
        else:
            missing.append(f"{artist} - {title}")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")

    miss_path = OUT + ".missing.txt"
    with open(miss_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(missing) + ("\n" if missing else ""))

    print(f"tracks:   {len(tracks)}")
    print(f"with text:{len(tracks) - len(missing)}  (browser: {from_browser})")
    print(f"missing:  {len(missing)}")
    print(f"lines:    {len(out)} -> {OUT}")
    print(f"missing list -> {miss_path}")


if __name__ == "__main__":
    main()

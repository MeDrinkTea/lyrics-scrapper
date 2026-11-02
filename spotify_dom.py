#!/usr/bin/env python3
"""
Декодирует выгрузку браузерного парсера (playlist.b64) в tracks.tsv.

    python spotify_dom.py                 # playlist.b64 -> tracks.tsv
    python spotify_dom.py -i x.b64 -o y.tsv

Если playlist.b64 рядом нет, берётся самый свежий playlist*.b64 из «Загрузок» —
именно туда браузер кладёт файл после window.__download().

Сам парсер — spotify_dom.js, он работает внутри вкладки open.spotify.com
(см. README, раздел «Треклист через браузер»).
"""

import argparse
import base64
import glob
import os
import sys

DEFAULT_IN = "playlist.b64"
DEFAULT_OUT = "tracks.tsv"


def downloads_dir():
    return os.path.join(os.path.expanduser("~"), "Downloads")


def newest_download():
    """Самый свежий playlist*.b64 в «Загрузках» или None."""
    hits = glob.glob(os.path.join(downloads_dir(), "playlist*.b64"))
    if not hits:
        return None
    return max(hits, key=os.path.getmtime)


def main():
    ap = argparse.ArgumentParser(description="playlist.b64 -> tracks.tsv")
    ap.add_argument("-i", "--input", default=None,
                    help="файл выгрузки (по умолчанию playlist.b64 или свежий из «Загрузок»)")
    ap.add_argument("-o", "--output", default=DEFAULT_OUT)
    args = ap.parse_args()

    path = args.input
    if path is None:
        path = DEFAULT_IN if os.path.exists(DEFAULT_IN) else newest_download()

    if not path or not os.path.exists(path):
        raise SystemExit(
            "нет файла выгрузки\n"
            "Сначала выполни во вкладке плейлиста: window.__download()\n"
            "или укажи путь: python spotify_dom.py -i путь\\playlist.b64"
        )

    raw = open(path, "rb").read().strip()
    try:
        text = base64.b64decode(raw, validate=True).decode("utf-8")
    except Exception as e:
        raise SystemExit(f"не декодируется как base64/UTF-8: {e}")

    rows = [l for l in text.split("\n") if l.strip()]
    if not rows:
        raise SystemExit("файл пустой — вероятно, список не прогрузился")

    bad = [l for l in rows if "\t" not in l]
    if bad:
        print(f"[!] строк без табуляции: {len(bad)}", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")

    print(f"[+] {len(rows)} треков -> {args.output}", file=sys.stderr)
    print(f"[*] источник: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()

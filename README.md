# Lyrics scrapper

Плейлист Spotify → тексты с Genius → обычный `.txt`, где **только строки песен, по одной на строку**: без названий, артистов, пометок куплетов и описаний.

A Spotify playlist → lyrics from Genius → a plain `.txt` with **lyric lines only, one per line**: no titles, artists, verse markers or descriptions.

Ниже две инструкции под спойлерами: **🇷🇺 русская** и **🇬🇧 английская**. Интерфейс программы тоже переключается между языками.
Two guides are below under spoilers: **🇷🇺 Russian** and **🇬🇧 English**. The app switches languages too.

<details>
<summary><b>🇷🇺 Русская инструкция</b></summary>

## Коротко

1. Запусти **`start.bat`** двойным кликом.
2. **«Из плейлиста (API)»** → вставь ссылку на плейлист Spotify.
3. **«Старт»** — на 450 треков уходит 20–40 минут.
4. **«Слить в lyrics.txt»**, затем **«Удалить дубли»**.
5. Готовый файл — **`lyrics_dedup.txt`** в папке программы.

## Что нужно

**Python 3.9+** (проверено на 3.11.9). При установке с [python.org](https://www.python.org/downloads/) обязательно поставь галочку «Add python.exe to PATH», иначе `start.bat` не найдёт интерпретатор.

Зависимости — две, `start.bat` доставит их сам при первом запуске:

```powershell
pip install -r requirements.txt      # requests, beautifulsoup4
```

`lxml` не нужен, Tkinter входит в Python.

## Быстрый старт в консоли

```powershell
python playlist.py https://open.spotify.com/playlist/XXXX   # треклист
python scrape_lyrics.py --tracks tracks.tsv -w 2            # тексты
python merge.py                                             # сборка
python dedup.py                                             # удаление дублей
```

## Окно программы

Двойной клик по **`start.bat`** или `python gui.py`.

1. **«Из плейлиста (API)»** — ссылка на плейлист, через несколько секунд готов `tracks.tsv`. Если Spotify ответил `429`/`401`, программа сама предложит путь через браузер.
2. **«Старт»** — потоки оставь на **2** (выше 3 не ставь, Genius банит). В логе идёт `[12/462]`, внизу — статус.
   - **«Пауза»** замораживает работу без потери прогресса, кнопка становится **«Продолжить»**.
   - **«Стоп»** прерывает; скачанное остаётся в кэше, следующий «Старт» продолжит с того же места.
3. **«Слить в lyrics.txt»** → **«Удалить дубли»**. Галочка «Собирать автоматически после парсинга» делает это сразу после парсинга.

Кнопки **RU / EN** в шапке переключают язык на лету; выбор хранится в `settings.json`. При первом запуске показывается окно с напоминанием прочитать README — чтобы вернуть его, удали `settings.json`.

## Треклист

`tracks.tsv` — по строке на трек, разделитель табуляция, UTF-8:

```
vers1zee	Палата 136
CUPSIZE	я уже не тот
```

Берётся первый артист: так поиск на Genius точнее, фиты по двум именам часто уводят на чужую версию. Нужны все — `--all-artists`.

```powershell
python playlist.py https://open.spotify.com/playlist/XXXX [-o FILE] [--all-artists]
```

Понимает плейлист, альбом и отдельный трек, в том числе с `?si=…`. Аккаунт не нужен: анонимный токен берётся со страницы `embed`.

### Если API не отвечает

Кнопка **«Через браузер…»**: программа кладёт скрипт в буфер, открывает плейлист и показывает инструкцию. Скрипт постепенно прокручивает список и в конце сам скачивает `playlist.b64` в «Загрузки» — оболочка замечает файл и делает из него `tracks.tsv`. Блок «Recommended» отбрасывается.

| Что | Что делать |
|---|---|
| Chrome просит `allow pasting` | Набери это **руками** и нажми `Enter` — вставка заработает |
| Вкладку нельзя сворачивать | В фоне Chrome душит таймеры, прокрутка идёт в разы медленнее |
| Не закрывай вкладку до конца | Результат живёт только в памяти страницы |

Файл не появился — выполни в консоли `window.__download()`, или нажми **«Импорт .b64…»**, или:

```powershell
python spotify_dom.py -i "C:\Users\...\Downloads\playlist.b64"
```

## Парсинг текстов

```powershell
python scrape_lyrics.py --tracks tracks.tsv -o lyrics.txt -w 2
```

| Ключ | Значение |
|---|---|
| `--tracks FILE` | Треклист (TSV) |
| `-o FILE` | Куда писать (по умолчанию `lyrics.txt`) |
| `-w N` | Потоков (по умолчанию 3, **выше 3 не ставь**) |
| `--retry-empty` | Перезапросить треки, которые вернулись пустыми |

Ищет на Genius по «артист + название», отсеивает каверы и чужие версии, вырезает шапки Genius, пометки `[Куплет]`/`[Chorus]`, `Embed` и описания песен. Ненайденное пишет в `lyrics.txt.missing.txt`.

Всё скачанное кэшируется в `lyrics_cache.json`, повторный запуск не перекачивает готовое. Ошибки (`429`, сеть) не кэшируются — трек будет повторён.

## Сборка и дубли

```powershell
python merge.py     # lyrics_cache.json + browser_lyrics.json + tracks.tsv -> lyrics.txt
python dedup.py     # lyrics.txt -> lyrics_dedup.txt
```

`merge.py` собирает в порядке плейлиста и заодно прогоняет финальную чистку. `dedup.py` по умолчанию исходник не трогает.

| Ключ | Значение |
|---|---|
| `--mode exact` | Побайтово после trim (по умолчанию) |
| `--mode case` | Без учёта регистра |
| `--mode loose` | Без регистра, пунктуации и лишних пробелов |
| `--keep first` | Оставить первое вхождение (по умолчанию) |
| `--keep none` | Выкинуть все повторы целиком |

В окне программы это подписано по-человечески: «точное», «без регистра», «без пунктуации».

## Что на выходе

`lyrics_dedup.txt` — обычный текст, одна строка песни на строку, в порядке плейлиста. Внутри нет названий, артистов, пометок `[Куплет 1]`, шапок Genius и описаний.

Разделителей между песнями нет — файл задуман как сплошной поток строк, поэтому дубли ищутся по всему документу: припев из двух треков схлопнется в один.

## Если Genius отдаёт 429

Это лимит запросов, а не капча. Останови прогон, подожди 10–30 минут и перезапусти с меньшим темпом: `-w 1` и `_MIN_INTERVAL` в `scrape_lyrics.py` побольше (по умолчанию `0.6` с). Потом `--retry-empty`, чтобы добрать недоделанное.

`0.6` с и 2 потока ≈ 3 запроса/с — безопасно. Четыре потока и `0.25` с дают бан на 15+ минут. Бан висит на `/api/search`, страницы песен при этом отдают 200.

## План Б: браузерный движок

Если `requests` режут по Cloudflare (`403`, «Just a moment…»):

```powershell
python serve.py        # отдельное окно, порт 8765
```

На `genius.com` в консоли браузера (`F12`):

```js
const src = await (await fetch('http://127.0.0.1:8765/engine.js')).text();
(0, eval)(src);
await window.__init();
window.__runSlow({ delay: 2500, backoff: 90000, minutes: 60 });
```

`__progress()` — прогресс, `__SLOW.stop = true` — пауза, `__download()` — выгрузка в `browser_lyrics.b64`. Результаты живут в памяти вкладки, поэтому выгружай до закрытия:

```powershell
python -c "import base64,json;d=json.loads(base64.b64decode(open('browser_lyrics.b64','rb').read()));json.dump({k:v for k,v in d.items() if v},open('browser_lyrics.json','w',encoding='utf-8'),ensure_ascii=False)"
```

Дальше `merge.py` подхватит файл наравне с кэшем.

## Частые проблемы

| Симптом | Решение |
|---|---|
| `429` пачками | Ждать 10–30 минут, снизить `-w`, поднять `_MIN_INTERVAL` |
| Много треков в `.missing.txt` | Андерграунда нет на Genius или трек назван иначе — поправь `tracks.tsv` |
| В файле описание песни | Прогони `merge.py`: он режет по `Read More` |
| Пустые результаты закэшированы | `--retry-empty` |
| Кракозябры в консоли | Это консоль, файлы всегда UTF-8 |
| `lyrics.txt` не обновился | `scrape_lyrics.py` пишет свой `-o`, а `merge.py` всегда пишет `lyrics.txt` |
| `start.bat` не открывает окно | Python не в PATH — переустанови с галочкой «Add python.exe to PATH» |
| Chrome не даёт вставить скрипт | Набери `allow pasting` руками, потом вставляй |
| `playlist.b64` не появился | `window.__download()`, «Импорт .b64…» или `spotify_dom.py -i` |
| Интерфейс не на том языке | Кнопка **RU** / **EN** в шапке |

## Файлы

| Файл | Что это |
|---|---|
| `tracks.tsv` | Треклист: `артист<TAB>название` |
| `playlist.py` | Треклист из ссылки Spotify |
| `spotify_dom.js`, `spotify_dom.py` | Треклист со страницы плейлиста, `playlist.b64` → `tracks.tsv` |
| `scrape_lyrics.py` | Основной парсер (Genius через `requests`) |
| `engine.js`, `serve.py` | Браузерный парсер и локальный сервер для него |
| `merge.py` | Сборка `lyrics.txt` в порядке плейлиста |
| `dedup.py` | Удаление повторяющихся строк |
| `gui.py`, `lang.py`, `start.bat` | Окно программы, тексты интерфейса, запуск |
| `lyrics.txt` | Собранные тексты |
| `lyrics_dedup.txt` | **Итоговый результат** |
| `lyrics.txt.missing.txt` | Треки без текста |
| `lyrics_cache.json`, `browser_lyrics.json`, `done.txt` | Кэш и результаты парсеров |
| `settings.json` | Язык и стартовое окно (появляется после первого запуска) |

## Как это устроено

```
плейлист Spotify
      │
      ├─ playlist.py ──────────┐        (API — основной путь)
      └─ spotify_dom.js/.py ───┴──► tracks.tsv
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                scrape_lyrics.py                   engine.js
                   (requests)                      (браузер)
                        │                               │
                        ▼                               ▼
               lyrics_cache.json              browser_lyrics.json
                        └───────────┬───────────────────┘
                                    ▼
                                 merge.py ──► lyrics.txt (+ .missing.txt)
                                    │
                                    ▼
                                 dedup.py ──► lyrics_dedup.txt
```

Треклист берётся любым из двух способов, результат одинаковый. Источники текстов независимы: `merge.py` берёт кэш, а чего там нет — из браузерного файла, так что остаток можно добрать любым путём.

</details>

<details>
<summary><b>🇬🇧 English guide</b></summary>

## The short version

1. Double-click **`start.bat`**.
2. **«From playlist (API)»** → paste a Spotify playlist link.
3. **«Start»** — 20–40 minutes for 450 tracks.
4. **«Merge into lyrics.txt»**, then **«Remove duplicates»**.
5. The result is **`lyrics_dedup.txt`** in the program folder.

## What you need

**Python 3.9+** (tested on 3.11.9). When installing from [python.org](https://www.python.org/downloads/), tick «Add python.exe to PATH» — otherwise `start.bat` won't find the interpreter.

Two dependencies; `start.bat` installs them on the first run:

```powershell
pip install -r requirements.txt      # requests, beautifulsoup4
```

`lxml` is not needed, Tkinter ships with Python.

## Quick start in the console

```powershell
python playlist.py https://open.spotify.com/playlist/XXXX   # tracklist
python scrape_lyrics.py --tracks tracks.tsv -w 2            # lyrics
python merge.py                                             # build
python dedup.py                                             # remove duplicates
```

## The app window

Double-click **`start.bat`** or run `python gui.py`.

1. **«From playlist (API)»** — paste a link, `tracks.tsv` is ready in seconds. If Spotify answers `429`/`401`, the app offers the browser path itself.
2. **«Start»** — keep threads at **2** (never above 3, Genius bans). The log counts `[12/462]`, the status line shows the current step.
   - **«Pause»** freezes the work without losing progress; the button becomes **«Resume»**.
   - **«Stop»** interrupts; everything downloaded stays cached, the next «Start» continues from the same place.
3. **«Merge into lyrics.txt»** → **«Remove duplicates»**. The «Build automatically after scraping» checkbox does this right after scraping.

The **RU / EN** buttons in the header switch the language live; the choice is saved to `settings.json`. On the first run a window reminds you to read this README — delete `settings.json` to bring it back.

## Tracklist

`tracks.tsv` — one track per line, tab-separated, UTF-8:

```
vers1zee	Палата 136
CUPSIZE	я уже не тот
```

Only the first artist is kept: that makes the Genius search more precise, since featuring credits often lead to someone else's version. Need them all — `--all-artists`.

```powershell
python playlist.py https://open.spotify.com/playlist/XXXX [-o FILE] [--all-artists]
```

Playlists, albums and single tracks work, including links with `?si=…`. No Spotify account needed: an anonymous token is taken from the `embed` page.

### If the API refuses

The **«Via browser…»** button puts a script into the clipboard, opens the playlist and shows instructions. The script scrolls the list gradually and downloads `playlist.b64` into Downloads — the app notices the file and turns it into `tracks.tsv`. The «Recommended» block is dropped.

| What | What to do |
|---|---|
| Chrome asks for `allow pasting` | Type it **by hand** and press `Enter` — pasting then works |
| Don't minimise the tab | Chrome throttles timers in background tabs, scrolling crawls |
| Don't close the tab early | The result lives only in page memory |

No file? Run `window.__download()` in the console, press **«Import .b64…»**, or:

```powershell
python spotify_dom.py -i "C:\Users\...\Downloads\playlist.b64"
```

## Scraping lyrics

```powershell
python scrape_lyrics.py --tracks tracks.tsv -o lyrics.txt -w 2
```

| Flag | Meaning |
|---|---|
| `--tracks FILE` | Tracklist (TSV) |
| `-o FILE` | Output (default `lyrics.txt`) |
| `-w N` | Threads (default 3, **never above 3**) |
| `--retry-empty` | Re-request tracks that came back empty |

It searches Genius by «artist + title», filters out covers and wrong versions, and strips Genius headers, `[Verse]`/`[Chorus]` markers, `Embed` and song descriptions. Tracks with no lyrics go to `lyrics.txt.missing.txt`.

Everything downloaded is cached in `lyrics_cache.json`; a repeated run does not re-download. Errors (`429`, network) are not cached — the track is retried next time.

## Build and duplicates

```powershell
python merge.py     # lyrics_cache.json + browser_lyrics.json + tracks.tsv -> lyrics.txt
python dedup.py     # lyrics.txt -> lyrics_dedup.txt
```

`merge.py` assembles everything in playlist order and runs the final clean-up. `dedup.py` leaves the source untouched by default.

| Flag | Meaning |
|---|---|
| `--mode exact` | Byte-for-byte after trim (default) |
| `--mode case` | Case-insensitive |
| `--mode loose` | Ignores case, punctuation and extra spaces |
| `--keep first` | Keep the first occurrence (default) |
| `--keep none` | Drop every repeated line entirely |

In the app these read as «exact», «ignore case», «ignore punctuation».

## What you get

`lyrics_dedup.txt` — plain text, one lyric line per line, in playlist order. No titles, artists, `[Verse 1]` markers, Genius headers or descriptions.

There are no separators between songs: the file is a continuous stream of lines, so duplicates are matched across the whole document — a chorus shared by two tracks collapses into one.

## If Genius returns 429

That's a rate limit, not a captcha. Stop the run, wait 10–30 minutes and restart slower: `-w 1` and a larger `_MIN_INTERVAL` in `scrape_lyrics.py` (default `0.6` s). Then `--retry-empty` to finish the rest.

`0.6` s with 2 threads ≈ 3 requests/s — safe. Four threads at `0.25` s cause a 15+ minute ban. The ban sits on `/api/search`; lyric pages still return 200.

## Plan B: the browser engine

If `requests` is blocked by Cloudflare (`403`, «Just a moment…»):

```powershell
python serve.py        # separate window, port 8765
```

On `genius.com`, in the browser console (`F12`):

```js
const src = await (await fetch('http://127.0.0.1:8765/engine.js')).text();
(0, eval)(src);
await window.__init();
window.__runSlow({ delay: 2500, backoff: 90000, minutes: 60 });
```

`__progress()` shows progress, `__SLOW.stop = true` pauses, `__download()` exports `browser_lyrics.b64`. Results live in page memory, so export before closing:

```powershell
python -c "import base64,json;d=json.loads(base64.b64decode(open('browser_lyrics.b64','rb').read()));json.dump({k:v for k,v in d.items() if v},open('browser_lyrics.json','w',encoding='utf-8'),ensure_ascii=False)"
```

Then `merge.py` picks the file up alongside the cache.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `429` in batches | Wait 10–30 minutes, lower `-w`, raise `_MIN_INTERVAL` |
| Many tracks in `.missing.txt` | Underground releases missing from Genius, or the title differs — fix `tracks.tsv` |
| A song description ended up in the file | Run `merge.py`: it cuts at `Read More` |
| Empty results are cached | `--retry-empty` |
| Garbled text in the console | That's the console; files are always UTF-8 |
| `lyrics.txt` was not updated | `scrape_lyrics.py` writes its own `-o`, `merge.py` always writes `lyrics.txt` |
| `start.bat` opens nothing | Python is not in PATH — reinstall with «Add python.exe to PATH» |
| Chrome blocks the paste | Type `allow pasting` by hand, then paste |
| No `playlist.b64` | `window.__download()`, «Import .b64…» or `spotify_dom.py -i` |
| Wrong interface language | The **RU** / **EN** buttons in the header |

## Files

| File | What it is |
|---|---|
| `tracks.tsv` | Tracklist: `artist<TAB>title` |
| `playlist.py` | Tracklist from a Spotify link |
| `spotify_dom.js`, `spotify_dom.py` | Tracklist from the playlist page, `playlist.b64` → `tracks.tsv` |
| `scrape_lyrics.py` | Main scraper (Genius via `requests`) |
| `engine.js`, `serve.py` | Browser scraper and its local server |
| `merge.py` | Builds `lyrics.txt` in playlist order |
| `dedup.py` | Removes repeated lines |
| `gui.py`, `lang.py`, `start.bat` | App window, interface strings, launcher |
| `lyrics.txt` | Assembled lyrics |
| `lyrics_dedup.txt` | **Final result** |
| `lyrics.txt.missing.txt` | Tracks with no lyrics |
| `lyrics_cache.json`, `browser_lyrics.json`, `done.txt` | Caches and scraper results |
| `settings.json` | Language and the welcome window (created on first run) |

## How it works

```
Spotify playlist
      │
      ├─ playlist.py ──────────┐        (API — the main path)
      └─ spotify_dom.js/.py ───┴──► tracks.tsv
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                scrape_lyrics.py                   engine.js
                   (requests)                      (browser)
                        │                               │
                        ▼                               ▼
               lyrics_cache.json              browser_lyrics.json
                        └───────────┬───────────────────┘
                                    ▼
                                 merge.py ──► lyrics.txt (+ .missing.txt)
                                    │
                                    ▼
                                 dedup.py ──► lyrics_dedup.txt
```

Either tracklist path gives the same result. The two lyric sources are independent: `merge.py` takes the cache and fills the gaps from the browser file, so the remainder can be collected any way you like.

</details>

## Лицензия / License

MIT — см. `LICENSE`. / MIT — see `LICENSE`.

Тексты песен и треклист в репозиторий не входят: они в `.gitignore`. Код свободный, скачанный контент — нет.
The lyrics and the tracklist are not in the repository: they are in `.gitignore`. The code is free, the downloaded content is not.

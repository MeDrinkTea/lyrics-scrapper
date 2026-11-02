/* Spotify playlist engine — runs inside an open.spotify.com playlist tab.
   Scrolls the list gradually so every row gets rendered, drops the
   "Recommended" block Spotify appends at the end, and exports the
   tracklist as base64 TSV (decode with spotify_dom.py).

   Два способа загрузки:
   1. Готовый сниппет из GUI — он содержит этот файл целиком, сервер не нужен.
   2. Вручную (см. README):
        const src = await (await fetch('http://127.0.0.1:8765/spotify_dom.js')).text();
        (0, eval)(src);
        await window.__scrollAll();
        window.__download();
*/

(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  /* Блок «Recommended», который Spotify подмешивает после плейлиста.
     Внутри него треки — чужие, в треклист они попадать не должны. */
  const RECOMMENDED = '[data-testid="recommended-tracks-context"]';

  const allRows = () => document.querySelectorAll('[data-testid="track-row"]');

  const inRecommended = el => !!(el && el.closest && el.closest(RECOMMENDED));

  const rows = () => allRows().length;

  /* Строки самого плейлиста — без хвоста «Recommended». Именно по ним
     считается рост: рекомендации подгружаются в конце и не должны
     влиять на решение «дошли до конца или нет». */
  const playlistRows = () => [...allRows()].filter(r => !inRecommended(r)).length;

  const hasRecommended = () => !!document.querySelector(RECOMMENDED);

  /* Ищем контейнер, который реально скроллится. На веб-плеере Spotify
     это обычно <html>, но в некоторых раскладках — внутренний div. */
  window.__findScroller = function () {
    const candidates = [];
    document.querySelectorAll('*').forEach(n => {
      const st = getComputedStyle(n);
      if (/(auto|scroll)/.test(st.overflowY) && n.scrollHeight > n.clientHeight + 40) {
        candidates.push(n);
      }
    });
    if (candidates.length) {
      candidates.sort((a, b) => b.scrollHeight - a.scrollHeight);
      return candidates[0];
    }
    return document.scrollingElement || document.documentElement;
  };

  /* Один шаг: сдвиг на 3/4 экрана и ожидание, пока дорисуются строки. */
  async function step(sc, pause) {
    const before = playlistRows();
    const h = sc.clientHeight || window.innerHeight;
    const prevTop = sc.scrollTop;

    sc.scrollTop = Math.min(prevTop + Math.round(h * 0.75), sc.scrollHeight);
    sc.dispatchEvent(new Event('scroll', { bubbles: true }));
    if (sc === document.scrollingElement) {
      window.dispatchEvent(new Event('scroll'));
    }

    const deadline = Date.now() + 1600;
    while (Date.now() < deadline) {
      await sleep(120);
      if (playlistRows() > before) break;
    }
    await sleep(pause);

    return { grew: playlistRows() > before, moved: sc.scrollTop !== prevTop, pl: playlistRows() };
  }

  /* Постепенная прокрутка до конца списка. */
  window.__scrollAll = async function (opts) {
    opts = opts || {};
    const pause = opts.pause ?? 300;
    const maxSteps = opts.maxSteps ?? 900;
    const stableLimit = opts.stable ?? 8;

    const sc = window.__findScroller();
    let last = playlistRows();
    let stable = 0;
    let steps = 0;

    while (stable < stableLimit && steps < maxSteps) {
      const r = await step(sc, pause);
      steps++;

      if (r.pl > last) {
        last = r.pl;
        stable = 0;
        continue;
      }
      if (!r.moved) {
        /* Дошли до низа — даём ленивой подгрузке больше времени. */
        await sleep(700);
      }

      /* Плейлист кончился, начались рекомендации, и список стоит на месте:
         дальше только чужие треки. */
      const atBottom = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 8;
      if (atBottom && hasRecommended() && stable >= 3) break;

      stable++;
    }

    const stats = window.__stats();
    return {
      tracks: stats.tracks,
      recommended: stats.recommended,
      rows: stats.rows,
      steps,
      scrollHeight: sc.scrollHeight,
      atBottom: sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 4,
    };
  };

  /* Сбор строк: название + первый артист + uri. */
  window.__extract = function () {
    const out = [];
    const seen = new Set();

    for (const row of allRows()) {
      if (inRecommended(row)) continue;          // хвост «Recommended»

      const label = row.getAttribute('aria-labelledby') || '';
      const m = label.match(/spotify:track:([A-Za-z0-9]+)/);
      const uri = m ? 'spotify:track:' + m[1] : null;

      const titleEl = row.querySelector('p[data-encore-id="listRowTitle"]');
      const title = (titleEl ? titleEl.textContent : row.getAttribute('aria-label') || '').trim();

      const artists = [...row.querySelectorAll(
        'a[data-testid="internal-artist-link"], a[href^="/artist/"]'
      )].map(a => a.textContent.trim()).filter(Boolean);

      if (!artists.length || !title) continue;   // битые строки и прочий мусор

      const key = uri || (artists[0] + '|' + title);
      if (seen.has(key)) continue;
      seen.add(key);

      out.push({ uri, artist: artists[0], title, allArtists: artists });
    }
    return out;
  };

  /* Сколько строк всего, сколько отброшено как рекомендации. */
  window.__stats = function () {
    const total = rows();
    const recommended = [...allRows()].filter(inRecommended).length;
    return { rows: total, recommended, tracks: window.__extract().length };
  };

  window.__toTsv = function (allArtists) {
    return window.__extract()
      .map(t => (allArtists ? t.allArtists.join(', ') : t.artist) + '\t' + t.title)
      .join('\n');
  };

  /* Выгрузка в файл: base64, чтобы не побилась кодировка при скачивании. */
  window.__download = function (name) {
    const tsv = window.__toTsv(false);
    const bytes = new TextEncoder().encode(tsv);
    let bin = '';
    const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    }
    const blob = new Blob([btoa(bin)], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name || 'playlist.b64';
    document.body.appendChild(a);
    a.click();
    a.remove();
    return { rows: window.__extract().length, name: a.download };
  };

  return 'spotify engine loaded';
})();

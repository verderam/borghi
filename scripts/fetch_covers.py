#!/usr/bin/env python3
"""Scarica le immagini di copertina per le schede idea.

Per ogni scheda in content/idee:
- se nel testo e' presente un link esterno, scarica un'immagine dal sito
  indicato (og:image / twitter:image / prima immagine grande della pagina);
- altrimenti cerca una foto liberamente riutilizzabile su Wikimedia Commons.

Salva il risultato in static/images/covers/idea-NNN.jpg, aggiorna il front
matter (cover, cover_alt) e scrive static/images/covers/ATTRIBUZIONE.md con
i crediti delle foto Commons.

Uso: python scripts/fetch_covers.py [--limit N] [--only NNN]
"""

import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IDEE_DIR = ROOT / "content" / "idee"
COVERS_DIR = ROOT / "static" / "images" / "covers"
ATTRIBUTIONS = COVERS_DIR / "ATTRIBUZIONE.md"
CREDITS_JSON = COVERS_DIR / ".credits.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = (8, 12)
MAX_BYTES = 10 * 1024 * 1024
MIN_WIDTH = 500

STOPWORDS = {
    "coltivazione", "coltivazioni", "allevamento", "recupero", "rilancio",
    "di", "del", "della", "delle", "dei", "dello", "e", "ed", "in", "da",
    "un", "una", "uno", "allo", "stato", "per", "con", "o", "a", "il",
    "la", "le", "i", "lo", "fuori", "suolo", "aperto",
}
SKIP_HOSTS = {"facebook.com", "www.facebook.com", "instagram.com",
              "www.instagram.com"}

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

session = requests.Session()
session.headers.update({"User-Agent": UA})


def read_idea(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    front, body = m.group(1), m.group(2)
    title = re.search(r"^title:\s*(.+)$", front, re.M).group(1).strip()
    links = re.findall(r"\]\(\s*(https?://[^)\s]+?)\s*\)", body)
    link = links[0].rstrip("$.,;") if links else None
    return text, title, link


def fetch_page(url):
    """Scarica la pagina; se http fallisce riprova in https.
    Segue anche i redirect via meta refresh."""
    for candidate in (url, re.sub(r"^http://", "https://", url)):
        try:
            r = session.get(candidate, timeout=TIMEOUT, allow_redirects=True)
            ctype = r.headers.get("content-type", "")
            if r.ok and "html" in ctype:
                m = re.search(
                    r"<meta[^>]+http-equiv=[\"']refresh[\"'][^>]+"
                    r"content=[\"']\s*\d+\s*;\s*URL=([^\"'>]+)", r.text, re.I)
                if m:
                    target = urljoin(r.url, m.group(1).strip())
                    try:
                        r2 = session.get(target, timeout=TIMEOUT)
                        if r2.ok and "html" in r2.headers.get(
                                "content-type", ""):
                            return r2.text, r2.url
                    except requests.RequestException:
                        pass
                return r.text, r.url
        except requests.RequestException:
            continue
    return None, None


def image_candidates(html, base_url):
    found = []
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        if re.search(r"(?:property|name)=[\"'](?:og:image|twitter:image)[\"']",
                     tag, re.I):
            m = re.search(r"content=[\"']([^\"']+)[\"']", tag, re.I)
            if m:
                found.append(urljoin(base_url, m.group(1)))
    for tag in re.findall(r"<img\b[^>]*>", html, re.I):
        m = re.search(r"\bsrc=[\"']([^\"']+)[\"']", tag, re.I)
        if not m:
            continue
        src = m.group(1)
        low = src.lower()
        if any(bad in low for bad in ("logo", "icon", "sprite", "blank",
                                      "avatar", "pixel", "spacer", "loader",
                                      "placeholder", ".svg", ".gif")):
            continue
        found.append(urljoin(base_url, src))
    return found


def download_image(url):
    """Scarica e valida un'immagine raster; ritorna bytes o None."""
    try:
        with session.get(url, timeout=TIMEOUT, stream=True) as r:
            if not r.ok:
                return None
            if not r.headers.get("content-type", "").startswith("image/"):
                return None
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > MAX_BYTES:
                    return None
        if len(data) < 15_000:
            return None
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            if im.format in ("GIF", "ICO") or im.width < MIN_WIDTH:
                return None
            ratio = im.width / im.height
            if ratio < 0.5 or ratio > 2.4:
                return None
        return data
    except (requests.RequestException, OSError):
        return None


def site_image(url):
    host = urlparse(url).netloc.lower()
    if host in SKIP_HOSTS:
        return None
    html, final_url = fetch_page(url)
    if not html:
        return None
    for candidate in image_candidates(html, final_url):
        data = download_image(candidate)
        if data:
            return data
    return None


def commons_queries(title):
    """Varianti di ricerca: titolo, parole chiave, singole parole."""
    words = [w for w in re.split(r"[^\w']+", title.lower()) if w]
    kept = [w for w in words if w not in STOPWORDS and len(w) > 2]
    queries = [title]
    if kept:
        queries.append(" ".join(kept))
        queries.extend(sorted(set(kept), key=len, reverse=True))
    return queries


def commons_image(query):
    """Cerca su Wikimedia Commons; ritorna (bytes, credito) o (None, None)."""
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6,
        "gsrlimit": 10, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1200,
    }
    try:
        for attempt in range(4):
            try:
                r = session.get(COMMONS_API, params=params, timeout=TIMEOUT)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 3:
                    return None, None
                time.sleep(3 * (attempt + 1))
        pages = r.json().get("query", {}).get("pages", {})
    except ValueError:
        return None, None
    for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if info.get("width", 0) < 600:
            continue
        data = download_image(info.get("thumburl") or info.get("url", ""))
        if not data:
            continue
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "",
                        meta.get("Artist", {}).get("value", "sconosciuto"))
        license_ = meta.get("LicenseShortName", {}).get("value", "sconosciuta")
        credit = {"file": page.get("title", ""), "author": artist.strip(),
                  "license": license_, "url": info.get("descriptionurl", "")}
        return data, credit
    return None, None


def save_jpeg(data, dest):
    with Image.open(io.BytesIO(data)) as im:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.getchannel("A"))
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((1200, 1200), Image.LANCZOS)
        im.save(dest, "JPEG", quality=82, optimize=True)


def update_front_matter(path, text, title, cover_rel):
    text = re.sub(r"^cover:.*$", f"cover: {cover_rel}", text,
                  count=1, flags=re.M)
    text = re.sub(r"^cover_alt:.*$",
                  f"cover_alt: Foto di copertina per {title}", text,
                  count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def process(path, commons_only=False):
    num = re.match(r"(\d+)-", path.name).group(1)
    dest = COVERS_DIR / f"idea-{num}.jpg"
    text, title, link = read_idea(path)
    data, source, credit = None, None, None
    if link and not commons_only:
        data = site_image(link)
        if data:
            source = "sito"
    if not data:
        for query in commons_queries(title):
            data, credit = commons_image(query)
            if data:
                source = "commons"
                break
    if not data:
        return {"file": path.name, "title": title, "link": link,
                "source": "errore"}
    save_jpeg(data, dest)
    update_front_matter(path, text, title, f"/images/covers/idea-{num}.jpg")
    return {"file": path.name, "title": title, "link": link,
            "source": source, "credit": credit}


def main():
    limit, only = None, None
    args = sys.argv[1:]
    commons_only = "--commons-only" in args
    args = [a for a in args if a != "--commons-only"]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--only" in args:
        only = args[args.index("--only") + 1]
    paths = [p for p in sorted(IDEE_DIR.glob("*.md"))
             if re.match(r"\d+-", p.name)]
    if only:
        paths = [p for p in paths if p.name.startswith(only)]
    if limit:
        paths = paths[:limit]

    started = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process, p, commons_only): p for p in paths}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            print(f"[{res['source']:>7}] {res['file']}", flush=True)

    results.sort(key=lambda r: r["file"])
    credits = {}
    if CREDITS_JSON.exists():
        credits = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    for r in results:
        if r["source"] == "commons" and r.get("credit"):
            credits[r["file"]] = r["credit"]
    CREDITS_JSON.write_text(json.dumps(credits, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    if credits:
        lines = ["# Attribuzione foto di copertina (Wikimedia Commons)", ""]
        for fname in sorted(credits):
            c = credits[fname]
            lines.append(f"- `{Path(fname).stem}` — {c['file']}, "
                         f"autore: {c['author']}, licenza {c['license']}. "
                         f"{c['url']}")
        ATTRIBUTIONS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {}
    for r in results:
        summary[r["source"]] = summary.get(r["source"], 0) + 1
    print(json.dumps(summary, ensure_ascii=False))
    print(f"completato in {time.time() - started:.0f}s")
    errors = [r["file"] for r in results if r["source"] == "errore"]
    if errors:
        print("errori:", *errors, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()

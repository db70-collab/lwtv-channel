#!/usr/bin/env python3
"""Generatore del sito LWTV Channel.

Legge i video del canale YouTube (feed RSS oppure API), li unisce ai testi di
approfondimento in content/ e ai file in downloads/, e scrive il sito statico
nella cartella public/.

Uso normale:        python build.py
Prova in locale:    python build.py --feed-file tests/feed-prova.xml --data-dir /tmp/prova
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


# ---------------------------------------------------------------- utilità

def norm(text):
    """Minuscolo, senza accenti: serve per confrontare parole chiave."""
    t = unicodedata.normalize("NFKD", text or "")
    return t.encode("ascii", "ignore").decode().lower()


def slugify(text):
    t = re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")
    return t[:70].strip("-") or "video"


def unique_slug(title, used):
    base = slugify(title)
    slug, n = base, 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def data_it(dt):
    return f"{dt.day} {MESI[dt.month - 1]} {dt.year}"


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def plain_text(html_text):
    t = re.sub(r"<[^>]+>", " ", html_text or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def excerpt(text, limit=150):
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:- ")
    return cut + "…"


def hashtags(text):
    return [h.lower() for h in re.findall(r"#([A-Za-z0-9_À-ÿ]+)", text or "")]


def description_to_html(desc):
    """Descrizione YouTube -> HTML sicuro (testo, link cliccabili, niente hashtag)."""
    desc = re.sub(r"(?:(?<=\s)|^)#[A-Za-z0-9_À-ÿ]+", "", desc or "")
    desc = desc.strip()
    if not desc:
        return ""
    paragraphs = re.split(r"\n\s*\n", desc)
    out = []
    for p in paragraphs:
        safe = html.escape(p.strip())
        safe = re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" rel="noopener nofollow" target="_blank">\1</a>',
            safe,
        )
        out.append("<p>" + safe.replace("\n", "<br>") + "</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- YouTube

def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "lwtv-site-builder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        if not vid:
            continue
        out.append({
            "id": vid.strip(),
            "title": (e.findtext("a:title", namespaces=NS) or "").strip(),
            "published": (e.findtext("a:published", namespaces=NS) or "").strip(),
            "description": (e.findtext("media:group/media:description", namespaces=NS) or "").strip(),
        })
    return out


def parse_api_page(data):
    out = []
    for it in data.get("items", []):
        sn = it.get("snippet", {})
        vid = sn.get("resourceId", {}).get("videoId")
        title = sn.get("title", "")
        if not vid or title in ("Private video", "Deleted video"):
            continue
        out.append({
            "id": vid,
            "title": title.strip(),
            "published": it.get("contentDetails", {}).get("videoPublishedAt") or sn.get("publishedAt", ""),
            "description": (sn.get("description") or "").strip(),
        })
    return out


def fetch_rss(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return parse_feed(http_get(url))


def fetch_api(channel_id, key):
    """Tutti i video del canale (playlist 'caricamenti'), 50 alla volta."""
    uploads = "UU" + channel_id[2:]
    items, token = [], None
    while True:
        params = {"part": "snippet,contentDetails", "playlistId": uploads,
                  "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        data = json.loads(http_get(
            "https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params)))
        items += parse_api_page(data)
        token = data.get("nextPageToken")
        if not token:
            break
    return items


def update_cache(cache_file, fetched):
    cache = {"videos": {}}
    if cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    vids = cache.setdefault("videos", {})
    used = {v["slug"] for v in vids.values()}
    new = 0
    for f in fetched:
        cur = vids.get(f["id"])
        if cur:
            cur["title"] = f["title"] or cur["title"]
            cur["description"] = f["description"] or cur.get("description", "")
            cur["published"] = f["published"] or cur["published"]
        else:
            vids[f["id"]] = {
                "id": f["id"], "slug": unique_slug(f["title"], used),
                "title": f["title"], "published": f["published"],
                "description": f["description"],
            }
            new += 1
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")
    return cache, new


# ---------------------------------------------------------------- contenuti

def read_md(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        return meta, m.group(2)
    return {}, raw


def md_to_html(body, base):
    h = markdown.markdown(body, extensions=["extra", "sane_lists"], output_format="html5")
    h = re.sub(r'(src|href)="/(?!/)', lambda m: f'{m.group(1)}="{base}/', h)
    h = h.replace("<table>", '<table class="table table-dark table-sm align-middle">')
    return h


def load_md_dir(folder):
    """id video (primi 11 caratteri del nome file) -> (meta, corpo)."""
    out = {}
    if folder.exists():
        for p in sorted(folder.glob("*.md")):
            out[p.stem[:11]] = read_md(p)
    return out


def load_hidden(path):
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line[:11])
    return ids


def keyword_section(text, sections):
    text = norm(text)
    best, best_score = None, 0
    for s in sections:
        score = 0
        for k in s.get("parole_chiave", []):
            if re.search(r"(?<![a-z0-9])" + re.escape(norm(k)) + r"(?![a-z0-9])", text):
                score += 1
        if score > best_score:
            best, best_score = s, score
    return best


def classify(video, meta, sections, hidden):
    """Restituisce (sezione, motivo). Sezione None = video non pubblicato."""
    if video["id"] in hidden or meta.get("nascondi"):
        return None, "nascosto a mano"
    wanted = norm(str(meta.get("sezione", "")))
    if wanted:
        for s in sections:
            if wanted in (norm(s["slug"]), norm(s["hashtag"]), norm(s["nome"])):
                return s, "indicata nel file di testo"
    tags = hashtags(video.get("description", "")) + hashtags(video.get("title", ""))
    for s in sections:
        if s["hashtag"].lower() in tags:
            return s, "hashtag"
    s = keyword_section(video.get("title", ""), sections)
    if s:
        return s, "parole nel titolo"
    return None, "non classificato"


def collect_downloads(folder, vid, base):
    d = folder / vid
    files = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                files.append({
                    "nome": p.name,
                    "ext": (p.suffix[1:] or "file").upper()[:5],
                    "dimensione": human_size(p.stat().st_size),
                    "url": f"{base}/files/{vid}/{urllib.parse.quote(p.name)}",
                    "path": p,
                })
    return files


def build_videos(cache, cfg, md_by_id, hidden, dl_dir, base):
    sections = cfg["sezioni"]
    ignored = set(cfg.get("hashtag_ignorati", []))
    section_tags = {s["hashtag"].lower() for s in sections}
    videos, elenco = [], []
    for v in sorted(cache["videos"].values(), key=lambda x: x["published"], reverse=True):
        meta, body = md_by_id.get(v["id"], ({}, ""))
        sec, why = classify(v, meta, sections, hidden)
        has_text = bool(body.strip())
        stato = "NASCOSTO" if sec is None else f"pubblicato in {sec['nome']}"
        elenco.append(f"{v['id']} | {v['published'][:10]} | {stato} ({why}) | "
                      f"approfondimento: {'si' if has_text else 'no'} | {v['title']}")
        if sec is None:
            continue
        try:
            dt = datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
        except ValueError:
            dt = datetime(2000, 1, 1)
        tags = [str(t).lower() for t in (meta.get("tag") or [])]
        for h in hashtags(v.get("description", "")):
            if h not in section_tags and h not in ignored and h not in tags:
                tags.append(h)
        tags = tags[:8]
        title = str(meta.get("titolo") or v["title"])
        body_html = md_to_html(body, base) if has_text else ""
        desc_html = description_to_html(v.get("description", ""))
        files = collect_downloads(dl_dir, v["id"], base)
        ex_source = plain_text(body_html) if has_text else v.get("description", "")
        videos.append({
            "id": v["id"], "slug": v["slug"], "titolo": title,
            "data": dt, "data_it": data_it(dt), "data_iso": dt.date().isoformat(),
            "sezione": sec, "tag": tags,
            "approfondimento": body_html, "descrizione_html": desc_html,
            "estratto": excerpt(ex_source), "file": files,
            "miniatura": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
        })
    return videos, elenco


# ---------------------------------------------------------------- scrittura sito

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_tree(src, dst):
    if not src.exists():
        return
    for p in src.rglob("*"):
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(src).parts):
            target = dst / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--feed-file", help="usa un feed RSS salvato in locale (solo per prove)")
    ap.add_argument("--no-fetch", action="store_true", help="non contattare YouTube, usa la cache")
    ap.add_argument("--data-dir", default=str(ROOT / "data"), help="cartella della cache (default: data)")
    ap.add_argument("--out", default=str(ROOT / "public"), help="cartella di uscita (default: public)")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    base = os.environ.get("BASE_PATH", cfg.get("base_path", "")).rstrip("/")
    site_url = os.environ.get("SITE_URL", cfg.get("url_sito", "")).rstrip("/")
    data_dir = Path(args.data_dir)
    out = Path(args.out)

    # 1. video da YouTube
    fetched = []
    if args.feed_file:
        fetched = parse_feed(Path(args.feed_file).read_bytes())
        print(f"Feed di prova letto: {len(fetched)} video")
    elif not args.no_fetch:
        key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        if key:
            try:
                fetched = fetch_api(cfg["channel_id"], key)
                print(f"YouTube API: {len(fetched)} video")
            except Exception as e:  # noqa: BLE001
                print(f"ATTENZIONE: API YouTube non riuscita ({e}); provo con il feed RSS")
        if not fetched:
            try:
                fetched = fetch_rss(cfg["channel_id"])
                print(f"Feed RSS: {len(fetched)} video")
            except Exception as e:  # noqa: BLE001
                print(f"ATTENZIONE: impossibile leggere YouTube ({e}); uso solo i video già salvati")
    cache, new = update_cache(data_dir / "videos.json", fetched)
    print(f"Video in archivio: {len(cache['videos'])} (nuovi: {new})")

    # 2. contenuti e classificazione
    md_by_id = load_md_dir(ROOT / "content" / "videos")
    hidden = load_hidden(ROOT / "content" / "nascosti.txt")
    videos, elenco = build_videos(cache, cfg, md_by_id, hidden, ROOT / "downloads", base)
    write(data_dir / "elenco-video.txt",
          "# Elenco di tutti i video del canale e di come vengono trattati dal sito.\n"
          "# Formato: ID | data | stato | approfondimento | titolo\n" + "\n".join(elenco) + "\n")
    print(f"Video pubblicati sul sito: {len(videos)} su {len(cache['videos'])}")

    # 3. pagine libere (chi siamo, privacy...)
    pages = []
    pages_dir = ROOT / "content" / "pages"
    if pages_dir.exists():
        for p in sorted(pages_dir.glob("*.md")):
            meta, body = read_md(p)
            pages.append({"slug": p.stem, "titolo": meta.get("titolo", p.stem.replace("-", " ").title()),
                          "descrizione": meta.get("descrizione", ""), "html": md_to_html(body, base)})

    # 4. generazione
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.globals.update(cfg=cfg, sections=cfg["sezioni"], url=lambda p: base + p,
                       site_url=site_url, anno=datetime.now().year)

    def render(template, dest, **ctx):
        ctx.setdefault("canonical", site_url + dest.replace("index.html", "") if site_url else "")
        write(out / dest.lstrip("/"), env.get_template(template).render(**ctx))

    with_files = [v for v in videos if v["file"]]
    render("home.html", "/index.html", ultimo=videos[0] if videos else None,
           recenti=videos[1:7] if len(videos) > 1 else [], con_file=with_files[:5],
           totale=len(videos), page_title="")
    for s in cfg["sezioni"]:
        vs = [v for v in videos if v["sezione"]["slug"] == s["slug"]]
        counts = {}
        for v in vs:
            for t in v["tag"]:
                counts[t] = counts.get(t, 0) + 1
        top_tags = [t for t, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:14]]
        render("section.html", f"/{s['slug']}/index.html", sezione=s, video=vs, tag_top=top_tags,
               page_title=s["nome"], meta_description=s["descrizione"])
    for v in videos:
        simili = [x for x in videos if x["id"] != v["id"] and x["sezione"]["slug"] == v["sezione"]["slug"]]
        simili.sort(key=lambda x: (-len(set(x["tag"]) & set(v["tag"])), -x["data"].timestamp()))
        render("video.html", f"/video/{v['slug']}/index.html", v=v, simili=simili[:3],
               page_title=v["titolo"], meta_description=excerpt(v["estratto"] or v["titolo"], 155))
    render("downloads.html", "/download/index.html", gruppi=with_files, page_title="Download",
           meta_description="File da scaricare dei progetti di LWTV Channel: schemi, modelli 3D, script e documenti.")
    for p in pages:
        render("page.html", f"/{p['slug']}/index.html", pagina=p, page_title=p["titolo"],
               meta_description=p["descrizione"])
    render("404.html", "/404.html", page_title="Pagina non trovata", canonical="")

    # 5. file statici, download, sitemap
    copy_tree(ROOT / "static", out / "static")
    copy_tree(ROOT / "media", out / "media")
    copy_tree(ROOT / "radice", out)
    for v in with_files:
        for f in v["file"]:
            dest = out / "files" / v["id"] / f["nome"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f["path"], dest)
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy2(cname, out / "CNAME")
    write(out / ".nojekyll", "")

    urls = ["/"] + [f"/{s['slug']}/" for s in cfg["sezioni"]] + ["/download/"] \
        + [f"/{p['slug']}/" for p in pages] + [f"/video/{v['slug']}/" for v in videos]
    if site_url:
        items = "".join(f"<url><loc>{html.escape(site_url + u)}</loc></url>" for u in urls)
        write(out / "sitemap.xml",
              '<?xml version="1.0" encoding="UTF-8"?>\n'
              f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>\n')
        write(out / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n")
    else:
        write(out / "robots.txt", "User-agent: *\nAllow: /\n")

    print(f"Sito generato in {out} ({len(urls)} pagine)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

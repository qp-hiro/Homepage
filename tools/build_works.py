# -*- coding: utf-8 -*-
"""
build_works.py — Generate the Works section of the site from the Google Drive folder.

Source of truth:  H:\マイドライブ\Homepage\Files_for_works\workN\
  - Paper PDFs            -> title / subtitle / year / abstract (auto-extracted)
  - Other PDFs (figures)  -> converted to PNG for the gallery
  - PNG/JPG images        -> resized (max 1800px) and optimized into works/img/workN/

Outputs (owned by this script — do not edit by hand):
  - works/img/workN/*               optimized web images (stale files are pruned)
  - works/workN-details.html        detail pages
  - works/works-data.js             card data consumed by works.html
  - index.html                      cascade block between WORKS:AUTO markers
  - llms-full.txt                   works list between WORKS:AUTO markers
  - chatbot.js                      works answer between WORKS:AUTO markers

Manual knobs live in works/works-overrides.json (tags, youtube, subtitles,
Japanese descriptions, thumbnail choice, hidden flag, abstract override).

Usage:
  python tools/build_works.py           # regenerate
  python tools/build_works.py --push    # regenerate + git commit & push if changed
"""
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys

import fitz  # PyMuPDF
from PIL import Image

DRIVE_DIR = r"H:\マイドライブ\Homepage\Files_for_works"
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = "https://qp-hiro.github.io/Homepage"
OVERRIDES_PATH = os.path.join(REPO_DIR, "works", "works-overrides.json")
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".works_cache.json")
MAX_IMG_WIDTH = 1800
JPEG_QUALITY = 87
PDF_RENDER_ZOOM = 2.2

MARK_BEGIN = "WORKS:AUTO:BEGIN"
MARK_END = "WORKS:AUTO:END"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

warnings = []


def warn(msg):
    warnings.append(msg)
    print("WARN: " + msg)


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(name):
    base = os.path.splitext(name)[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
    if not slug:
        slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return slug


# ---------------------------------------------------------------- PDF parsing

def pdf_text(doc, max_pages=2):
    return "\n".join(doc[i].get_text() for i in range(min(max_pages, doc.page_count)))


def is_paper_pdf(doc):
    text = pdf_text(doc)
    low = text.lower()
    if "abstract" in low or "概要" in text:
        return True
    return doc.page_count >= 2 and len(text) > 2000


def extract_title(doc):
    """Largest-font horizontal text spans on page 1, in reading order.
    Rotated text (e.g. the arXiv sidebar stamp) is excluded."""
    spans = []
    for block in doc[0].get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            d = line.get("dir", (1, 0))
            if abs(d[0]) < 0.99:
                continue
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t and "arxiv" not in t.lower():
                    spans.append(span)
    if not spans:
        return ""
    max_size = max(s["size"] for s in spans)
    parts = [s["text"].strip() for s in spans if s["size"] > max_size - 0.5]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


# hard section boundaries that end an abstract
ABSTRACT_STOP = (r"(?:CCS\s+Concepts?|CCS\s+CONCEPTS|Keywords?\s*\n|KEYWORDS|Index\s+Terms|"
                 r"ACM\s+Reference|\n\s*1\.?\s*\n?\s*I(?:ntroduction|NTRODUCTION))")
# boilerplate lines that may be injected into the abstract's text flow (ACM footer block)
JUNK_LINE = re.compile(
    r"^\s*(?:This work is licensed|Permission to make|©|ACM ISBN|https?://doi\.org|arXiv:|\d{1,4}\s*$)")
VENUE_LINE = re.compile(r"[’']\d{2},\s+\S")  # e.g. "IUI ’26, Paphos, Cyprus"


def _clean_abstract_block(block):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not JUNK_LINE.match(ln) and not VENUE_LINE.search(ln)]
    text = "\n".join(lines).replace("-\n", "")
    return re.sub(r"\s+", " ", text).strip()


def extract_abstract(doc):
    text = pdf_text(doc)
    # 1) labeled abstract ("Abstract" heading), junk lines removed from the window
    m = re.search(r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\n](.*?)(?=%s)" % ABSTRACT_STOP, text, re.S)
    if m:
        abstract = _clean_abstract_block(m.group(1))
        if len(abstract) > 150:
            return abstract
    # 2) unlabeled abstract (arXiv ACM small format, CHI review format):
    #    accumulate the narrative lines directly above the first section
    #    boundary, stopping at a figure caption, image, or author line.
    IMAGE = "\x00IMAGE"
    blocks = []
    for i in range(min(2, doc.page_count)):
        for b in doc[i].get_text("blocks"):
            if len(b) > 6 and b[6] != 0:
                blocks.append(IMAGE)
                continue
            t = b[4].strip()
            if t:
                blocks.append(t)
    boundary = re.compile(
        r"^(?:CCS\s+Concepts?|Additional\s+Key\s+Words|Keywords|KEYWORDS|Index\s+Terms|"
        r"ACM\s+Reference|(?:1\.?\s*\n?\s*)?I(?:ntroduction|NTRODUCTION)\s*(?:\n|$))")
    idx = next((i for i, b in enumerate(blocks)
                if b != IMAGE and (boundary.match(b)
                                   or re.search(r"\n1\.?\s*\n\s*I(?:ntroduction|NTRODUCTION)", b))),
               len(blocks))
    collected = []
    for b in reversed(blocks[:idx]):
        if re.fullmatch(r"[\d\s]+", b):
            continue  # line-number gutter / page numbers
        if (b == IMAGE
                or re.match(r"(?:Fig(?:ure)?|図)\.?\s*\d", b)   # figure caption
                or re.match(r"[A-Z][A-Z∗*]{3,}", b)             # author / all-caps heading line
                or b.startswith("Permission to make") or b.startswith("This work is licensed")):
            break
        collected.append(b)
    collected.reverse()
    abstract = _clean_abstract_block("\n".join(collected))
    return abstract if len(abstract) > 150 else ""


def extract_year(doc):
    years = [int(y) for y in re.findall(r"\b(20[0-4][0-9])\b", pdf_text(doc, 1))]
    return str(max(years)) if years else ""


# ---------------------------------------------------------------- image build

def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            return json.loads(read_text(CACHE_PATH))
        except Exception:
            pass
    return {}


def build_image(src, out_dir, slug, cache):
    """Convert one source asset (image or figure PDF) into an optimized web image.
    Returns the output filename, or None on failure."""
    key = src
    digest = sha1_of(src)
    ext = os.path.splitext(src)[1].lower()
    cached = cache.get(key)
    if cached and cached.get("sha1") == digest and os.path.exists(os.path.join(out_dir, cached.get("out", ""))):
        return cached["out"]
    try:
        if ext == ".pdf":
            doc = fitz.open(src)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM))
            im = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            im = Image.open(src)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if im.width > MAX_IMG_WIDTH:
            im = im.resize((MAX_IMG_WIDTH, round(im.height * MAX_IMG_WIDTH / im.width)), Image.LANCZOS)
        # encode both ways; prefer JPEG when clearly smaller (photos), PNG otherwise (diagrams)
        png_buf, jpg_buf = io.BytesIO(), io.BytesIO()
        im.save(png_buf, format="PNG", optimize=True)
        im.convert("RGB").save(jpg_buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        use_jpg = ext in (".jpg", ".jpeg") or jpg_buf.tell() < png_buf.tell() * 0.5
        out_name = slug + (".jpg" if use_jpg else ".png")
        with open(os.path.join(out_dir, out_name), "wb") as f:
            f.write((jpg_buf if use_jpg else png_buf).getvalue())
    except Exception as e:
        warn("image conversion failed for %s: %s" % (src, e))
        return None
    cache[key] = {"sha1": digest, "out": out_name}
    return out_name


# ---------------------------------------------------------------- work model

def collect_work(folder, num, overrides, cache):
    """Scan one Drive workN folder and return a work dict, or None if unusable."""
    ov = overrides.get("work%d" % num, {})
    entries = sorted(os.listdir(folder))
    papers, assets = [], []
    for name in entries:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext == ".pdf":
            try:
                doc = fitz.open(path)
            except Exception as e:
                warn("cannot open PDF %s: %s" % (path, e))
                continue
            (papers if is_paper_pdf(doc) else assets).append(path)
        elif ext in IMG_EXTS:
            assets.append(path)

    # primary paper: prefer an extractable English abstract, then newest modified
    paper_info = {}
    candidates = []
    for p in papers:
        doc = fitz.open(p)
        abstract = extract_abstract(doc)
        ascii_letters = sum(1 for ch in abstract if ch.isascii() and ch.isalpha())
        letters = sum(1 for ch in abstract if ch.isalpha())
        is_english = letters > 0 and ascii_letters / letters > 0.7
        candidates.append((bool(abstract), is_english, os.path.getmtime(p), p, doc, abstract))
    if candidates:
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        _, _, _, ppath, pdoc, abstract = candidates[-1]
        paper_info = {
            "title": extract_title(pdoc),
            "abstract": abstract,
            "year": extract_year(pdoc),
            "path": ppath,
        }

    auto_title = paper_info.get("title", "")
    if ":" in auto_title:
        auto_main, auto_sub = [s.strip() for s in auto_title.split(":", 1)]
    else:
        auto_main, auto_sub = auto_title, ""
    title = ov.get("title") or auto_main
    subtitle = ov.get("subtitle", auto_sub)

    abstract = ov.get("abstract") or paper_info.get("abstract", "")
    year = ov.get("year") or paper_info.get("year", "")

    hidden = ov.get("hidden", False) or not (title and abstract and year and assets)
    if not ov.get("hidden", False) and hidden and (papers or assets):
        missing = [k for k, v in
                   [("paper/title", title), ("abstract", abstract), ("year", year), ("images", assets)] if not v]
        warn("work%d is hidden: missing %s (folder: %s)" % (num, ", ".join(missing), folder))

    work = {
        "num": num,
        "hidden": hidden,
        "title": title,
        "subtitle": subtitle,
        "subtitle_jp": ov.get("subtitle_jp", ""),
        "desc_en": ov.get("desc_en") or subtitle,
        "desc_jp": ov.get("desc_jp", ""),
        "tags": ov.get("tags", ""),
        "year": year,
        "youtube": ov.get("youtube", ""),
        "abstract": abstract,
        "images": [],
    }
    if hidden:
        return work

    # build images; thumbnail first
    out_dir = os.path.join(REPO_DIR, "works", "img", "work%d" % num)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    thumb_src = ov.get("thumbnail", "")
    ordered = sorted(assets, key=lambda p: (os.path.basename(p) != thumb_src,
                                            "main" not in os.path.basename(p).lower(),
                                            "teaser" not in os.path.basename(p).lower(),
                                            os.path.basename(p)))
    produced = []
    for src in ordered:
        out_name = build_image(src, out_dir, slugify(os.path.basename(src)), cache)
        if out_name:
            produced.append(out_name)
    # prune stale outputs
    for name in os.listdir(out_dir):
        if name not in produced:
            os.remove(os.path.join(out_dir, name))
    if not produced:
        work["hidden"] = True
        warn("work%d hidden: no usable images" % num)
        return work
    work["images"] = produced
    return work


# ---------------------------------------------------------------- generators

DETAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Hirosuke Asahi</title>
    <link rel="stylesheet" href="../styles.css">

    <script async src="https://www.googletagmanager.com/gtag/js?id=G-7S7V1ZM4MJ"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', 'G-7S7V1ZM4MJ');
    </script>
</head>
<body>

    <header class="topbar">
        <a href="../index.html" class="mark">
            <span>Hirosuke Asahi</span>
            <span class="jp">旭 博佑</span>
        </a>
        <button class="nav-toggle" aria-label="Menu" aria-expanded="false">
            <span></span><span></span><span></span>
        </button>
        <nav class="primary-nav">
            <a href="../index.html#profile">Profile <span class="jp">プロフィール</span></a>
            <a href="../index.html#career">Career <span class="jp">経歴</span></a>
            <a href="../index.html#publications">Publications <span class="jp">業績</span></a>
            <a href="../works.html" class="is-current">Works <span class="jp">作品</span></a>
            <a href="../gallery.html">Gallery <span class="jp">写真</span></a>
            <a href="../index.html#contact">Contact <span class="jp">連絡</span></a>
        </nav>
    </header>

    <main class="detail-shell">
        <a href="../works.html" class="detail-back">← Back to Works</a>

        <header class="detail-head" data-reveal>
            <span class="detail-head__eyebrow">№ {num:02d} · {year}{tags_part}</span>
            <h1 class="detail-head__title">{title}</h1>
{subtitle_html}        </header>

        <section class="detail-body" data-reveal>
{video_html}            <div class="detail-abstract">
                <p class="detail-abstract__label">Abstract</p>
                <p class="detail-abstract__text">
                    {abstract}
                </p>
            </div>
        </section>

        <section class="detail-gallery" data-reveal>
{gallery_html}        </section>
    </main>

    <div class="lightbox" role="dialog" aria-modal="true">
        <span class="lightbox__close">[ ESC to close ]</span>
        <img src="" alt="">
    </div>

    <footer class="page-foot">
        <span>© 2025 Hirosuke Asahi</span>
        <span><a href="../works.html">↑ Back to Works</a></span>
    </footer>

    <script src="../main.js"></script>
    <script src="../chatbot.js" defer></script>
</body>
</html>
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gen_detail_page(w):
    tags_part = " · %s" % esc(w["tags"]) if w["tags"] else ""
    subtitle_html = ""
    if w["subtitle"]:
        subtitle_html = '            <p class="detail-head__subtitle">— %s</p>\n' % esc(w["subtitle"])
    video_html = ""
    if w["youtube"]:
        # click-to-play poster: avoids YouTube's refusal to embed on file:// previews
        # and defers the heavy iframe until the visitor actually wants the video
        video_html = (
            '            <div class="video-frame" data-youtube="%s" role="button" tabindex="0" '
            'aria-label="Play video: %s">\n'
            '                <img class="video-frame__poster" '
            'src="https://img.youtube.com/vi/%s/hqdefault.jpg" alt="%s" loading="lazy">\n'
            '                <span class="video-frame__play" aria-hidden="true">&#9654;</span>\n'
            '            </div>\n' % (w["youtube"], esc(w["title"]), w["youtube"], esc(w["title"])))
    gallery_html = "".join(
        '            <img data-lightbox src="img/work%d/%s" alt="%s">\n' % (w["num"], name, esc(w["title"]))
        for name in w["images"])
    return DETAIL_TEMPLATE.format(
        title=esc(w["title"]), num=w["num"], year=w["year"], tags_part=tags_part,
        subtitle_html=subtitle_html, video_html=video_html,
        abstract=esc(w["abstract"]), gallery_html=gallery_html)


def gen_works_data(visible):
    items = []
    for w in visible:
        items.append(
            "    {\n"
            "        num: %d,\n"
            "        title: %s,\n"
            "        subtitle: %s,\n"
            "        year: %s,\n"
            "        imagePath: %s,\n"
            "        detailsPath: %s\n"
            "    }" % (
                w["num"], json.dumps(w["title"]), json.dumps(w["subtitle"]),
                json.dumps(w["year"]), json.dumps("works/img/work%d/%s" % (w["num"], w["images"][0])),
                json.dumps("works/work%d-details.html" % w["num"])))
    return ("// Generated by tools/build_works.py — do not edit by hand.\n"
            "const WORKS_DATA = [\n%s\n];\n" % ",\n".join(items))


def gen_cascade_items(visible):
    blocks = []
    for w in visible:
        jp = ' <span class="jp">%s</span>' % esc(w["subtitle_jp"]) if w["subtitle_jp"] else ""
        blocks.append(
            '            <a class="cascade__item" href="works/work%(num)d-details.html" data-reveal>\n'
            '                <div class="cascade__media">\n'
            '                    <img src="works/img/work%(num)d/%(img)s" alt="">\n'
            '                    <span class="cascade__num">№ %(num02)s</span>\n'
            '                    <span class="cascade__year">%(year)s</span>\n'
            '                    <span class="cascade__veil"></span>\n'
            '                    <span class="cascade__more">↗</span>\n'
            '                </div>\n'
            '                <div class="cascade__caption">\n'
            '                    <h3 class="cascade__title">%(title)s</h3>\n'
            '                    <span class="cascade__tags">%(tags)s</span>\n'
            '                    <p class="cascade__subtitle">%(desc)s%(jp)s</p>\n'
            '                </div>\n'
            '            </a>' % {
                "num": w["num"], "num02": "%02d" % w["num"], "img": w["images"][0],
                "year": w["year"], "title": esc(w["title"]), "tags": esc(w["tags"]),
                "desc": esc(w["desc_en"]), "jp": jp})
    return "\n\n".join(blocks)


def gen_llms_lines(visible):
    lines = []
    for i, w in enumerate(visible, 1):
        full = w["title"] + (": " + w["subtitle"] if w["subtitle"] else "")
        lines.append("%d. **%s** (%s) — %s — %s/works/work%d-details.html" % (
            i, full, w["year"], w["abstract"], SITE_URL, w["num"]))
    return "\n".join(lines)


def gen_chatbot_lines(visible):
    def li(w, desc):
        return '<li><a href="${ROOT(\'works/work%d-details.html\')}">%s</a> — %s (%s)</li>' % (
            w["num"], w["title"], desc, w["year"])
    jp_items = "".join(li(w, w["desc_jp"] or w["desc_en"]) for w in visible)
    en_items = "".join(li(w, w["desc_en"]) for w in visible)
    return (
        '            jp: `代表的な作品:<ul class="hcb-list">%s</ul>'
        '<a href="${ROOT(\'works.html\')}">作品一覧はこちら</a>。`,\n'
        '            en: `Selected works:<ul class="hcb-list">%s</ul>'
        'See the <a href="${ROOT(\'works.html\')}">Works page</a>.`' % (jp_items, en_items))


def replace_marked(path, new_body, comment=("<!--", "-->")):
    text = read_text(path)
    begin = " ".join(x for x in (comment[0], MARK_BEGIN, comment[1]) if x)
    end = " ".join(x for x in (comment[0], MARK_END, comment[1]) if x)
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        warn("markers not found in %s — skipped" % path)
        return
    write_text(path, pattern.sub(begin + "\n" + new_body + "\n" + end, text))


# ---------------------------------------------------------------------- main

def main():
    push = "--push" in sys.argv
    if not os.path.isdir(DRIVE_DIR):
        print("ERROR: Drive folder not found: " + DRIVE_DIR)
        sys.exit(1)

    overrides = json.loads(read_text(OVERRIDES_PATH)) if os.path.exists(OVERRIDES_PATH) else {}
    cache = load_cache()

    works = []
    for name in sorted(os.listdir(DRIVE_DIR)):
        m = re.fullmatch(r"work(\d+)", name)
        folder = os.path.join(DRIVE_DIR, name)
        if not m or not os.path.isdir(folder):
            continue
        if not os.listdir(folder):
            continue
        w = collect_work(folder, int(m.group(1)), overrides, cache)
        if w:
            works.append(w)

    visible = [w for w in works if not w["hidden"]]
    visible.sort(key=lambda w: (int(w["year"]), w["num"]), reverse=True)
    if not visible:
        print("ERROR: no visible works — aborting without touching the site.")
        sys.exit(1)

    # detail pages (remove pages of hidden works so stale content never lingers)
    for w in works:
        page = os.path.join(REPO_DIR, "works", "work%d-details.html" % w["num"])
        if w["hidden"]:
            if os.path.exists(page):
                os.remove(page)
                print("removed stale page: " + page)
            img_dir = os.path.join(REPO_DIR, "works", "img", "work%d" % w["num"])
            if os.path.isdir(img_dir):
                for f in os.listdir(img_dir):
                    os.remove(os.path.join(img_dir, f))
                os.rmdir(img_dir)
        else:
            write_text(page, gen_detail_page(w))

    write_text(os.path.join(REPO_DIR, "works", "works-data.js"), gen_works_data(visible))
    replace_marked(os.path.join(REPO_DIR, "index.html"), gen_cascade_items(visible))
    replace_marked(os.path.join(REPO_DIR, "llms-full.txt"), gen_llms_lines(visible))
    replace_marked(os.path.join(REPO_DIR, "chatbot.js"), gen_chatbot_lines(visible), comment=("//", ""))

    # stamp the "Last updated" date in llms-full.txt
    llms_path = os.path.join(REPO_DIR, "llms-full.txt")
    today = datetime.date.today().isoformat()
    write_text(llms_path, re.sub(r"> Last updated: \d{4}-\d{2}-\d{2}\.",
                                 "> Last updated: %s." % today, read_text(llms_path)))

    write_text(CACHE_PATH, json.dumps(cache, indent=1))
    print("OK: %d visible works (%s)" % (len(visible), ", ".join("work%d" % w["num"] for w in visible)))

    if push:
        paths = ["works", "index.html", "llms-full.txt", "chatbot.js"]
        subprocess.check_call(["git", "add", "--"] + paths, cwd=REPO_DIR)
        if subprocess.call(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR) != 0:
            subprocess.check_call(
                ["git", "commit", "-m",
                 "Auto-sync works from Drive\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
                cwd=REPO_DIR)
            subprocess.check_call(["git", "push"], cwd=REPO_DIR)
            print("pushed.")
        else:
            print("no changes to push.")


if __name__ == "__main__":
    main()

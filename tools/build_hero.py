# -*- coding: utf-8 -*-
"""
build_hero.py — Regenerate the hero background slideshow from Hero/.

Scans the Hero/ folder, sorts filenames alphabetically, and rewrites the
block between <!-- HERO:AUTO:BEGIN --> ... :END --> in index.html with
<img> tags that point at the local files.

Image rotation is handled by main.js; the first <img> gets `is-active`.

Usage:
  python tools/build_hero.py

Add / remove images: just drop .jpg|.jpeg|.png|.webp into Hero/ and push.
"""
import io
import os
import re
import sys
from urllib.parse import quote

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERO_DIR = os.path.join(REPO_DIR, "Hero")
HTML_PATH = os.path.join(REPO_DIR, "index.html")

MARK_BEGIN = "HERO:AUTO:BEGIN"
MARK_END = "HERO:AUTO:END"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def list_images():
    if not os.path.isdir(HERO_DIR):
        return []
    return sorted(
        fn for fn in os.listdir(HERO_DIR)
        if not fn.startswith(".") and os.path.splitext(fn)[1].lower() in IMG_EXTS
    )


def render_block(files):
    """Build the <img> tags that go between the HERO:AUTO markers.
    Filenames are URL-encoded so Japanese / spaces work."""
    lines = []
    for i, fn in enumerate(files):
        active = " is-active" if i == 0 else ""
        encoded = quote(fn)
        lines.append(
            f'            <img src="Hero/{encoded}" class="hero-bg__img{active}" alt="" loading="eager">'
        )
    return "\n".join(lines)


def replace_marked(path, new_body, comment=("<!--", "-->")):
    text = read_text(path)
    begin = " ".join(x for x in (comment[0], MARK_BEGIN, comment[1]) if x)
    end = " ".join(x for x in (comment[0], MARK_END, comment[1]) if x)
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        print(f"WARN: markers not found in {path} — skipped")
        return False
    write_text(path, pattern.sub(begin + "\n" + new_body + "\n            " + end, text))
    return True


def main():
    files = list_images()
    if not files:
        print(f"WARN: no images found in {HERO_DIR}")
    block = render_block(files)
    ok = replace_marked(HTML_PATH, block)
    if not ok:
        sys.exit(1)
    print(f"OK: {len(files)} hero images -> index.html")
    for f in files:
        print(f"  - Hero/{f}")


if __name__ == "__main__":
    main()

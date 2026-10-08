# -*- coding: utf-8 -*-
"""
build_publications.py — Regenerate the Publications & Achievements section
from publications.json.

Reads publications.json (source of truth) and injects regenerated HTML into
index.html between <!-- PUBLICATIONS:AUTO:BEGIN --> ... :END --> markers.
Also updates the "N items" per-group counts and keeps the Group B/C/D
`start=` and `counter-reset` offsets continuous so the CSS counter numbering
stays correct.

The llms-full.txt publications block is also regenerated between its own
`<!-- PUBLICATIONS:AUTO:BEGIN -->` markers.

Authors / cite text supports a simple `**text**` syntax to mark your own
name — it is rendered as `<span class="self">text</span>` in HTML and left
as `**text**` (markdown bold) in llms-full.txt.

Usage:
  python tools/build_publications.py
"""
import io
import json
import os
import re
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(REPO_DIR, "publications.json")
INDEX_PATH = os.path.join(REPO_DIR, "index.html")
LLMS_PATH = os.path.join(REPO_DIR, "llms-full.txt")

MARK_BEGIN = "PUBLICATIONS:AUTO:BEGIN"
MARK_END = "PUBLICATIONS:AUTO:END"


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_self_html(text):
    """Convert **word** → <span class="self">word</span>."""
    def repl(m):
        return '<span class="self">' + esc(m.group(1)) + "</span>"
    return re.sub(r"\*\*(.+?)\*\*", repl, esc(text))


def render_item_html(item):
    type_en = esc(item.get("type_en", ""))
    type_jp = esc(item.get("type_jp", ""))
    title = esc(item.get("title", ""))
    title_jp = item.get("title_jp") or ""
    authors = item.get("authors") or ""
    venue = esc(item.get("venue", ""))
    year = esc(str(item.get("year", "")))
    links = item.get("links") or []

    type_html = type_en
    if type_jp:
        type_html = f'{type_en} <span class="jp">{type_jp}</span>'
    # HTML entities inside types ("Oral & Poster" needs amp)
    type_html = type_html.replace("&amp;", "&").replace("&", "&amp;")
    # Restore <span> escaping we accidentally doubled
    type_html = type_html.replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;")

    title_html = title
    if title_jp:
        title_html = f'{title} <span class="jp">{esc(title_jp)}</span>'

    cite_html = ""
    if authors:
        cite_html = f'                        <p class="ach__cite">{render_self_html(authors)}</p>\n'

    venue_text = venue
    if year:
        venue_text = f"{venue} · {year}" if venue else year

    if links:
        link_html = "".join(
            f'<a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["text"])}</a>'
            for l in links
        )
        venue_block = (
            '                        <p class="ach__venue">\n'
            f'                            {venue_text}\n'
            f'                            <span class="ach__links">{link_html}</span>\n'
            '                        </p>\n'
        )
    else:
        venue_block = f'                        <p class="ach__venue">{venue_text}</p>\n'

    return (
        "                <li>\n"
        f'                    <span class="ach__type">{type_html}</span>\n'
        '                    <div class="ach__body">\n'
        f'                        <p class="ach__title">{title_html}</p>\n'
        f'{cite_html}'
        f'{venue_block}'
        '                    </div>\n'
        "                </li>"
    )


def render_group_html(group, start_idx):
    """Return (html_block, next_start_idx)."""
    items = group.get("items", [])
    n = len(items)
    title_en = esc(group["title_en"])
    title_jp = esc(group["title_jp"])

    item_blocks = []
    for i, it in enumerate(items):
        comment_idx = start_idx + i
        item_blocks.append(f"                <!-- {comment_idx:02d} -->\n" + render_item_html(it))
    ol_attrs = ""
    if start_idx > 1:
        ol_attrs = f' start="{start_idx}" style="counter-reset: ach {start_idx - 1};"'

    block = (
        '        <div class="ach-group" data-reveal>\n'
        '            <h3 class="ach-group__title">\n'
        f'                <span>{title_en}</span>\n'
        f'                <span class="jp">{title_jp}</span>\n'
        f'                <span class="count">{n} items</span>\n'
        '            </h3>\n'
        "\n"
        f'            <ol class="ach-list"{ol_attrs}>\n'
        + "\n".join(item_blocks) + "\n"
        "            </ol>\n"
        "        </div>"
    )
    return block, start_idx + n


def render_publications_html(data):
    # `_llms_only` groups (e.g. Preprints, Workshops) appear in llms-full.txt
    # for AI readers but are intentionally hidden from the visual HTML.
    groups = [g for g in data["groups"] if not g.get("_llms_only")]
    out = []
    next_idx = 1
    for g in groups:
        block, next_idx = render_group_html(g, next_idx)
        out.append(block)
    return "\n\n\n".join(out)


# ───────────────────────── llms-full.txt generators ─────────────────────────

def render_authors_md(text):
    """llms-full.txt keeps **…** as markdown bold — no transformation needed
    except trimming author list for cleanliness. We just pass through."""
    return text or ""


def _llms_item_line(it, idx=None, group_key=None):
    """Format a single item as a bullet or numbered-list line."""
    full_title = it["title"]
    if it.get("title_jp"):
        full_title = f"{full_title} ({it['title_jp']})"
    prefix = f"{idx}. " if idx else "- "
    parts = [f"{prefix}**{full_title}**"]
    if it.get("authors"):
        parts.append(render_authors_md(it["authors"]))

    venue_year = ""
    if it.get("venue") and it.get("year"):
        venue_year = f"{it['venue']}, {it['year']}"
    elif it.get("venue") or it.get("year"):
        venue_year = f"{it.get('venue', '')}{it.get('year', '')}"

    # Type suffix: English venues → English type; Japanese venues → Japanese type.
    # Awards don't need a type suffix (the group name already conveys it).
    show_type = group_key not in ("awards", "preprints")
    if show_type:
        if group_key in ("international",) and it.get("type_en"):
            venue_year = f"{venue_year} ({it['type_en']})"
        elif it.get("type_jp"):
            venue_year = f"{venue_year} ({it['type_jp']})"
        elif it.get("type_en"):
            venue_year = f"{venue_year} ({it['type_en']})"
    if venue_year:
        parts.append(venue_year)

    if it.get("links"):
        for l in it["links"]:
            # For arXiv-style single-link preprints, drop the redundant "arXiv:" prefix
            if group_key == "preprints" and l.get("text", "").lower() in ("arxiv", "preprint"):
                parts.append(l["url"])
            else:
                parts.append(f"{l['text']}: {l['url']}")
    return " — ".join(x for x in parts if x)


def render_llms_block(data):
    """Build the publications section for llms-full.txt (markdown).
    Includes every group in publications.json (including _llms_only ones
    like Preprints and Workshops)."""
    out = []
    headings = {
        "international": "### International conferences (peer-reviewed) / 国際学会",
        "preprints":     "### Preprints / プレプリント",
        "domestic":      "### Domestic conferences (Japan) / 国内学会",
        "workshops":     "### Domestic workshops / 国内ワークショップ",
        "awards":        "### Awards / 受賞",
        "other":         "### Other activities / その他",
    }
    numbered_keys = {"international", "domestic", "awards"}

    for g in data["groups"]:
        key = g.get("key")
        heading = headings.get(key, f"### {g.get('title_en', key)}")
        items = g.get("items", [])
        if not items:
            continue
        out.append(heading)
        out.append("")
        if key in numbered_keys:
            for i, it in enumerate(items, 1):
                out.append(_llms_item_line(it, idx=i, group_key=key))
        else:
            for it in items:
                out.append(_llms_item_line(it, group_key=key))
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ───────────────────────────── marker replacement ────────────────────────────

def replace_marked(path, new_body, comment=("<!--", "-->")):
    text = read_text(path)
    begin = " ".join(x for x in (comment[0], MARK_BEGIN, comment[1]) if x)
    end = " ".join(x for x in (comment[0], MARK_END, comment[1]) if x)
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        print(f"WARN: markers not found in {path} — skipped")
        return False
    write_text(path, pattern.sub(begin + "\n" + new_body + "\n" + end, text))
    return True


def main():
    data = json.loads(read_text(SRC_PATH))
    html_body = render_publications_html(data)
    llms_body = render_llms_block(data)

    ok1 = replace_marked(INDEX_PATH, html_body)
    ok2 = replace_marked(LLMS_PATH, llms_body)

    total = sum(len(g["items"]) for g in data["groups"])
    print(f"OK: {len(data['groups'])} groups, {total} items")
    if not ok1:
        print(f"WARN: {INDEX_PATH} not updated (markers missing)")
        sys.exit(1)
    if not ok2:
        print(f"WARN: {LLMS_PATH} not updated (markers missing)")


if __name__ == "__main__":
    main()

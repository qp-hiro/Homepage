# -*- coding: utf-8 -*-
"""
build_cv.py — Generate CV from profile.json + publications.json.

Outputs:
  cv.md    Markdown version (compact; good for GitHub preview / recruiter sharing)
  cv.html  Styled HTML for in-browser viewing or "Save as PDF"
  cv.pdf   PDF generated from cv.html via WeasyPrint (if available)

If WeasyPrint isn't installed (e.g. running locally without it), the PDF step
is skipped — the HTML can still be printed from a browser.

Usage:
  python tools/build_cv.py
"""
import datetime
import io
import json
import os
import re
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(REPO_DIR, "profile.json")
PUBLICATIONS_PATH = os.path.join(REPO_DIR, "publications.json")
CV_MD_PATH = os.path.join(REPO_DIR, "cv.md")
CV_HTML_PATH = os.path.join(REPO_DIR, "cv.html")
CV_PDF_PATH = os.path.join(REPO_DIR, "cv.pdf")


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_json(path):
    return json.loads(read_text(path))


def strip_self_md(text):
    """Keep **self** markers as markdown bold — identity transform."""
    return text or ""


def strip_self_html(text):
    """Convert **X** → <strong class="self">X</strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r'<strong class="self">\1</strong>',
                  (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ─────────────────────────────── Markdown ────────────────────────────────────

def render_markdown(profile, pubs):
    name_en = profile["name"]["en"]
    name_jp = profile["name"].get("jp", "")
    title_en = profile.get("title_en", "")
    aff_en = profile["affiliation"]["en"]
    aff_jp = profile["affiliation"].get("jp", "")
    emails = profile.get("email", [])
    homepage = profile.get("homepage", "")

    out = []
    out.append(f"# {name_en}" + (f" ({name_jp})" if name_jp else ""))
    out.append("")
    out.append(f"**{title_en}**")
    out.append("")
    out.append(f"{aff_en}" + (f" / {aff_jp}" if aff_jp else ""))
    out.append("")
    out.append(" · ".join(filter(None, [
        " / ".join(f"[{e}](mailto:{e})" for e in emails),
        f"[{homepage}]({homepage})" if homepage else "",
    ])))
    out.append("")
    out.append(f"*Last updated: {datetime.date.today().isoformat()}*")
    out.append("")

    # Research interests
    ri = profile.get("research_interests", {})
    if ri.get("en"):
        out.append("## Research Interests")
        out.append("")
        out.append(ri["en"])
        if ri.get("jp"):
            out.append("")
            out.append(ri["jp"])
        out.append("")

    # Education
    edus = profile.get("education", [])
    if edus:
        out.append("## Education")
        out.append("")
        for e in edus:
            line = f"- **{e['period']}** — {e['degree_en']}"
            if e.get("institution_en"):
                line += f", {e['institution_en']}"
            if e.get("degree_jp"):
                line += f"  \n  *{e['degree_jp']}*"
            out.append(line)
        out.append("")

    # Fellowships
    fells = profile.get("fellowships", [])
    if fells:
        out.append("## Fellowships")
        out.append("")
        for f in fells:
            line = f"- **{f['period']}** — {f['name_en']}"
            if f.get("institution_en"):
                line += f", {f['institution_en']}"
            if f.get("name_jp"):
                line += f"  \n  *{f['name_jp']}*"
            out.append(line)
        out.append("")

    # Publications (from publications.json)
    groups = pubs.get("groups", [])

    def group_items(key):
        for g in groups:
            if g.get("key") == key:
                return g.get("items", [])
        return []

    def pub_line(it, numbered=None):
        title = it["title"]
        if it.get("title_jp"):
            title += f" ({it['title_jp']})"
        prefix = f"{numbered}. " if numbered else "- "
        parts = [f"{prefix}**{title}**"]
        if it.get("authors"):
            parts.append(strip_self_md(it["authors"]))
        venue_year = ""
        if it.get("venue") and it.get("year"):
            venue_year = f"{it['venue']}, {it['year']}"
        elif it.get("venue") or it.get("year"):
            venue_year = f"{it.get('venue', '')}{it.get('year', '')}"
        if it.get("type_en"):
            venue_year = f"{venue_year} ({it['type_en']})"
        if venue_year:
            parts.append(venue_year)
        if it.get("links"):
            for l in it["links"]:
                parts.append(f"[{l['text']}]({l['url']})")
        return " — ".join(x for x in parts if x)

    sections = [
        ("international", "International Conferences (peer-reviewed)", True),
        ("preprints", "Preprints", False),
        ("domestic", "Domestic Conferences", True),
        ("workshops", "Domestic Workshops", False),
        ("awards", "Awards", True),
        ("other", "Other Activities", False),
    ]
    out.append("## Publications & Achievements")
    out.append("")
    for key, heading, numbered in sections:
        items = group_items(key)
        if not items:
            continue
        out.append(f"### {heading}")
        out.append("")
        if numbered:
            for i, it in enumerate(items, 1):
                out.append(pub_line(it, numbered=i))
        else:
            for it in items:
                out.append(pub_line(it))
        out.append("")

    # Technical Skills
    sk = profile.get("skills", {})
    if sk:
        out.append("## Technical Skills")
        out.append("")
        for tier, label in [("advanced", "Advanced"), ("intermediate", "Intermediate"), ("beginner", "Beginner")]:
            items = sk.get(tier, [])
            if items:
                out.append(f"- **{label}**: {', '.join(items)}")
        out.append("")

    # Languages
    langs = profile.get("languages", [])
    if langs:
        out.append("## Languages")
        out.append("")
        for l in langs:
            out.append(f"- {l['name']}: {l['level']}")
        out.append("")

    # Links
    links = profile.get("links", [])
    if links:
        out.append("## Online")
        out.append("")
        for l in links:
            out.append(f"- [{l['name']}]({l['url']})")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ───────────────────────────────── HTML ──────────────────────────────────────

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
    font-family: "Segoe UI", "Meiryo UI", "Hiragino Sans", "Yu Gothic UI", "Noto Sans CJK JP", system-ui, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1c1a17;
    background: #ffffff;
}
.wrap { max-width: 840px; margin: 0 auto; padding: 24px 0; }
h1 {
    font-weight: 300;
    font-size: 32pt;
    letter-spacing: -0.01em;
    line-height: 1.05;
    margin: 0 0 2px;
}
.name-jp { font-size: 13pt; color: #4a463f; margin-left: 10px; font-weight: 400; }
.title { font-size: 11.5pt; color: #4a463f; margin: 0 0 6px; }
.contact {
    font-size: 10pt; color: #4a463f;
    margin: 2px 0 4px;
}
.contact a { color: inherit; text-decoration: none; border-bottom: 1px solid #c7c3b8; }
.meta {
    font-size: 8.5pt; letter-spacing: 0.14em; text-transform: uppercase;
    color: #7a7468;
    margin: 10px 0 24px;
}
.hr {
    height: 1px;
    background: linear-gradient(to right, #1c1a17 0, #1c1a17 70%, transparent 100%);
    margin: 0 0 24px;
}
h2 {
    font-size: 11pt;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 600;
    color: #1c1a17;
    margin: 20px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #d4d0c6;
    page-break-after: avoid;
}
h3 {
    font-size: 10pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
    color: #4a463f;
    margin: 14px 0 6px;
    page-break-after: avoid;
}
p { margin: 0 0 8px; }
p.ri-jp { color: #4a463f; margin-top: 4px; }
ul, ol { margin: 0 0 10px 0; padding-left: 20px; }
li { margin-bottom: 6px; page-break-inside: avoid; }
li .period { display: inline-block; font-variant-numeric: tabular-nums; color: #4a463f; margin-right: 8px; font-weight: 500; }
li .jp-sub { display: block; color: #4a463f; font-size: 9.5pt; margin-top: 2px; }
li .venue { color: #4a463f; }
.pub-title { font-weight: 600; }
.pub-type { color: #7a7468; }
.strong-self, strong.self { font-weight: 700; color: #1c1a17; }
.skills-row {
    display: flex;
    gap: 16px;
    margin-bottom: 6px;
}
.skills-row .tier-label {
    flex: 0 0 110px;
    font-size: 9.5pt;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #7a7468;
}
.skills-row .tier-items { flex: 1; }
.chip {
    display: inline-block;
    padding: 1px 8px;
    margin: 2px 3px 2px 0;
    border: 1px solid #d4d0c6;
    border-radius: 999px;
    font-size: 9.5pt;
}
.langs-row { display: flex; flex-wrap: wrap; gap: 14px 24px; }
.langs-row .lang { font-size: 10pt; }
.links-row a {
    display: inline-block;
    margin-right: 14px;
    color: #1c1a17;
    text-decoration: none;
    border-bottom: 1px solid #c7c3b8;
    font-size: 10pt;
}
.footer { margin-top: 28px; color: #7a7468; font-size: 8.5pt; }
"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(profile, pubs):
    name_en = esc(profile["name"]["en"])
    name_jp = esc(profile["name"].get("jp", ""))
    title_en = esc(profile.get("title_en", ""))
    aff_en = esc(profile["affiliation"]["en"])
    aff_jp = esc(profile["affiliation"].get("jp", ""))
    homepage = esc(profile.get("homepage", ""))
    emails = profile.get("email", [])

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="UTF-8">')
    parts.append(f"<title>Curriculum Vitae — {name_en}</title>")
    parts.append("<style>" + CSS + "</style>")
    parts.append("</head><body><div class='wrap'>")

    # Header
    parts.append(f"<h1>{name_en}<span class='name-jp'>{name_jp}</span></h1>")
    if title_en:
        parts.append(f"<p class='title'>{title_en}</p>")
    parts.append(f"<p class='contact'>{aff_en}{(' / ' + aff_jp) if aff_jp else ''}</p>")
    contact_bits = []
    for e in emails:
        contact_bits.append(f"<a href='mailto:{esc(e)}'>{esc(e)}</a>")
    if homepage:
        contact_bits.append(f"<a href='{homepage}'>{homepage}</a>")
    parts.append("<p class='contact'>" + " · ".join(contact_bits) + "</p>")
    parts.append(f"<p class='meta'>Curriculum Vitae · Last updated {datetime.date.today().isoformat()}</p>")
    parts.append("<div class='hr'></div>")

    # Research interests
    ri = profile.get("research_interests", {})
    if ri.get("en"):
        parts.append("<h2>Research Interests</h2>")
        parts.append(f"<p>{esc(ri['en'])}</p>")
        if ri.get("jp"):
            parts.append(f"<p class='ri-jp'>{esc(ri['jp'])}</p>")

    # Education
    edus = profile.get("education", [])
    if edus:
        parts.append("<h2>Education</h2>")
        parts.append("<ul>")
        for e in edus:
            inst = f", {esc(e['institution_en'])}" if e.get("institution_en") else ""
            jp = f"<span class='jp-sub'>{esc(e['degree_jp'])}</span>" if e.get("degree_jp") else ""
            parts.append(
                f"<li><span class='period'>{esc(e['period'])}</span>"
                f"<strong>{esc(e['degree_en'])}</strong>{inst}{jp}</li>"
            )
        parts.append("</ul>")

    # Fellowships
    fells = profile.get("fellowships", [])
    if fells:
        parts.append("<h2>Fellowships</h2>")
        parts.append("<ul>")
        for f in fells:
            inst = f", {esc(f['institution_en'])}" if f.get("institution_en") else ""
            jp = f"<span class='jp-sub'>{esc(f['name_jp'])}</span>" if f.get("name_jp") else ""
            parts.append(
                f"<li><span class='period'>{esc(f['period'])}</span>"
                f"<strong>{esc(f['name_en'])}</strong>{inst}{jp}</li>"
            )
        parts.append("</ul>")

    # Publications
    groups = pubs.get("groups", [])

    def group_items(key):
        for g in groups:
            if g.get("key") == key:
                return g.get("items", [])
        return []

    def pub_html(it):
        title = esc(it["title"])
        if it.get("title_jp"):
            title += f" <span class='jp-sub' style='display:inline;'>({esc(it['title_jp'])})</span>"
        bits = [f"<span class='pub-title'>{title}</span>"]
        if it.get("authors"):
            bits.append(f" — {strip_self_html(it['authors'])}")
        venue_year = ""
        if it.get("venue") and it.get("year"):
            venue_year = f"{esc(it['venue'])}, {esc(str(it['year']))}"
        elif it.get("venue") or it.get("year"):
            venue_year = esc(it.get("venue", "") or str(it.get("year", "")))
        if it.get("type_en"):
            venue_year += f" <span class='pub-type'>({esc(it['type_en'])})</span>"
        if venue_year:
            bits.append(f" — <span class='venue'>{venue_year}</span>")
        if it.get("links"):
            for l in it["links"]:
                bits.append(f" — <a href='{esc(l['url'])}'>{esc(l['text'])}</a>")
        return "<li>" + "".join(bits) + "</li>"

    sections = [
        ("international", "International Conferences (peer-reviewed)", True),
        ("preprints", "Preprints", False),
        ("domestic", "Domestic Conferences", True),
        ("workshops", "Domestic Workshops", False),
        ("awards", "Awards", True),
        ("other", "Other Activities", False),
    ]
    parts.append("<h2>Publications &amp; Achievements</h2>")
    for key, heading, numbered in sections:
        items = group_items(key)
        if not items:
            continue
        parts.append(f"<h3>{heading}</h3>")
        tag = "ol" if numbered else "ul"
        parts.append(f"<{tag}>")
        for it in items:
            parts.append(pub_html(it))
        parts.append(f"</{tag}>")

    # Skills
    sk = profile.get("skills", {})
    if sk:
        parts.append("<h2>Technical Skills</h2>")
        for tier, label in [("advanced", "Advanced"), ("intermediate", "Intermediate"), ("beginner", "Beginner")]:
            items = sk.get(tier, [])
            if items:
                chips = "".join(f"<span class='chip'>{esc(x)}</span>" for x in items)
                parts.append(
                    f"<div class='skills-row'><div class='tier-label'>{label}</div>"
                    f"<div class='tier-items'>{chips}</div></div>"
                )

    # Languages
    langs = profile.get("languages", [])
    if langs:
        parts.append("<h2>Languages</h2>")
        row = "".join(
            f"<span class='lang'><strong>{esc(l['name'])}</strong> — {esc(l['level'])}</span>"
            for l in langs
        )
        parts.append(f"<div class='langs-row'>{row}</div>")

    # Links
    links = profile.get("links", [])
    if links:
        parts.append("<h2>Online</h2>")
        row = "".join(
            f"<a href='{esc(l['url'])}'>{esc(l['name'])}</a>"
            for l in links
        )
        parts.append(f"<p class='links-row'>{row}</p>")

    parts.append(
        "<p class='footer'>Generated automatically from "
        "<code>profile.json</code> + <code>publications.json</code> via "
        "<code>tools/build_cv.py</code>.</p>"
    )
    parts.append("</div></body></html>")
    return "\n".join(parts)


# ─────────────────────────────── Entry point ─────────────────────────────────

def main():
    profile = read_json(PROFILE_PATH)
    pubs = read_json(PUBLICATIONS_PATH)

    md = render_markdown(profile, pubs)
    html = render_html(profile, pubs)

    write_text(CV_MD_PATH, md)
    write_text(CV_HTML_PATH, html)
    print(f"wrote {os.path.relpath(CV_MD_PATH, REPO_DIR)}")
    print(f"wrote {os.path.relpath(CV_HTML_PATH, REPO_DIR)}")

    # Try PDF via WeasyPrint (optional dependency)
    try:
        from weasyprint import HTML as WeasyHTML  # type: ignore
    except Exception:
        print("WeasyPrint not available — skipping PDF (install with `pip install weasyprint`)")
        return
    try:
        WeasyHTML(string=html, base_url=REPO_DIR).write_pdf(CV_PDF_PATH)
        print(f"wrote {os.path.relpath(CV_PDF_PATH, REPO_DIR)}")
    except Exception as e:
        print(f"WARN: PDF generation failed: {e}")


if __name__ == "__main__":
    main()

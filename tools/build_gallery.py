# -*- coding: utf-8 -*-
"""
build_gallery.py — Build the Gallery section from the Google Drive source.

Source of truth:
  /Users/.../マイドライブ/Homepage/Gallery/<Category>/*.jpg|png|webp

Outputs (owned by this script — do not edit by hand):
  Gallery/<Category>/*.jpg          optimized web images (resized, re-encoded)
  Gallery/gallery.json              manifest (debug / inspection)
  gallery.html                      <!-- GALLERY:AUTO:BEGIN --> ... <!-- GALLERY:AUTO:END -->
                                    inlined so the page works via file:// too

Each sub-folder of the source Gallery/ becomes one category. Image files in
the folder become its photos, sorted by filename.

Japanese labels and display-name overrides live in tools/gallery-overrides.json:

    {
      "Animal":   { "name_jp": "動物" },
      "Portrait": { "name_jp": "肖像", "name": "Portraits" }
    }

Common category names have a default Japanese label (see DEFAULT_JP).

Usage:
  python tools/build_gallery.py
"""
import hashlib
import io
import json
import os
import re
import sys

from PIL import Image

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Drive source — the folder the user curates by hand.
# Env var takes precedence so GitHub Actions can point this at a temp dir
# populated by drive_sync.py.
DRIVE_DIR = os.environ.get(
    "GALLERY_DRIVE_DIR",
    "/Users/qphirosuke/Library/CloudStorage/GoogleDrive-hirosuke.asahi@star.rcast.u-tokyo.ac.jp/マイドライブ/Homepage/Gallery",
)
LOCAL_DIR = os.path.join(REPO_DIR, "Gallery")
MANIFEST_PATH = os.path.join(LOCAL_DIR, "gallery.json")
HTML_PATH = os.path.join(REPO_DIR, "gallery.html")
OVERRIDES_PATH = os.path.join(REPO_DIR, "tools", "gallery-overrides.json")
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gallery_cache.json")

MAX_IMG_WIDTH = 1800
JPEG_QUALITY = 87

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

MARK_BEGIN = "GALLERY:AUTO:BEGIN"
MARK_END = "GALLERY:AUTO:END"

# Default Japanese labels for common category names.
# Display order for categories (anything not listed falls through to
# alphabetical order at the end). Case-insensitive match on folder name.
# Both singular and plural variants are listed so renaming the Drive folder
# does not require code changes.
CATEGORY_ORDER = [
    "Life",
    "Portrait", "Portraits",
    "Scenery",
    "Animal", "Animals",
    "Travel", "Travels",
]

DEFAULT_JP = {
    "Animal":       "動物",
    "Animals":      "動物",
    "Portrait":     "肖像",
    "Portraits":    "肖像",
    "Scenery":      "風景",
    "Landscape":    "風景",
    "Landscapes":   "風景",
    "Life":         "暮らし",
    "Street":       "ストリート",
    "Travel":       "旅",
    "Travels":      "旅",
    "Nature":       "自然",
    "Architecture": "建築",
    "Still Life":   "静物",
    "Night":        "夜景",
    "Macro":        "マクロ",
    "Flower":       "花",
    "Flowers":      "花",
    "City":         "都市",
    "Sea":          "海",
    "Mountain":     "山",
    "Mountains":    "山",
}


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_json(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


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


def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            return read_json(CACHE_PATH)
        except Exception:
            pass
    return {}


def trim_white_border(im, threshold=245, min_crop_px=4):
    """Crop near-white uniform borders if the image has them.
    Only crops if at least `min_crop_px` would be removed from any side,
    so photos that happen to be bright-edged aren't aggressively cut.
    `threshold` (0–255): any pixel with luminance >= threshold counts as
    'white border'. Lower → more aggressive, higher → safer."""
    gray = im.convert("L")
    # Pixels below threshold are content (white, 255); white border → 0
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return im  # pure-white image → leave alone
    x0, y0, x1, y1 = bbox
    w, h = im.size
    # Must crop a meaningful amount, otherwise leave as-is
    if (x0 < min_crop_px and y0 < min_crop_px
            and (w - x1) < min_crop_px and (h - y1) < min_crop_px):
        return im
    return im.crop(bbox)


def build_image(src, out_dir, slug, cache):
    """Convert one source image into an optimized web JPEG.
    Returns (out_name, width, height) or None on failure."""
    key = src
    digest = sha1_of(src)
    cached = cache.get(key)
    if cached and cached.get("sha1") == digest and os.path.exists(os.path.join(out_dir, cached.get("out", ""))):
        return cached["out"], cached.get("w", 0), cached.get("h", 0)
    try:
        im = Image.open(src)
        # Honour EXIF rotation (portrait phones often need this)
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        # Trim white film-style borders if present
        im = trim_white_border(im)
        # Clamp the LONG edge so portraits aren't shrunk disproportionately
        long_edge = max(im.width, im.height)
        if long_edge > MAX_IMG_WIDTH:
            scale = MAX_IMG_WIDTH / long_edge
            new_w = round(im.width * scale)
            new_h = round(im.height * scale)
            im = im.resize((new_w, new_h), Image.LANCZOS)
        w, h = im.width, im.height
        out_name = slug + ".jpg"
        im.convert("RGB").save(os.path.join(out_dir, out_name),
                               format="JPEG", quality=JPEG_QUALITY, optimize=True)
    except Exception as e:
        print("WARN: image conversion failed for %s: %s" % (src, e))
        return None
    cache[key] = {"sha1": digest, "out": out_name, "w": w, "h": h}
    return out_name, w, h


def collect_categories(cache):
    overrides = read_json(OVERRIDES_PATH) if os.path.exists(OVERRIDES_PATH) else {}
    categories = []

    if not os.path.isdir(DRIVE_DIR):
        print("ERROR: Drive source not found: " + DRIVE_DIR)
        sys.exit(1)

    for name in sorted(os.listdir(DRIVE_DIR)):
        if name.startswith("."):
            continue
        src_folder = os.path.join(DRIVE_DIR, name)
        if not os.path.isdir(src_folder):
            continue

        srcs = sorted(
            os.path.join(src_folder, fn)
            for fn in os.listdir(src_folder)
            if not fn.startswith(".") and os.path.splitext(fn)[1].lower() in IMG_EXTS
        )
        if not srcs:
            continue

        out_folder = os.path.join(LOCAL_DIR, name)
        os.makedirs(out_folder, exist_ok=True)

        produced = []
        for src in srcs:
            result = build_image(src, out_folder, slugify(os.path.basename(src)), cache)
            if result:
                out_name, w, h = result
                produced.append({"file": out_name, "w": w, "h": h})

        # Prune stale outputs
        existing = {fn for fn in os.listdir(out_folder) if not fn.startswith(".")}
        kept = {p["file"] for p in produced}
        for stale in existing - kept:
            try:
                os.remove(os.path.join(out_folder, stale))
            except OSError:
                pass

        if not produced:
            continue

        ov = overrides.get(name, {})
        categories.append({
            "slug": name,
            "name": ov.get("name", name),
            "name_jp": ov.get("name_jp", DEFAULT_JP.get(name, "")),
            "photos": produced,
        })

    # Apply the display order: anything in CATEGORY_ORDER comes first in that
    # order, anything else keeps its alphabetical position at the tail.
    order_map = {slug.lower(): i for i, slug in enumerate(CATEGORY_ORDER)}
    def sort_key(c):
        return order_map.get(c["slug"].lower(), len(order_map) + ord(c["slug"][0]))
    categories.sort(key=sort_key)
    return categories


def inline_into_html(html_path, data):
    """Replace the GALLERY:AUTO block in gallery.html with an inline JS
    assignment, so no fetch is needed to render the page."""
    text = read_text(html_path)
    begin = "<!-- " + MARK_BEGIN + " -->"
    end = "<!-- " + MARK_END + " -->"
    body = (
        "    <script id=\"gallery-data\">\n"
        "    /* Generated by tools/build_gallery.py — do not edit by hand. */\n"
        "    window.GALLERY_DATA = " + json.dumps(data, ensure_ascii=False, indent=4) + ";\n"
        "    </script>"
    )
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        print("WARN: markers not found in %s — skipped inlining" % html_path)
        return False
    write_text(html_path, pattern.sub(begin + "\n" + body + "\n    " + end, text))
    return True


def main():
    cache = load_cache()
    os.makedirs(LOCAL_DIR, exist_ok=True)

    categories = collect_categories(cache)
    data = {"categories": categories}

    write_json(MANIFEST_PATH, data)
    inline_into_html(HTML_PATH, data)
    write_json(CACHE_PATH, cache)

    total = sum(len(c["photos"]) for c in categories)
    print("OK: %d categories, %d photos" % (len(categories), total))
    for c in categories:
        print("  - %s (%s): %d" % (c["slug"], c["name_jp"] or "—", len(c["photos"])))


if __name__ == "__main__":
    main()

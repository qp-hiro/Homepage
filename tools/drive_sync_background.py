# -*- coding: utf-8 -*-
"""
drive_sync_background.py — Download hero background images from Google Drive.

Mirrors the Drive source `Background/*.{jpg,png,…}` into `Hero/` in the repo,
then build_hero.py regenerates index.html from the resulting file list.

Env vars:
  GOOGLE_APPLICATION_CREDENTIALS   Service-account JSON path.
  BACKGROUND_FOLDER_ID             Drive folder ID of the Background folder.
  HERO_DIR                         Local destination (default: ./Hero).

Usage:
  python tools/drive_sync_background.py
"""
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.environ.get("HERO_DIR", os.path.join(REPO_DIR, "Hero"))

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def must(name):
    val = os.environ.get(name, "")
    if not val:
        print(f"ERROR: environment variable {name} is required")
        sys.exit(1)
    return val


def list_files(service, parent_id):
    results, page_token = [], None
    while True:
        resp = service.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def download(service, fm, dest_path):
    tmp = dest_path + ".part"
    req = service.files().get_media(fileId=fm["id"])
    with open(tmp, "wb") as f:
        downloader = MediaIoBaseDownload(f, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    os.replace(tmp, dest_path)


def main():
    key_path = must("GOOGLE_APPLICATION_CREDENTIALS")
    folder_id = must("BACKGROUND_FOLDER_ID")
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    os.makedirs(TARGET_DIR, exist_ok=True)

    files = [
        f for f in list_files(service, folder_id)
        if os.path.splitext(f.get("name", ""))[1].lower() in IMG_EXTS
    ]
    drive_names = set()

    for fm in files:
        name = fm["name"]
        drive_names.add(name)
        dest = os.path.join(TARGET_DIR, name)
        if os.path.exists(dest) and str(os.path.getsize(dest)) == (fm.get("size") or ""):
            continue
        download(service, fm, dest)
        print(f"downloaded: {name}")

    # Prune local files that no longer exist in Drive
    for local in list(os.listdir(TARGET_DIR)):
        if local.startswith("."):
            continue
        ext = os.path.splitext(local)[1].lower()
        if ext in IMG_EXTS and local not in drive_names:
            try:
                os.remove(os.path.join(TARGET_DIR, local))
                print(f"removed stale: {local}")
            except OSError:
                pass

    print(f"OK: {len(files)} images synced to {TARGET_DIR}")


if __name__ == "__main__":
    main()

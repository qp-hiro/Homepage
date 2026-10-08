# -*- coding: utf-8 -*-
"""
drive_sync_works.py — Download the Works source tree from Google Drive.

Used by the GitHub Actions "Works sync" workflow so build_works.py can run
without a local Drive mount. The expected Drive layout mirrors the local
Windows path:

  <ROOT>/
    work1/
      paper.pdf
      *.jpg | *.jpeg | *.png | *.webp | *.pdf  (figures)
    work2/
      ...

Unlike drive_sync.py (which only pulls images for the Gallery), this one
pulls PDFs too since build_works.py parses them for the title, abstract,
and year.

Env vars:
  GOOGLE_APPLICATION_CREDENTIALS  Path to the service-account JSON key.
  WORKS_FOLDER_ID                 ID of the Drive Files_for_works folder.
  WORKS_DRIVE_DIR                 Where to download to (default: /tmp/works-src).

Usage:
  python tools/drive_sync_works.py
"""
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TARGET_DIR = os.environ.get("WORKS_DRIVE_DIR", "/tmp/works-src")

# Which file types to download. build_works.py expects PDFs (papers / figure
# PDFs) alongside raster images.
WANTED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def must(name):
    val = os.environ.get(name, "")
    if not val:
        print(f"ERROR: environment variable {name} is required")
        sys.exit(1)
    return val


def list_children(service, parent_id, folders_only=False):
    """Return all children of parent_id (handles paging)."""
    results = []
    page_token = None
    while True:
        q = [f"'{parent_id}' in parents", "trashed=false"]
        if folders_only:
            q.append("mimeType='application/vnd.google-apps.folder'")
        resp = service.files().list(
            q=" and ".join(q),
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
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


def download_file(service, file_meta, dest_path):
    tmp = dest_path + ".part"
    request = service.files().get_media(fileId=file_meta["id"])
    with open(tmp, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    os.replace(tmp, dest_path)


def wanted(file_meta):
    name = file_meta.get("name", "")
    ext = os.path.splitext(name)[1].lower()
    return ext in WANTED_EXTS


def main():
    key_path = must("GOOGLE_APPLICATION_CREDENTIALS")
    folder_id = must("WORKS_FOLDER_ID")
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    os.makedirs(TARGET_DIR, exist_ok=True)

    work_folders = list_children(service, folder_id, folders_only=True)
    print(f"found {len(work_folders)} work folders in Drive root")

    total_dl = 0
    for wf in sorted(work_folders, key=lambda c: c["name"]):
        wf_name = wf["name"]
        wf_dir = os.path.join(TARGET_DIR, wf_name)
        os.makedirs(wf_dir, exist_ok=True)

        files = [f for f in list_children(service, wf["id"]) if wanted(f)]
        for fm in files:
            dest = os.path.join(wf_dir, fm["name"])
            # Skip byte-identical copies (size match is good-enough)
            if os.path.exists(dest) and str(os.path.getsize(dest)) == (fm.get("size") or ""):
                continue
            download_file(service, fm, dest)
            total_dl += 1
            print(f"downloaded: {wf_name}/{fm['name']}")

    print(f"OK: {total_dl} files downloaded into {TARGET_DIR}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
drive_sync_publications.py — Download publication PDFs from Google Drive.

Mirrors the Drive source `Files_for_publications/<title>/<paper>.pdf`
structure into `publications_pdfs/<title>/<paper>.pdf` in the repo.

Env vars:
  GOOGLE_APPLICATION_CREDENTIALS         Service-account JSON path.
  PUBLICATIONS_FILES_FOLDER_ID           Drive folder ID of Files_for_publications.
  PUBLICATIONS_PDFS_DIR                  Local destination (default: ./publications_pdfs).

Usage:
  python tools/drive_sync_publications.py
"""
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.environ.get(
    "PUBLICATIONS_PDFS_DIR",
    os.path.join(REPO_DIR, "publications_pdfs"),
)

WANTED_EXTS = {".pdf"}


def must(name):
    val = os.environ.get(name, "")
    if not val:
        print(f"ERROR: environment variable {name} is required")
        sys.exit(1)
    return val


def list_children(service, parent_id, folders_only=False):
    results, page_token = [], None
    while True:
        q = [f"'{parent_id}' in parents", "trashed=false"]
        if folders_only:
            q.append("mimeType='application/vnd.google-apps.folder'")
        resp = service.files().list(
            q=" and ".join(q),
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


def download_file(service, fm, dest_path):
    tmp = dest_path + ".part"
    request = service.files().get_media(fileId=fm["id"])
    with open(tmp, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    os.replace(tmp, dest_path)


def wanted(fm):
    ext = os.path.splitext(fm.get("name", ""))[1].lower()
    return ext in WANTED_EXTS


def main():
    key_path = must("GOOGLE_APPLICATION_CREDENTIALS")
    folder_id = must("PUBLICATIONS_FILES_FOLDER_ID")
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    os.makedirs(TARGET_DIR, exist_ok=True)

    title_folders = list_children(service, folder_id, folders_only=True)
    print(f"found {len(title_folders)} title folders in Drive root")

    total_dl = 0
    for tf in sorted(title_folders, key=lambda c: c["name"]):
        name = tf["name"]
        dst = os.path.join(TARGET_DIR, name)
        os.makedirs(dst, exist_ok=True)

        files = [f for f in list_children(service, tf["id"]) if wanted(f)]
        for fm in files:
            dest = os.path.join(dst, fm["name"])
            if os.path.exists(dest) and str(os.path.getsize(dest)) == (fm.get("size") or ""):
                continue
            download_file(service, fm, dest)
            total_dl += 1
            print(f"downloaded: {name}/{fm['name']}")

    print(f"OK: {total_dl} PDFs downloaded into {TARGET_DIR}")


if __name__ == "__main__":
    main()

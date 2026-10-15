# -*- coding: utf-8 -*-
"""
drive_sync.py — Download the Gallery source tree from Google Drive.

Used by the GitHub Actions workflow so the build can run without a local
Drive mount. The expected layout mirrors the local one:

  <ROOT>/
    <Category 1>/
      *.jpg | *.jpeg | *.png | *.webp
    <Category 2>/
      ...

Env vars:
  GOOGLE_APPLICATION_CREDENTIALS  Path to the service-account JSON key.
  DRIVE_FOLDER_ID                  ID of the Drive Gallery folder (the thing
                                   that would be `.../Homepage/Gallery/` on
                                   the user's Mac).
  GALLERY_DRIVE_DIR                Where to download to (default: /tmp/gallery-src).

The service account must have at least Viewer access to the Drive folder —
share the folder with the service account's email in Drive UI.

Usage:
  python tools/drive_sync.py
"""
import io
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TARGET_DIR = os.environ.get("GALLERY_DRIVE_DIR", "/tmp/gallery-src")
FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")

IMG_MIME_PREFIX = "image/"


def must(name):
    val = os.environ.get(name, "")
    if not val:
        print(f"ERROR: environment variable {name} is required")
        sys.exit(1)
    return val


def list_children(service, parent_id, mime_contains=None, folders_only=False):
    """Return all children of parent_id matching the filter (handles paging)."""
    results = []
    page_token = None
    while True:
        q = [f"'{parent_id}' in parents", "trashed=false"]
        if folders_only:
            q.append("mimeType='application/vnd.google-apps.folder'")
        elif mime_contains:
            q.append(f"mimeType contains '{mime_contains}'")
        resp = service.files().list(
            q=" and ".join(q),
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum, size)",
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
    """Stream a file from Drive to dest_path."""
    tmp = dest_path + ".part"
    request = service.files().get_media(fileId=file_meta["id"])
    with open(tmp, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    os.replace(tmp, dest_path)


def main():
    key_path = must("GOOGLE_APPLICATION_CREDENTIALS")
    folder_id = must("DRIVE_FOLDER_ID")
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    os.makedirs(TARGET_DIR, exist_ok=True)

    categories = list_children(service, folder_id, folders_only=True)
    print(f"found {len(categories)} categories in Drive root")

    total_dl = 0

    def sync_images_from(folder_meta, dest_dir, label):
        """Download every image directly in folder_meta into dest_dir."""
        nonlocal total_dl
        os.makedirs(dest_dir, exist_ok=True)
        images = [
            f for f in list_children(service, folder_meta["id"])
            if (f.get("mimeType") or "").startswith(IMG_MIME_PREFIX)
        ]
        for img in images:
            dest = os.path.join(dest_dir, img["name"])
            if os.path.exists(dest) and str(os.path.getsize(dest)) == (img.get("size") or ""):
                continue
            download_file(service, img, dest)
            total_dl += 1
            print(f"downloaded: {label}/{img['name']}")

    for cat in sorted(categories, key=lambda c: c["name"]):
        cat_name = cat["name"]
        cat_dir = os.path.join(TARGET_DIR, cat_name)
        # Direct images in the category folder
        sync_images_from(cat, cat_dir, cat_name)
        # One level of nested sub-folders (used as clusters: People/<Country>)
        sub_folders = list_children(service, cat["id"], folders_only=True)
        for sub in sub_folders:
            sub_dir = os.path.join(cat_dir, sub["name"])
            sync_images_from(sub, sub_dir, f"{cat_name}/{sub['name']}")

    print(f"OK: {total_dl} files downloaded into {TARGET_DIR}")


if __name__ == "__main__":
    main()

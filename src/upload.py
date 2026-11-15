"""YouTube upload with the free YouTube Data API v3 (OAuth refresh token per channel)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def client_for(prefix: str):
    token = os.environ.get(f"YT_{prefix}_REFRESH_TOKEN")
    cid, secret = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    if not (token and cid and secret):
        return None
    creds = Credentials(None, refresh_token=token, client_id=cid, client_secret=secret,
                        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(yt, video: Path, thumb: Path | None, title: str, description: str, tags: list[str],
           lang: str, privacy: str = "private", publish_at: str | None = None) -> str:
    body = {
        "snippet": {
            "title": title[:100], "description": description[:4900], "tags": tags[:15],
            "categoryId": "27",  # Education
            "defaultLanguage": lang, "defaultAudioLanguage": lang,
        },
        "status": {
            "privacyStatus": privacy,          # private | public (publish_at needs private)
            "selfDeclaredMadeForKids": True,   # REQUIRED for children's content (COPPA)
            "containsSyntheticMedia": True,    # disclose AI-generated voice/visuals
            "embeddable": True,
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at   # YouTube makes it public automatically at this time
    for attempt in range(5):
        try:
            req = yt.videos().insert(part="snippet,status", body=body,
                                     media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            vid = resp["id"]
            break
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 10)
                continue
            raise
    if thumb and thumb.exists():
        try:  # custom thumbnails need a phone-verified channel; ignore if not allowed yet
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except HttpError:
            pass
    return vid

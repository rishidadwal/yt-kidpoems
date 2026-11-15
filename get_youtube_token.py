"""Run ONCE on your own computer per YouTube channel. Saves the YouTube login straight into GitHub Secrets.

Nothing secret is printed or written to a file (house rule: secrets live only in GitHub Secrets).

1. Google Cloud Console -> project "kidpoems" -> Clients -> your "Desktop app" client: keep its ID and secret handy
2. In a normal terminal (needs gh logged in):   python get_youtube_token.py EN rishidadwal/yt-kidpoems
3. Paste the client ID and secret when asked (they are not shown), pick the channel in the browser.
   -> sets YT_CLIENT_ID, YT_CLIENT_SECRET and YT_<PREFIX>_REFRESH_TOKEN on the repo.
"""
from __future__ import annotations

import getpass
import subprocess
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def client_config(client_id: str, client_secret: str) -> dict:
    """The installed-app config Google's library expects (instead of a client_secret.json file)."""
    if not client_id.endswith(".apps.googleusercontent.com") or not client_secret:
        raise ValueError("client ID must end with .apps.googleusercontent.com and the secret must not be empty")
    return {"installed": {"client_id": client_id, "client_secret": client_secret,
                          "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                          "token_uri": "https://oauth2.googleapis.com/token",
                          "redirect_uris": ["http://localhost"]}}


def set_secret(repo: str, name: str, value: str) -> None:
    """`gh secret set` reads the value from stdin, so it never appears in a command line, log or file."""
    subprocess.run(["gh", "secret", "set", name, "-R", repo], input=value, text=True, check=True,
                   stdout=subprocess.DEVNULL, timeout=60)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python get_youtube_token.py <PREFIX e.g. EN> <owner/repo>")
        return 2
    prefix, repo = argv[1].upper(), argv[2]
    from google_auth_oauthlib.flow import InstalledAppFlow
    cid = input("OAuth client ID: ").strip()
    secret = getpass.getpass("OAuth client secret (hidden): ").strip()
    flow = InstalledAppFlow.from_client_config(client_config(cid, secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        print("Google returned no refresh token - remove the app at myaccount.google.com/permissions and retry.")
        return 1
    for name, value in (("YT_CLIENT_ID", cid), ("YT_CLIENT_SECRET", secret),
                        (f"YT_{prefix}_REFRESH_TOKEN", creds.refresh_token)):
        set_secret(repo, name, value)
        print(f"saved {name} on {repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

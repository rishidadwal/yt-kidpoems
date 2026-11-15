"""Run ONCE on your own computer per YouTube channel to get its refresh token.

1. Google Cloud Console -> new project -> enable "YouTube Data API v3"
2. OAuth consent screen: External, add yourself as a Test user
3. Credentials -> Create OAuth client ID -> "Desktop app" -> download JSON as client_secret.json (next to this file)
4. python get_youtube_token.py   -> browser opens -> pick the channel -> copy the printed values into GitHub Secrets
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nYT_CLIENT_ID      =", creds.client_id)
print("YT_CLIENT_SECRET  =", creds.client_secret)
print("YT_<PREFIX>_REFRESH_TOKEN =", creds.refresh_token)
print("\nSave these as GitHub Secrets (e.g. YT_EN_REFRESH_TOKEN for the English channel).")

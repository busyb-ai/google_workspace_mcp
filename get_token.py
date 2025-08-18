from requests_oauthlib import OAuth2Session
import webbrowser
import os
from dotenv import load_dotenv


load_dotenv('.env')

CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
# print("CLIENT_ID:", CLIENT_ID)
# print("CLIENT_SECRET:", CLIENT_SECRET)
REDIRECT_URI = os.environ["GOOGLE_OAUTH_REDIRECT_URI"]
SCOPE = "https://www.googleapis.com/auth/chat.messages https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/tasks https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar.events openid https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/forms.body https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/chat.messages.readonly https://www.googleapis.com/auth/chat.spaces https://www.googleapis.com/auth/forms.responses.readonly https://www.googleapis.com/auth/presentations.readonly https://www.googleapis.com/auth/tasks.readonly https://www.googleapis.com/auth/cse https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/forms.body.readonly https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/calendar"

AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

def get_authorization_code():
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
    authorization_url, _ = oauth.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline", prompt="consent")

    print("Please go to this URL and authorize access:")
    print(authorization_url)

    webbrowser.open(authorization_url)

    # After user authorizes, they get redirected to REDIRECT_URI with ?code= in URL
    # You need to capture that code manually or via a simple HTTP server (not shown here)
    auth_response = input("Paste the full redirect URL here: ")
    return auth_response

def fetch_token(auth_response):
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
    token = oauth.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=auth_response)
    return token

if __name__ == "__main__":
    auth_response = get_authorization_code()
    token = fetch_token(auth_response)
    print("Access token:", token["access_token"])
    print("Refresh token:", token.get("refresh_token"))

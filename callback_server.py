import os
import json
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from requests_oauthlib import OAuth2Session


load_dotenv('.env')

CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
REDIRECT_URI = os.environ["GOOGLE_OAUTH_REDIRECT_URI"]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        self.server.auth_code = params.get("code", [None])[0]

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization successful! You can close this window.")

def start_local_server():
    server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
    threading.Thread(target=server.serve_forever).start()
    return server

# Then later:
server = start_local_server()

# Open authorization URL in browser
# ...

# Wait until the server gets the auth code
while not hasattr(server, "auth_code"):
    pass

auth_code = server.auth_code

TOKEN_URL = "https://oauth2.googleapis.com/token"


def save_token(token, filename="token.json"):
    with open(filename, "w") as f:
        json.dump(token, f)


def fetch_access_token(auth_code):
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    token = oauth.fetch_token(
        TOKEN_URL,
        client_secret=CLIENT_SECRET,
        code=auth_code
    )
    return token

# Example usage:
token = fetch_access_token(auth_code)
token_file = os.environ['TOKEN_FILE']
save_token(token, filename=token_file)
print("Access token:", token["access_token"])
print("Refresh token:", token.get("refresh_token"))
server.shutdown()

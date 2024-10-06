
# This small flask app implements the Authorization Code OAuth flow to
# generate an access_token and refresh_token according to a specific
# scope of access within the Spotify API.

# flask --app generate_secrets run

# This will create the "secrets" file on disk

import base64
import json
import os
import uuid

from dotenv import load_dotenv
from flask import Flask, redirect, request
import requests

app = Flask(__name__)

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
NONCE = uuid.uuid4().hex + uuid.uuid1().hex
REDIRECT_URL = "http://localhost:5000/callback" # <-- MUST match the redirect URI listed on your Spotify app
SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public user-library-read user-library-modify user-read-private user-read-email "


def build_auth_url(client_id, scope, redirect_uri, state=None):
    url = "https://accounts.spotify.com/authorize?"
    url += "response_type=code"
    url += "&client_id=" + client_id
    url += "&scope=" + scope
    url += "&redirect_uri=" + redirect_uri
    url += (f"&state={state}" if state else "")
    return url


@app.route("/callback")
def call_back():
    """
    This will serve as our callback which spotify will redirect to once the user
    has authenticated. It will take in an authorization code from the redirect and use
    that to request an access token (and refresh token).
    """
    auth_code: str = request.args.get('code')
    state: str | None = request.args.get('state')

    if state != NONCE:
        raise Exception("State mismatch during authorization.")

    url = "https://accounts.spotify.com/api/token"

    resp = requests.post(
        url=url,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URL
        },
        headers={
            "Authorization": "Basic " + base64.b64encode(bytes(f"{CLIENT_ID}:{CLIENT_SECRET}", encoding='utf-8')).decode("utf-8"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    print(f"API token status code: {resp.status_code}")
    print(resp.content)
    resp = json.loads(resp.content)
    access_token = resp['access_token']
    refresh_token = resp['refresh_token']

    with open("secrets", "w") as f:
        json.dump({"access_token": access_token, "refresh_token": refresh_token}, f)

    return f"""
        <p>authorization code: {auth_code}</p>
        <p>state: {state}</p>
        <p>access_token: {access_token}</p>
        <p>refresh_token: {refresh_token}</p>
    """

@app.route("/")
def auth():
    """
    This is the initial route for kicking off the OAuth flow. It will redirect to Spotify for the
    user (me) to authorize this app to access the specific scopes I've selected.
    """

    url = build_auth_url(
        client_id=CLIENT_ID,
        scope=SCOPES,
        redirect_uri=REDIRECT_URL,
        state=NONCE
    )
    return redirect(location=url)


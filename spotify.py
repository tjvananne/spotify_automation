
import base64
from dataclasses import dataclass
import functools
import json
import os
import time
from typing import Dict, Callable

from dotenv import load_dotenv
import requests


load_dotenv()
SECRETS_PATH = './secrets'
MY_USER_ID = 'et1kvvnuze4mz6xjxyjeoqua3'



@dataclass
class ApiReq():
    kwargs: Dict
    method: Callable = requests.get


class Spotify():
    def __init__(self):
        self._load_tokens()
        self._last_request: ApiReq | None = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10
    
    @property
    def access_token(self):
        return os.environ['ACCESS_TOKEN']
    
    @property
    def refresh_token(self):
        return os.environ['REFRESH_TOKEN']

    @property
    def client_id(self):
        return os.environ['CLIENT_ID']

    @property
    def client_secret(self):
        return os.environ['CLIENT_SECRET']

    @property
    def auth_header(self):
        return {
            "Authorization": f"Bearer {self.access_token}"
        }

    def check_response(func):
        """
        Wraps any calls to the Spofity API so we can handle specific
        HTTP response codes.

        NOTE: Is this a bad idea doing this in a decorator that also
        calls the method that is being decorated? I'm calling
        self._retry_request() which ends up calling self.api_req().
        My concern is running into stack issues. Do I need a while
        loop in self.api_req() for retries instead of decorating
        that method?
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            result: requests.models.Response = func(self, *args, **kwargs)
            if result.status_code != 200:
                print(f"HTTP CODE {result.status_code}")
                self._consecutive_errors += 1
                if result.status_code == 401:
                    print("Refreshing access token...")
                    self._refresh_access_token()
                    result = self._retry_request(self._last_request)
                elif result.status_code == 429:
                    print("Backing off requests...")
                    self._backoff()
                    result = self._retry_request(self._last_request)
                # print("content: ", result.content)
                print("headers: ", result.headers)
                if self._consecutive_errors >= self._max_consecutive_errors:
                    raise Exception("Too many consecutive errors. Terminating program.")
            else:
                print("recording error")
                self._consecutive_errors = 0
            return result
        return wrapper

    @check_response
    def api_req(self, request: ApiReq) -> requests.models.Response:
        self._last_request = request
        response: requests.models.Response = request.method(**request.kwargs)
        return response

    def _retry_request(self, request: ApiReq) -> requests.models.Response:
        # Update auth_header with the newly refreshed access_token prior to retry
        request.kwargs['headers'] = self.auth_header
        response: requests.models.Response = self.api_req(request)
        return response

    def v1_me(self):
        response = self.api_req(
            ApiReq(
                kwargs={
                    "url":"https://api.spotify.com/v1/me",
                    "headers": self.auth_header,
                }
            )
        )
        print("v1/me: ", response.content)
        # TODO: do whatever processing is required here

    def get_users_liked_songs(self):
        pass # these are my "liked" songs

    def get_users_playlists(self):
        response = self.api_req(
            ApiReq(
                kwargs={
                    "url": f"https://api.spotify.com/v1/users/{MY_USER_ID}/playlists/",
                    "headers": self.auth_header,
                }
            )
        )
        playlists = json.loads(response.content)
        print("limit: ", playlists['limit'])
        print("next: ", playlists['next'])
        print([(x['id'], x['name']) for x in playlists['items']])

        # Wrap this up in some form of pagination method
        while playlists['next']:
            response = self.api_req(
                ApiReq(
                    kwargs={
                        "url": playlists['next'],
                        "headers": self.auth_header,
                    }
                )
            )

        with open("data/v1_my_playlists.json", "w") as f:
            json.dump(json.loads(response.content), f, indent=2)

    def _load_tokens(self) -> None:
        """
        Read secret access_token and refresh_token from JSON file on disk
        and load into environment variables.
        """
        
        with open(SECRETS_PATH, 'r') as f:
            secrets = json.load(f)
        
        os.environ['ACCESS_TOKEN'] = secrets['access_token']
        os.environ['REFRESH_TOKEN'] = secrets['refresh_token']


    def _save_tokens(self, access_token: str) -> None:
        """
        After using a refresh_token to request a new access_token, this
        function can be called to cache that access_token to disk. Also
        calls the method to load tokens so the env variables are in sync.
        """

        secrets = {
            'access_token': access_token,
            'refresh_token': os.environ['REFRESH_TOKEN']
        }

        with open(SECRETS_PATH, 'w') as f:
            json.dump(secrets, f)

        self._load_tokens()


    def _refresh_access_token(self):

        resp = requests.post(
            url='https://accounts.spotify.com/api/token',
            headers={
                "Authorization": "Basic " + base64.b64encode(bytes(f"{self.client_id}:{self.client_secret}", encoding='utf-8')).decode("utf-8"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            },
        )

        if resp.status_code == 200:
            self._save_tokens(json.loads(resp.content)['access_token'])


    def _backoff(self):
        time.sleep(10)



if __name__ == "__main__":
    spot = Spotify()
    spot.v1_me()
    print('-' * 50)
    spot.get_users_playlists()


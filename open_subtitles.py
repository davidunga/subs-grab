""" Wrapper for OpenSubtitles API """

import requests
import json
import os
from dataclasses import dataclass

# ------------------------------------------------------


@dataclass
class API_URL:
    """ OpenSubtitles API urls """
    LOGIN = "https://api.opensubtitles.com/api/v1/login"
    SEARCH = "https://api.opensubtitles.com/api/v1/subtitles"
    DOWNLOAD = "https://api.opensubtitles.com/api/v1/download"

@dataclass
class Credentials:
    """ OpenSubtitles credentials """
    username: str
    password: str
    api_key: str


CREDENTIALS_FILE = os.path.dirname(__file__) + "/credentials.json"

# ------------------------------------------------------


class OpenSubtitles:

    def __init__(self, credentials: Credentials = None, login: bool = True):
        """
        Args:
            credentials: OpenSubtitles credentials. default = load from credentials file
            login: login on initialization
        """
        self.credentials = load_credentials() if credentials is None else credentials
        self.token = None
        if login:
            self.login()

    def login(self):
        response = requests.post(
            API_URL.LOGIN,
            headers={'api-key': self.credentials.api_key, 'content-type': 'application/json'},
            data=json.dumps({'username': self.credentials.username, 'password': self.credentials.password})
        )
        response.raise_for_status()
        self.token = response.json()['token']

    def search(self, search_params: dict) -> dict:
        """ Search open subtitles DB """
        response = requests.get(
            API_URL.SEARCH,
            headers={'api-key': self.credentials.api_key},
            params=search_params
        )
        response.raise_for_status()
        return response.json()['data']

    def download_item(self, file_item: dict, dst_fname: str):
        """
        Download subtitle file item
        Args:
            file_item: open-subtitles api file item
            dst_fname: path to save subtitles to
        """
        response = requests.post(
            API_URL.DOWNLOAD,
            headers={'api-key': self.credentials.api_key,
                     'authorization': self.token,
                     'content-type': 'application/json'},
            data=json.dumps({'file_id': file_item['file_id']})
        )
        response.raise_for_status()
        open(dst_fname, 'wb').write(requests.get(response.json()['link']).content)


# ------------------------------------------------------


def load_credentials() -> Credentials:
    """ Load credentials from credentials.json """
    assert os.path.isfile(CREDENTIALS_FILE), \
        "No open-subtitles credentials file found. Create credentials.json with fields: username, password, api-key"
    credentials = json.load(open(CREDENTIALS_FILE, 'r'))
    assert set(credentials.keys()) == {"username", "password", "api-key"}, \
        "Invalid credentials file. credentials.json should contain fields: username, password, api-key"
    return Credentials(username=credentials["username"],
                       password=credentials["password"],
                       api_key=credentials["api-key"])

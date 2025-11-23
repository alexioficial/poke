from requests.models import Response
import requests
from urllib.parse import urlparse


def is_valid_url(url_string: str) -> bool:
    try:
        result = urlparse(url_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def fetch(url: str, params: dict = {}) -> dict:
    response: Response = requests.get(url=url, params=params, timeout=10)
    response.raise_for_status()
    data: dict = response.json()
    return data

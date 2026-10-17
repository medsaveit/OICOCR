import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

retries = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)

adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)


def graph_get(url, headers, params=None):
    try:
        resp = session.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.ChunkedEncodingError:
        print("⚠️ ChunkedEncodingError, retrying once...")
        resp = session.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as e:
        raise Exception(f"Graph GET failed: {e}")


def graph_post(url, headers, data):
    resp = session.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json() if resp.content else None

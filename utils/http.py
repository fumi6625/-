import itertools
import requests
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from config.settings import USER_AGENTS


_ua_cycle = itertools.cycle(USER_AGENTS)


def make_session() -> requests.Session:
    """共通ヘッダーを設定した requests.Session を返す"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": next(_ua_cycle),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


def rotate_ua(session: requests.Session) -> None:
    """セッションの User-Agent をローテーションする"""
    session.headers["User-Agent"] = next(_ua_cycle)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=32),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """リトライ付きGETリクエスト。429/503は短時間待機後リトライ"""
    resp = session.get(url, timeout=20, **kwargs)
    if resp.status_code in (429, 503):
        raise requests.ConnectionError(f"Rate limited: {resp.status_code}")
    return resp

"""
ホットペッパーグルメ スクレイパー

requests + BeautifulSoup を使用。
URL形式: https://www.hotpepper.jp/{area_code}/lst/  (例: SA23/Y300/lst/)
"""
import re
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, HP_STATION_AREA
from utils.http import make_session, get_with_retry, rotate_ua

logger = logging.getLogger(__name__)

BASE = "https://www.hotpepper.jp"
ITEMS_PER_PAGE = 20


class HotPepperScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._session = make_session()
        self._session.headers.update({
            "Referer": BASE + "/",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []

        area_code = HP_STATION_AREA.get(station_name)
        if not area_code:
            logger.warning(f"[ホットペッパー] エリアコード未設定: {station_name}")
            return results

        max_pages = 2 if self.dry_run else 50

        for page in range(1, max_pages + 1):
            soup = self._fetch_page(area_code, page)
            if soup is None:
                break

            cards = soup.select("div.shopDetailText")
            if not cards:
                logger.info(f"[ホットペッパー] {station_name}: 結果なし（p{page}）")
                break

            logger.info(f"[ホットペッパー] {station_name} p{page}: {len(cards)}件")

            for card in cards:
                try:
                    r = self._parse_card(card, station_name)
                    if r and (r.budget == 0 or r.budget <= MAX_BUDGET):
                        results.append(r)
                except Exception as e:
                    logger.warning(f"[ホットペッパー] カード解析エラー: {e}")

            if not self._has_next_page(soup):
                break

            self._list_sleep()

        return results

    # ──────────────────────────────────────────

    def _fetch_page(self, area_code: str, page: int):
        # page1: /SA23/Y300/lst/  page2: /SA23/Y300/lst/bgn21/  ...
        bgn = "" if page == 1 else f"bgn{(page - 1) * ITEMS_PER_PAGE + 1}/"
        url = f"{BASE}/{area_code}/lst/{bgn}"
        try:
            resp = get_with_retry(
                self._session, url,
                headers={"Referer": f"{BASE}/{area_code}/"},
                allow_redirects=True,
            )
            rotate_ua(self._session)
            logger.info(f"[ホットペッパー] {url} → {resp.status_code} ({len(resp.text)}文字)")
            if resp.status_code == 200 and len(resp.text) > 1000:
                return BeautifulSoup(resp.text, "lxml")
            return None
        except Exception as e:
            logger.warning(f"[ホットペッパー] 取得失敗 {url}: {e}")
            return None

    def _parse_card(self, card, station_name: str) -> Restaurant | None:
        # 店名・URL
        name_tag = card.select_one("h3.shopDetailStoreName a")
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        href = name_tag.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else urljoin(BASE, href)

        # ジャンル: "韓国料理｜東通り" → "韓国料理" だけ取り出す
        genre_tag = card.select_one("p.parentGenreName")
        genre = genre_tag.get_text(strip=True).split("｜")[0] if genre_tag else ""

        # アクセス情報（住所代わり）
        access_tag = card.select_one("li.shopDetailInfoAccess")
        address = access_tag.get("title") or access_tag.get_text(strip=True) if access_tag else ""

        # 予算（ディナー）: "2001～3000円" → 3000
        budget_tag = card.select_one("div.storeBudgetAverage p.dinnerBudget")
        budget_text = budget_tag.get_text(strip=True) if budget_tag else ""
        budget = self._parse_budget(budget_text)

        # キャッチコピーとアイコンリストから設備情報を取得
        full_text = card.get_text(" ", strip=True)
        seats_match = re.search(r"(\d+)\s*席", full_text)
        seats = int(seats_match.group(1)) if seats_match else 0
        has_course    = "有" if "コース" in full_text else "不明"
        all_you_drink = "有" if "飲み放題" in full_text else "不明"
        private_room  = "有" if "個室" in full_text else "不明"

        return Restaurant(
            name=name,
            station=station_name,
            address=address,
            genre=genre,
            has_course=has_course,
            all_you_drink=all_you_drink,
            seats=seats,
            private_room=private_room,
            budget=budget,
            url=url,
            source="hotpepper",
        )

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        return bool(
            soup.select_one("a.next") or
            soup.select_one("li.next a") or
            soup.select_one("a[rel='next']") or
            soup.select_one("p.pagination-parts a.current + a")
        )

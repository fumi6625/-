"""
ホットペッパーグルメ スクレイパー

requests + BeautifulSoup を使用。
駅名でキーワード検索 → 一覧取得 → 詳細取得。
"""
import re
import logging
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, SEARCH_RADIUS_KM
from utils.http import make_session, get_with_retry, rotate_ua

logger = logging.getLogger(__name__)

BASE = "https://www.hotpepper.jp"

# 予算上限6000円以下に対応するコード群
# B006=3001-4000, B007=4001-5000, B008=5001-7000（6000円以内を後でフィルタ）
BUDGET_CODES = ["B006", "B007", "B008"]

# 検索URL候補（順番に試す）
SEARCH_URL_TEMPLATES = [
    # パターン1: エリア＋キーワード検索
    BASE + "/SA11/sk{keyword}/",
    # パターン2: キーワードのみ
    BASE + "/Saccess0EntranceAction.do?sk={keyword}&sa=&rsc=0&vn=1",
    # パターン3: 旧形式フォールバック
    BASE + "/yoyaku/rstSearchTop.do?freeword={keyword}&BUGET=B008&PG={page}",
]


class HotPepperScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._session = make_session()
        self._session.headers.update({
            "Referer": BASE + "/",
        })

    # ──────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []
        # 駅名から「駅」を除去（例: 梅田駅 → 梅田）
        keyword = station_name.replace("駅", "")
        encoded = quote(keyword, safe="")

        max_pages = 2 if self.dry_run else 50

        for page in range(1, max_pages + 1):
            soup, final_url = self._fetch_search_page(encoded, page)
            if soup is None:
                break

            # 複数のカードセレクタを試す
            cards = self._find_cards(soup)
            if not cards:
                logger.info(f"[ホットペッパー] {station_name}: 結果なし（p{page}）")
                break

            logger.info(f"[ホットペッパー] {station_name} p{page}: {len(cards)}件")

            for card in cards:
                try:
                    restaurant = self._parse_card(card, station_name, final_url)
                    if not restaurant:
                        continue
                    # 予算フィルタ
                    if 0 < restaurant.budget > MAX_BUDGET:
                        continue
                    results.append(restaurant)
                except Exception as e:
                    logger.warning(f"[ホットペッパー] カード解析エラー: {e}")

            if not self._has_next_page(soup):
                break

            self._list_sleep()

        return results

    # ──────────────────────────────────────────
    # ページ取得
    # ──────────────────────────────────────────

    def _fetch_search_page(self, encoded_keyword: str, page: int):
        """複数のURL形式を試してページを取得する"""
        urls_to_try = [
            # 現行の主要URL形式
            f"{BASE}/SA11/sk{encoded_keyword}/",
            f"{BASE}/SA11/sk{encoded_keyword}/bgn{(page-1)*20+1}/",
            # 別形式
            f"{BASE}/Saccess0EntranceAction.do?sk={encoded_keyword}&rsc=0&vn=1&start={page}",
            # フリーワード検索
            f"{BASE}/rstSearch/keyword={encoded_keyword}/page={page}/",
        ]

        for url in urls_to_try:
            try:
                resp = get_with_retry(
                    self._session, url,
                    headers={"Referer": BASE + "/"},
                    allow_redirects=True,
                )
                rotate_ua(self._session)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    soup = BeautifulSoup(resp.text, "lxml")
                    # 404ページや空ページを除外
                    if "存在しません" in resp.text or "not found" in resp.text.lower():
                        continue
                    return soup, resp.url
            except Exception as e:
                logger.debug(f"URL試行失敗 {url}: {e}")
                continue

        logger.warning(f"[ホットペッパー] すべてのURL形式が失敗")
        return None, None

    # ──────────────────────────────────────────
    # カード検索
    # ──────────────────────────────────────────

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """ページ内の店舗カード要素を探す"""
        selectors = [
            # 現行HTML
            "div.cassetteRestaurant",
            "li.cassetteRestaurant",
            "article.cassetteRestaurant",
            # 旧HTML
            "div.shopDetailInfo",
            "section.shopDetail",
            "div.rstCassette",
            "li.shopListItem",
            # 汎用
            "div.list-cassette__item",
            "li.list-item",
            "div[class*='cassette']",
            "li[class*='cassette']",
        ]
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                return cards
        return []

    # ──────────────────────────────────────────
    # カード解析
    # ──────────────────────────────────────────

    def _parse_card(self, card, station_name: str, base_url: str) -> Restaurant | None:
        """カード要素から Restaurant を生成する"""
        # 店名・URL
        name_tag = (
            card.select_one("h3 a") or
            card.select_one("h2 a") or
            card.select_one("p.cassetteRestaurant__name a") or
            card.select_one("a[href*='/str']") or
            card.select_one("a[href*='hotpepper']")
        )
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        href = name_tag.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else urljoin(BASE, href)

        # ジャンル
        genre_tag = (
            card.select_one("p.cassetteRestaurant__type") or
            card.select_one("span.cassetteRestaurant__categoryItem") or
            card.select_one("p.shopDetailInfoCatch") or
            card.select_one("span.shopCategory") or
            card.select_one("[class*='category']") or
            card.select_one("[class*='genre']")
        )
        genre = genre_tag.get_text(strip=True) if genre_tag else ""

        # 住所
        addr_tag = (
            card.select_one("p.cassetteRestaurant__address") or
            card.select_one("p.shopAddress") or
            card.select_one("span[itemprop='streetAddress']") or
            card.select_one("[class*='address']")
        )
        address = addr_tag.get_text(strip=True) if addr_tag else ""

        # 予算
        budget_tag = (
            card.select_one("p.cassetteRestaurant__price") or
            card.select_one("span.cassetteRestaurant__priceNum") or
            card.select_one("[class*='budget']") or
            card.select_one("[class*='price']")
        )
        budget_text = budget_tag.get_text(strip=True) if budget_tag else ""
        budget = self._parse_budget(budget_text)

        # テキスト全体から席数・設備を取得
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
        next_link = (
            soup.select_one("a.next") or
            soup.select_one("li.next a") or
            soup.select_one("a[rel='next']") or
            soup.select_one("[class*='next']")
        )
        return next_link is not None

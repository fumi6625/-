"""
ホットペッパーグルメ スクレイパー

requests + BeautifulSoup を使用。
駅のエリアコード（SA23/Y***）でエリア検索 → 一覧取得。
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


class HotPepperScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._session = make_session()
        self._session.headers.update({
            "Referer": BASE + "/",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    # ──────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []

        area_code = HP_STATION_AREA.get(station_name)
        if not area_code:
            logger.warning(f"[ホットペッパー] エリアコード未設定: {station_name}")
            return results

        max_pages = 2 if self.dry_run else 50

        for page in range(1, max_pages + 1):
            soup, final_url = self._fetch_search_page(area_code, page)
            if soup is None:
                break

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
                    # 予算フィルタ（0=未取得は除外しない）
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

    def _fetch_search_page(self, area_code: str, page: int):
        """エリアコードを使って検索ページを取得する"""
        # page 1 は bgn1 なし、page 2 以降は bgn{(page-1)*20+1}
        bgn = "" if page == 1 else f"bgn{(page - 1) * 20 + 1}/"

        urls_to_try = [
            f"{BASE}/{area_code}/{bgn}",
            f"{BASE}/{area_code}/bgn{(page-1)*20+1}/",
        ]

        # 重複除去
        seen = set()
        deduped = []
        for u in urls_to_try:
            if u not in seen:
                seen.add(u)
                deduped.append(u)

        for url in deduped:
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

        logger.warning(f"[ホットペッパー] エリア {area_code} p{page}: 取得失敗")
        return None, None

    # ──────────────────────────────────────────
    # カード検索
    # ──────────────────────────────────────────

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """ページ内の店舗カード要素を探す"""
        selectors = [
            # 現行HTML（エリアページ）
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
                logger.debug(f"[ホットペッパー] カードセレクタ: {sel} ({len(cards)}件)")
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
            card.select_one("a.shopDetailInfoTitle") or
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
            soup.select_one("a[class*='next']")
        )
        return next_link is not None

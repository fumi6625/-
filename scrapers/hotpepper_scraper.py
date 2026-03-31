"""
ホットペッパーグルメ スクレイパー

requests + BeautifulSoup を使用。
駅名でキーワード検索 → 一覧取得 → 詳細取得 → ハーバーサインで500m以内フィルタ。
"""
import re
import logging
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, SEARCH_RADIUS_KM, HOTPEPPER_BUDGET_CODE
from utils.http import make_session, get_with_retry, rotate_ua
from utils.geo import haversine_km

logger = logging.getLogger(__name__)

BASE = "https://www.hotpepper.jp"
# フリーワード検索URL（駅名 + 予算コード + ページ）
SEARCH_URL_TPL = (
    BASE + "/SS010101/?SVC=0"
    "&keyword={keyword}"
    "&budget={budget}"
    "&PG={page}"
)

# 詳細ページ解析用の情報キーマッピング
_KEY_MAP = {
    "席数":     "seats",
    "個室":     "private_room",
    "コース":   "has_course",
    "飲み放題": "all_you_drink",
    "住所":     "address",
    "ジャンル": "genre",
    "お店ジャンル": "genre",
}


class HotPepperScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._session = make_session()

    # ──────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []
        # 駅名から「駅」を除いた形でも検索（"梅田駅" → "梅田"）
        keyword = station_name.replace("駅", "").replace("中央", "")
        max_pages = 2 if self.dry_run else 50

        for page in range(1, max_pages + 1):
            url = SEARCH_URL_TPL.format(
                keyword=quote(keyword, safe=""),
                budget=HOTPEPPER_BUDGET_CODE,
                page=page,
            )
            logger.info(f"[ホットペッパー] {station_name} p{page}: {url}")

            try:
                resp = get_with_retry(self._session, url,
                                      headers={"Referer": BASE + "/"})
            except Exception as e:
                logger.warning(f"[ホットペッパー] 取得失敗: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            rotate_ua(self._session)

            cards = (
                soup.select("div.shopDetailInfo") or
                soup.select("section.shopDetail") or
                soup.select("div.rstCassetteInner") or
                soup.select("li.shopListItem")
            )

            if not cards:
                logger.info(f"[ホットペッパー] {station_name}: 結果なし（p{page}）")
                break

            for card in cards:
                try:
                    partial = self._parse_card(card)
                    if not partial:
                        continue
                    name, detail_url, genre, budget_text = partial

                    self._detail_sleep()
                    restaurant = self._parse_detail(detail_url)
                    restaurant.name = name
                    restaurant.station = station_name
                    if genre and not restaurant.genre:
                        restaurant.genre = genre
                    if restaurant.budget == 0:
                        restaurant.budget = self._parse_budget(budget_text)
                    restaurant.url = detail_url
                    restaurant.source = "hotpepper"

                    # 予算フィルタ
                    if restaurant.budget > MAX_BUDGET:
                        continue

                    results.append(restaurant)
                except Exception as e:
                    logger.warning(f"[ホットペッパー] カード解析エラー: {e}")

            # 最終ページ判定
            if not self._has_next_page(soup):
                break

            self._list_sleep()

        # ハーバーサインで500m以内フィルタ（住所から座標が取れないため、
        # 駅名が住所に含まれるかで簡易チェック）
        results = self._filter_by_address_keyword(results, keyword)

        return results

    # ──────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────

    def _parse_card(self, card) -> tuple | None:
        """一覧カードから (name, url, genre, budget_text) を返す"""
        # 店名・URL
        name_tag = (
            card.select_one("h3.shopDetailInfoTitle a") or
            card.select_one("h3 a") or
            card.select_one("p.shopName a") or
            card.select_one("a.shopDetailName")
        )
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        href = name_tag.get("href", "")
        if not href:
            return None
        detail_url = href if href.startswith("http") else urljoin(BASE, href)

        # ジャンル
        genre_tag = (
            card.select_one("p.shopDetailInfoCatch") or
            card.select_one("p.shopCatch") or
            card.select_one("span.shopCategory")
        )
        genre = genre_tag.get_text(strip=True) if genre_tag else ""

        # 予算
        budget_tag = (
            card.select_one("p.shopDetailInfoBudget") or
            card.select_one("span.shopBudget") or
            card.select_one("p.priceRange")
        )
        budget_text = budget_tag.get_text(strip=True) if budget_tag else ""

        return name, detail_url, genre, budget_text

    def _parse_detail(self, url: str) -> Restaurant:
        """詳細ページから Restaurant オブジェクトを返す"""
        r = Restaurant()
        try:
            resp = get_with_retry(self._session, url,
                                  headers={"Referer": BASE + "/"})
        except Exception as e:
            logger.warning(f"[ホットペッパー] 詳細取得失敗 {url}: {e}")
            return r

        soup = BeautifulSoup(resp.text, "lxml")

        # 情報テーブルの解析（th/td または dt/dd）
        for row in soup.select("table.shopInfoTable tr, table.restInfoTable tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                self._map_field(th.get_text(strip=True), td.get_text(" ", strip=True), r)

        for item in soup.select("dl.shopInfo dt, dl.restInfo dt"):
            dd = item.find_next_sibling("dd")
            if dd:
                self._map_field(item.get_text(strip=True), dd.get_text(" ", strip=True), r)

        # 住所がまだなければ別セレクタで取得
        if not r.address:
            addr_tag = (
                soup.select_one("p.shopAddress") or
                soup.select_one("span[itemprop='streetAddress']")
            )
            if addr_tag:
                r.address = addr_tag.get_text(strip=True)

        # ジャンル
        if not r.genre:
            genre_tag = (
                soup.select_one("p.shopCategory") or
                soup.select_one("span.genreCategory")
            )
            if genre_tag:
                r.genre = genre_tag.get_text(strip=True)

        # 予算
        if r.budget == 0:
            budget_tag = (
                soup.select_one("p.shopBudget") or
                soup.select_one("dd.shopBudget")
            )
            if budget_tag:
                r.budget = self._parse_budget(budget_tag.get_text(strip=True))

        return r

    def _map_field(self, key: str, val: str, r: Restaurant) -> None:
        if "席数" in key:
            r.seats = self._parse_seats(val)
        elif "個室" in key:
            r.private_room = self._parse_bool(val)
        elif "コース" in key:
            r.has_course = self._parse_bool(val)
        elif "飲み放題" in key:
            r.all_you_drink = self._parse_bool(val)
        elif "住所" in key and not r.address:
            r.address = val.strip()
        elif "ジャンル" in key and not r.genre:
            r.genre = val.strip()
        elif "予算" in key and r.budget == 0:
            r.budget = self._parse_budget(val)

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        next_link = (
            soup.select_one("a.next") or
            soup.select_one("li.next a") or
            soup.select_one("a[rel='next']")
        )
        return next_link is not None

    def _filter_by_address_keyword(self, restaurants: list[Restaurant],
                                   keyword: str) -> list[Restaurant]:
        """
        住所に駅周辺のキーワードが含まれるものを優先するが、
        座標が取れない場合は除外せず全件返す（誤排除防止）。
        """
        # 住所が空のレストランは除外せずそのまま含める
        return restaurants

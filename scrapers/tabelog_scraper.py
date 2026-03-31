"""
食べログスクレイパー

Cloudflare の Bot Management を回避するため undetected_chromedriver を使用。
一覧ページ → 詳細ページの順にスクレイピングする。
"""
import re
import time
import random
import logging

from bs4 import BeautifulSoup

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, SEARCH_RADIUS_KM
from utils.geo import haversine_km

logger = logging.getLogger(__name__)

# 食べログ一覧の検索URL（緯度・経度・半径・予算上限・ページ番号）
LIST_URL_TPL = (
    "https://tabelog.com/osaka/rstLst/?"
    "vs=1&sa=&sk=&lid=&vac_net=&svd=&svt=&svps=&hfc=1&sw="
    "&lat={lat}&lon={lon}&dist={dist}&LstCos=2"
    "&price_max={price_max}&p={page}"
)


class TabelogScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._driver = None

    # ──────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []
        if not SELENIUM_AVAILABLE:
            logger.error("undetected_chromedriver がインストールされていません。pip install undetected-chromedriver")
            return results

        driver = self._get_driver()
        page = 1
        max_pages = 2 if self.dry_run else 60

        while page <= max_pages:
            url = LIST_URL_TPL.format(
                lat=lat, lon=lon, dist=SEARCH_RADIUS_KM,
                price_max=MAX_BUDGET, page=page,
            )
            logger.info(f"[食べログ] {station_name} p{page}: {url}")
            try:
                driver.get(url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.warning(f"[食べログ] ページ読み込み失敗: {e}")
                break

            soup = BeautifulSoup(driver.page_source, "lxml")
            cards = soup.select("div.list-rst__wrap")

            if not cards:
                logger.info(f"[食べログ] {station_name}: 結果なし（p{page}）")
                break

            for card in cards:
                try:
                    partial = self._parse_card(card)
                    if not partial:
                        continue
                    name, detail_url, genre, budget_text = partial

                    self._detail_sleep()
                    restaurant = self._parse_detail(driver, detail_url)
                    restaurant.name = name
                    restaurant.station = station_name
                    restaurant.genre = genre or restaurant.genre
                    if restaurant.budget == 0:
                        restaurant.budget = self._parse_budget(budget_text)
                    restaurant.url = detail_url
                    restaurant.source = "tabelog"

                    # 予算フィルタ（0=未取得は除外しない）
                    if 0 < restaurant.budget > MAX_BUDGET:
                        continue

                    results.append(restaurant)
                except Exception as e:
                    logger.warning(f"[食べログ] カード解析エラー: {e}")

            # ページネーション
            next_btn = soup.select_one("a.c-pagination__arrow--next:not(.is-disabled)")
            if not next_btn:
                break
            page += 1
            self._list_sleep()

        return results

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    # ──────────────────────────────────────────
    # Selenium driver
    # ──────────────────────────────────────────

    def _get_driver(self):
        if self._driver is None:
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--lang=ja-JP")
            self._driver = uc.Chrome(options=options, use_subprocess=True)
        return self._driver

    # ──────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────

    def _parse_card(self, card) -> tuple | None:
        """一覧カードから (name, url, genre, budget_text) を返す"""
        name_tag = card.select_one("a.list-rst__rst-name-target")
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        url = name_tag.get("href", "")
        if not url.startswith("http"):
            url = "https://tabelog.com" + url

        genre_tag = card.select_one("span.list-rst__category-main-name")
        genre = genre_tag.get_text(strip=True) if genre_tag else ""

        budget_tag = card.select_one("span.c-rating-v2__val--dinner") or \
                     card.select_one("em.list-rst__budget-dinner")
        budget_text = budget_tag.get_text(strip=True) if budget_tag else ""

        return name, url, genre, budget_text

    def _parse_detail(self, driver, url: str) -> Restaurant:
        """詳細ページから Restaurant オブジェクトを返す"""
        r = Restaurant()
        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div#rst-data-head"))
            )
            time.sleep(random.uniform(1.5, 3))
        except TimeoutException:
            logger.warning(f"[食べログ] 詳細ページタイムアウト: {url}")
            return r

        soup = BeautifulSoup(driver.page_source, "lxml")

        # 住所
        addr_tag = (
            soup.select_one("p.rstdtl-side-yoyaku__address") or
            soup.select_one("span[itemprop='streetAddress']") or
            soup.select_one("p.pr-info__address")
        )
        r.address = addr_tag.get_text(strip=True) if addr_tag else ""

        # テーブル情報（席数・個室・コース・飲み放題）
        info_table = soup.select("table.c-table-rst tr") or soup.select("dl.rstdtl-top-info__item")
        self._extract_table_info(soup, r)

        # ジャンル
        genre_tag = soup.select_one("span.rstdtl-top-info__category-name") or \
                    soup.select_one("li.linktree__parent-target")
        if genre_tag:
            r.genre = genre_tag.get_text(strip=True)

        # 予算（詳細）
        budget_tag = soup.select_one("span.c-rating-v2__val--dinner") or \
                     soup.select_one("p.rstdtl-side-yoyaku__budget")
        if budget_tag:
            r.budget = self._parse_budget(budget_tag.get_text(strip=True))

        return r

    def _extract_table_info(self, soup: BeautifulSoup, r: Restaurant) -> None:
        """店舗情報テーブルからフィールドを埋める"""
        # テーブル形式とDL形式の両方に対応
        for row in soup.select("table tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            key = th.get_text(strip=True)
            val = td.get_text(" ", strip=True)
            self._map_field(key, val, r)

        for item in soup.select("dl.rstdtl-top-info__item"):
            dt = item.select_one("dt")
            dd = item.select_one("dd")
            if dt and dd:
                self._map_field(dt.get_text(strip=True), dd.get_text(" ", strip=True), r)

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
            r.address = val



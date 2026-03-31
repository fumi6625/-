"""
Google ビジネス（Google Maps）スクレイパー

undetected_chromedriver を使用して Google Maps から店舗情報を取得する。
"""
import re
import time
import logging

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, SEARCH_RADIUS_KM

logger = logging.getLogger(__name__)


class GoogleBusinessScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            try:
                import undetected_chromedriver as uc
                options = uc.ChromeOptions()
                options.add_argument("--lang=ja-JP")
                options.add_argument("--window-size=1280,900")
                self._driver = uc.Chrome(options=options, headless=True)
                logger.info("[Google] Chrome 起動成功")
            except Exception as e:
                logger.error(f"[Google] Chrome 起動失敗: {e}")
                raise
        return self._driver

    def close(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []
        try:
            driver = self._get_driver()
        except Exception:
            return results

        # Google Maps 検索: 緯度経度でエリア指定 + キーワード
        query = f"{station_name} 飲食店"
        # zoom=16 ≒ 500m圏内表示
        url = (
            f"https://www.google.com/maps/search/{query}"
            f"/@{lat},{lon},16z?hl=ja"
        )
        logger.info(f"[Google] {station_name}: {url}")

        try:
            driver.get(url)
            time.sleep(3)  # ページ読み込み待機

            # 結果フィードが表示されるまで待機
            for _ in range(10):
                if self._find_feed(driver):
                    break
                time.sleep(1)

            # スクロールして結果を追加読み込み
            max_scroll = 2 if self.dry_run else 8
            self._scroll_feed(driver, max_scroll)

            # HTML解析
            soup = BeautifulSoup(driver.page_source, "lxml")
            items = self._find_items(soup)
            logger.info(f"[Google] {station_name}: {len(items)}件のカード取得")

            for item in items:
                try:
                    r = self._parse_item(item, station_name)
                    if r and (r.budget == 0 or r.budget <= MAX_BUDGET):
                        results.append(r)
                except Exception as e:
                    logger.debug(f"[Google] カード解析エラー: {e}")

        except Exception as e:
            logger.warning(f"[Google] {station_name} 取得エラー: {e}")

        return results

    # ──────────────────────────────────────────

    def _find_feed(self, driver) -> bool:
        """結果フィードが存在するか確認"""
        try:
            return bool(driver.find_elements("css selector", 'div[role="feed"]'))
        except Exception:
            return False

    def _scroll_feed(self, driver, times: int):
        """フィードをスクロールして追加結果を読み込む"""
        try:
            feed_selectors = ['div[role="feed"]', 'div[aria-label*="結果"]', 'div[aria-label*="Result"]']
            feed = None
            for sel in feed_selectors:
                elems = driver.find_elements("css selector", sel)
                if elems:
                    feed = elems[0]
                    break
            if not feed:
                return
            for _ in range(times):
                driver.execute_script("arguments[0].scrollBy(0, 600);", feed)
                time.sleep(1.2)
        except Exception as e:
            logger.debug(f"[Google] スクロールエラー: {e}")

    def _find_items(self, soup: BeautifulSoup) -> list:
        """店舗カード要素を探す"""
        selectors = [
            'div[role="article"]',
            'a[href*="/maps/place/"]',
            'div[jsaction*="mouseover"]',
        ]
        for sel in selectors:
            items = soup.select(sel)
            if items:
                logger.debug(f"[Google] カードセレクタ: {sel} ({len(items)}件)")
                return items

        # フォールバック: /maps/place/ リンクを含む親要素
        place_links = soup.find_all("a", href=re.compile(r"/maps/place/"))
        parents = []
        seen_ids = set()
        for link in place_links:
            parent = link.find_parent("div", attrs={"role": re.compile(r"article|listitem")})
            if parent is None:
                parent = link.find_parent("div")
            if parent and id(parent) not in seen_ids:
                seen_ids.add(id(parent))
                parents.append(parent)
        return parents

    def _parse_item(self, item, station_name: str) -> Restaurant | None:
        """カード要素から Restaurant を生成"""
        # 店舗ページURL (Google Maps)
        place_link = item.select_one('a[href*="/maps/place/"]') or item.select_one("a[href]")
        href = place_link.get("href", "") if place_link else ""
        if not href:
            return None
        url = href if href.startswith("http") else "https://www.google.com" + href

        # aria-label からの名前取得（最も安定）
        name = ""
        aria = item.get("aria-label", "")
        if aria:
            name = aria.split("·")[0].strip()

        # aria-label がない場合は最初の有意義なテキストを使用
        if not name:
            for tag in item.find_all(["h3", "span", "div"]):
                t = tag.get_text(strip=True)
                if t and len(t) > 1 and len(t) < 60 and not t.startswith("http"):
                    name = t
                    break

        if not name:
            return None

        # テキスト全体から情報を抽出
        full_text = item.get_text(" ", strip=True)

        # ジャンル（"居酒屋"、"ラーメン"などのカテゴリ）
        genre_patterns = [
            r"居酒屋", r"ラーメン", r"焼肉", r"寿司|すし", r"イタリアン",
            r"中華", r"和食", r"洋食", r"カフェ", r"焼き鳥", r"串揚げ",
            r"海鮮", r"鉄板焼", r"しゃぶしゃぶ", r"うどん", r"そば",
            r"韓国料理", r"バー", r"ダイニング",
        ]
        genre = ""
        for pat in genre_patterns:
            if re.search(pat, full_text):
                genre = re.search(pat, full_text).group(0)
                break

        # 住所（「大阪府」「〒」などで始まる文字列）
        addr_match = re.search(r"(大阪[^\s]{3,30}|〒\d{3}-\d{4}[^\s]+)", full_text)
        address = addr_match.group(0) if addr_match else ""

        # 予算（「¥」「円」を含む数値）
        budget_match = re.search(r"[¥￥][\d,]+", full_text)
        budget = self._parse_budget(budget_match.group(0)) if budget_match else 0

        # 席数
        seats_match = re.search(r"(\d+)\s*席", full_text)
        seats = int(seats_match.group(1)) if seats_match else 0

        return Restaurant(
            name=name,
            station=station_name,
            address=address,
            genre=genre,
            has_course="有" if "コース" in full_text else "不明",
            all_you_drink="有" if "飲み放題" in full_text else "不明",
            seats=seats,
            private_room="有" if "個室" in full_text else "不明",
            budget=budget,
            url=url,
            source="google",
        )

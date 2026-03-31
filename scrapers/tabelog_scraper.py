"""
食べログスクレイパー

デバッグで requests+BeautifulSoup でも一覧ページが取得できることが判明。
一覧: requests+BeautifulSoup
詳細: requests+BeautifulSoup（失敗時は情報を最大限取得）
"""
import re
import time
import random
import logging

import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant
from config.settings import MAX_BUDGET, SEARCH_RADIUS_KM
from utils.http import make_session, get_with_retry, rotate_ua

logger = logging.getLogger(__name__)

BASE = "https://tabelog.com"

# 一覧ページ検索URL（緯度・経度・半径・予算上限・ページ番号）
LIST_URL_TPL = (
    "https://tabelog.com/osaka/rstLst/?"
    "vs=1&lat={lat}&lon={lon}&dist={dist}"
    "&price_max={price_max}&p={page}"
)


class TabelogScraper(BaseScraper):

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._session = make_session()
        self._session.headers.update({
            "Referer": "https://tabelog.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        results: list[Restaurant] = []
        page = 1
        max_pages = 2 if self.dry_run else 20

        while page <= max_pages:
            url = LIST_URL_TPL.format(
                lat=lat, lon=lon, dist=SEARCH_RADIUS_KM,
                price_max=MAX_BUDGET, page=page,
            )
            logger.info(f"[食べログ] {station_name} p{page}: {url}")

            try:
                resp = get_with_retry(self._session, url)
                rotate_ua(self._session)
            except Exception as e:
                logger.warning(f"[食べログ] 取得失敗: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.list-rst__wrap")

            if not cards:
                logger.info(f"[食べログ] {station_name}: 結果なし（p{page}）")
                break

            for card in cards:
                try:
                    restaurant = self._parse_card(card, station_name)
                    if not restaurant:
                        continue

                    # 予算フィルタ（0=未取得は除外しない）
                    if 0 < restaurant.budget > MAX_BUDGET:
                        continue

                    results.append(restaurant)
                except Exception as e:
                    logger.warning(f"[食べログ] カード解析エラー: {e}")

            # ページネーション確認
            next_btn = soup.select_one("a.c-pagination__arrow--next")
            if not next_btn or "is-disabled" in next_btn.get("class", []):
                break

            page += 1
            self._list_sleep()

        return results

    def close(self) -> None:
        pass  # requests.Session は明示的なクローズ不要

    # ──────────────────────────────────────────
    # 一覧カード解析（詳細ページへのアクセスなし）
    # ──────────────────────────────────────────

    def _parse_card(self, card, station_name: str) -> Restaurant | None:
        """一覧カードから Restaurant を生成する（詳細ページなし）"""
        # 店名・URL
        name_tag = card.select_one("a.list-rst__rst-name-target")
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        url = name_tag.get("href", "")
        if not url:
            return None
        if not url.startswith("http"):
            url = BASE + url

        # ジャンル: ".list-rst__area-genre" は "駅名 距離 / ジャンル" 形式
        genre_tag = card.select_one("p.list-rst__area-genre")
        if genre_tag:
            raw = genre_tag.get_text(" ", strip=True)
            # " / " で分割して後半部分をジャンルとして取得
            if " / " in raw:
                genre = raw.split(" / ", 1)[1].strip()
            else:
                genre = raw
        else:
            genre = ""

        # 予算（ディナー）: ".c-rating-v3__time--dinner .c-rating-v3__val"
        dinner_block = card.select_one(".c-rating-v3__time--dinner")
        if dinner_block:
            budget_tag = dinner_block.select_one(".c-rating-v3__val")
        else:
            budget_tag = card.select_one(".c-rating-v3__val")
        budget_text = budget_tag.get_text(strip=True) if budget_tag else ""
        budget = self._parse_budget(budget_text)

        # 住所
        addr_tag = (
            card.select_one("p.list-rst__address") or
            card.select_one("p.list-rst__area-genre")
        )
        address = addr_tag.get_text(strip=True) if addr_tag else ""
        # "住所: XXX" 形式の場合は "住所: " を除去
        address = re.sub(r"^住所[：:]\s*", "", address)

        # 席数・個室・コース・飲み放題
        # カード内のバッジ・アイコンから取得
        features_text = card.get_text(" ", strip=True)
        has_course    = "有" if "コース" in features_text else "不明"
        all_you_drink = "有" if "飲み放題" in features_text else "不明"
        private_room  = "有" if "個室" in features_text else "不明"
        seats_tag = card.select_one("li.list-rst__seat-count")
        seats = self._parse_seats(seats_tag.get_text(strip=True)) if seats_tag else 0

        r = Restaurant(
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
            source="tabelog",
        )
        return r

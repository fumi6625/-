import re
import time
import random
from abc import ABC, abstractmethod

from models.restaurant import Restaurant
from config.settings import LIST_SLEEP_MIN, LIST_SLEEP_MAX, DETAIL_SLEEP_MIN, DETAIL_SLEEP_MAX


class BaseScraper(ABC):

    @abstractmethod
    def search(self, station_name: str, lat: float, lon: float) -> list[Restaurant]:
        """指定駅・座標付近のレストランを返す"""
        ...

    # ──────────────────────────────────────────
    # Sleep helpers
    # ──────────────────────────────────────────

    def _list_sleep(self) -> None:
        time.sleep(random.uniform(LIST_SLEEP_MIN, LIST_SLEEP_MAX))

    def _detail_sleep(self) -> None:
        time.sleep(random.uniform(DETAIL_SLEEP_MIN, DETAIL_SLEEP_MAX))

    # ──────────────────────────────────────────
    # Text parsers
    # ──────────────────────────────────────────

    def _parse_seats(self, text: str) -> int:
        """
        "50席" / "最大50名" / "～50名" などから数値を抽出。
        見つからなければ 0 を返す。
        """
        if not text:
            return 0
        m = re.search(r"(\d+)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    def _parse_bool(self, text: str) -> str:
        """
        "あり" / "有" → "有",  "なし" / "無" → "無",  それ以外 → "不明"
        """
        if not text:
            return "不明"
        t = text.strip()
        if re.search(r"あり|有|○|◯|有り", t):
            return "有"
        if re.search(r"なし|無|×|なし", t):
            return "無"
        return "不明"

    def _parse_budget(self, text: str) -> int:
        """
        "〜¥4,000" / "3000円〜4000円" / "3,000～4,999円" などから
        上限金額を整数で返す。見つからなければ 0。
        """
        if not text:
            return 0
        clean = text.replace(",", "").replace("，", "").replace("¥", "").replace("円", "")
        # 範囲の場合は最後の数値を上限とする
        nums = re.findall(r"\d+", clean)
        if not nums:
            return 0
        return int(nums[-1])

    # ──────────────────────────────────────────
    # Deduplication helper (used in main)
    # ──────────────────────────────────────────

    @staticmethod
    def dedup(restaurants: list[Restaurant]) -> list[Restaurant]:
        """店名＋住所先頭20文字で重複を排除する"""
        seen: set = set()
        result: list[Restaurant] = []
        for r in restaurants:
            key = (r.name.strip(), r.address[:20].strip())
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result

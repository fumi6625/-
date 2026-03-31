"""
デバッグスクリプト v2: 実際に取得できるHTMLを確認する
実行: python3 debug_scrapers.py
"""
import sys
import re

# ── undetected_chromedriver のインポート確認 ──────────────────────
print("=" * 60)
print("① パッケージ確認")
print("=" * 60)
try:
    import undetected_chromedriver as uc
    print("✓ undetected_chromedriver OK")
except ImportError as e:
    print(f"✗ undetected_chromedriver: {e}")
    if "distutils" in str(e):
        print("→ 修正方法: pip3 install setuptools")
    else:
        print("→ 修正方法: pip3 install undetected-chromedriver")

try:
    from selenium.webdriver.common.by import By
    print("✓ selenium OK")
except ImportError:
    print("✗ selenium → pip3 install selenium")

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9",
    "Referer": "https://www.hotpepper.jp/",
}

# ── ホットペッパー 複数URL試行 ────────────────────────────────────
print()
print("=" * 60)
print("② ホットペッパー URL確認")
print("=" * 60)

hp_urls = [
    "https://www.hotpepper.jp/SA11/sk梅田/",
    "https://www.hotpepper.jp/SA11/",
    "https://www.hotpepper.jp/s1/",
    "https://www.hotpepper.jp/",
]

for url in hp_urls:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.title.string[:50] if soup.title else "なし"
        # カード候補を探す
        card_count = 0
        card_selector = ""
        for sel in ["div.cassetteRestaurant", "li.cassetteRestaurant",
                    "div.shopDetailInfo", "div.rstCassette", "article"]:
            c = soup.select(sel)
            if c:
                card_count = len(c)
                card_selector = sel
                break
        print(f"[{resp.status_code}] {url[:60]}")
        print(f"  タイトル: {title}")
        print(f"  カード: {card_count}件 ({card_selector})")
        if card_count > 0:
            print(f"  → このURLが使えます！")
            # 最初のカードのHTML構造を表示
            first = soup.select(card_selector)[0]
            links = [a['href'] for a in first.select("a[href]")[:2]]
            print(f"  リンク例: {links}")
            break
    except Exception as e:
        print(f"  エラー: {e}")

# ── 食べログ 確認 ─────────────────────────────────────────────────
print()
print("=" * 60)
print("③ 食べログ確認（requests で20件取得できるか）")
print("=" * 60)

url_tb = ("https://tabelog.com/osaka/rstLst/?"
          "vs=1&lat=34.7025&lon=135.4959&dist=0.5&price_max=6000&p=1")
HEADERS["Referer"] = "https://tabelog.com/"
resp_tb = requests.get(url_tb, headers=HEADERS, timeout=20)
soup_tb = BeautifulSoup(resp_tb.text, "lxml")
cards = soup_tb.select("div.list-rst__wrap")
print(f"ステータス: {resp_tb.status_code}")
print(f"カード数: {len(cards)}件")
if cards:
    first = cards[0]
    name = first.select_one("a.list-rst__rst-name-target")
    genre = first.select_one("span.list-rst__category-main-name")
    budget = first.select_one("span.c-rating-v2__val--dinner")
    print(f"  1件目 店名: {name.get_text(strip=True) if name else '?'}")
    print(f"  1件目 ジャンル: {genre.get_text(strip=True) if genre else '?'}")
    print(f"  1件目 予算: {budget.get_text(strip=True) if budget else '?'}")

print()
print("=" * 60)
print("デバッグ完了")
print("=" * 60)

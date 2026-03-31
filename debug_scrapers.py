"""
デバッグスクリプト: 実際に取得できるHTMLを確認する
実行: python3 debug_scrapers.py
"""
import sys
import subprocess

# ── undetected_chromedriver のインポート確認 ──────────────────────
print("=" * 60)
print("① undetected_chromedriver インポート確認")
print("=" * 60)
try:
    import undetected_chromedriver as uc
    print("✓ undetected_chromedriver OK")
except ImportError as e:
    print(f"✗ エラー: {e}")
    print("→ 実行: pip3 install undetected-chromedriver selenium")

try:
    from selenium.webdriver.common.by import By
    print("✓ selenium OK")
except ImportError as e:
    print(f"✗ selenium エラー: {e}")
    print("→ 実行: pip3 install selenium")

# ── ホットペッパー HTML 確認 ──────────────────────────────────────
print()
print("=" * 60)
print("② ホットペッパー HTML 確認")
print("=" * 60)

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9",
    "Referer": "https://www.hotpepper.jp/",
}

# 梅田周辺で検索
url = "https://www.hotpepper.jp/SS010101/?SVC=0&keyword=%E6%A2%85%E7%94%B0&budget=B008&PG=1"
print(f"URL: {url}")
resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
print(f"ステータスコード: {resp.status_code}")
print(f"最終URL: {resp.url}")
print(f"レスポンスサイズ: {len(resp.text)} 文字")

soup = BeautifulSoup(resp.text, "lxml")
print(f"ページタイトル: {soup.title.string if soup.title else 'なし'}")

# 様々なセレクタを試す
selectors_to_try = [
    "div.shopDetailInfo",
    "section.shopDetail",
    "div.rstCassette",
    "li.shopListItem",
    "div.cassetteRestaurant",
    "div.list-cassette",
    "article.list-cassette__item",
    "div.cst",
    "li.cst",
    "div.resListItem",
    "div.shopLineArea",
    "div[class*='shop']",
    "div[class*='restaurant']",
    "div[class*='list']",
]

print("\n--- セレクタ検索結果 ---")
found = False
for sel in selectors_to_try:
    items = soup.select(sel)
    if items:
        print(f"✓ {sel}: {len(items)}件")
        found = True

if not found:
    print("✗ 既知のセレクタでは見つかりませんでした")
    print("\n--- HTMLの最初の500文字 ---")
    print(resp.text[:500])
    print("\n--- bodyタグ内のclass一覧（上位20個）---")
    classes = set()
    for tag in soup.find_all(class_=True)[:100]:
        for c in tag.get("class", []):
            classes.add(c)
    for c in sorted(classes)[:20]:
        print(f"  .{c}")

# ── 食べログ URL 確認 ─────────────────────────────────────────────
print()
print("=" * 60)
print("③ 食べログ URL 確認（HTMLのみ、Seleniumなし）")
print("=" * 60)

url_tb = ("https://tabelog.com/osaka/rstLst/?"
          "vs=1&lat=34.7025&lon=135.4959&dist=0.5&price_max=6000&p=1")
print(f"URL: {url_tb}")
try:
    resp_tb = requests.get(url_tb, headers=headers, timeout=20, allow_redirects=True)
    print(f"ステータスコード: {resp_tb.status_code}")
    print(f"最終URL: {resp_tb.url}")
    soup_tb = BeautifulSoup(resp_tb.text, "lxml")
    print(f"ページタイトル: {soup_tb.title.string[:60] if soup_tb.title else 'なし'}")
    cards = soup_tb.select("div.list-rst__wrap")
    print(f"div.list-rst__wrap: {len(cards)}件")
    if len(cards) == 0:
        print("（Cloudflareでブロックされている可能性があります）")
except Exception as e:
    print(f"エラー: {e}")

print()
print("=" * 60)
print("デバッグ完了。この出力を貼り付けてください。")
print("=" * 60)

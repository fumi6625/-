"""
デバッグスクリプト v3 - ホットペッパーの正しいURLを調査
実行: python3 debug_scrapers.py
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)

# ══════════════════════════════════════════════════════════════
# ① ホットペッパー: トップページから検索フォームを解析
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("① ホットペッパー: トップページ解析")
print("=" * 60)

session.headers["Referer"] = "https://www.hotpepper.jp/"
top_resp = session.get("https://www.hotpepper.jp/", timeout=15)
soup_top = BeautifulSoup(top_resp.text, "lxml")

# 検索フォームのaction URLを調べる
print("--- 検索フォーム ---")
for form in soup_top.select("form"):
    action = form.get("action", "")
    if action and ("search" in action.lower() or "rst" in action.lower()
                   or "entrance" in action.lower() or "keyword" in action.lower()):
        print(f"  action: {action}")
        for inp in form.select("input, select"):
            print(f"    [{inp.name}] name={inp.get('name','')} value={inp.get('value','')}")

# 大阪のエリアリンクを探す
print("\n--- 大阪関連リンク ---")
for a in soup_top.select("a[href]"):
    href = a.get("href", "")
    text = a.get_text(strip=True)
    if "大阪" in text or "osaka" in href.lower() or "SA2" in href:
        print(f"  [{text[:15]}] → {href[:70]}")

# ══════════════════════════════════════════════════════════════
# ② ホットペッパー: 大阪エリアコードを試す
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("② ホットペッパー: 大阪URLを試す")
print("=" * 60)

candidates = [
    "https://www.hotpepper.jp/SA28/",
    "https://www.hotpepper.jp/SA27/",
    "https://www.hotpepper.jp/SA29/",
    "https://www.hotpepper.jp/SACG11/",
    "https://www.hotpepper.jp/SGB11/",
    "https://www.hotpepper.jp/s1011/",  # 大阪市
    "https://www.hotpepper.jp/s1012/",  # 梅田
]

working_url = None
for url in candidates:
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string[:50] if soup.title else "?"
        # 店舗カードを探す
        found = []
        for sel in ["div.cassetteRestaurant", "li.cassetteRestaurant",
                    "div.shopDetailInfo", "div.rstCassette", "article.cassetteRestaurant",
                    "div[class*='cassette']", "li[class*='restaurant']"]:
            c = soup.select(sel)
            if c:
                found.append(f"{sel}({len(c)}件)")
        status = "✓" if found else "✗"
        print(f"{status} [{r.status_code}] {url}")
        print(f"     タイトル: {title}")
        if found:
            print(f"     カード: {', '.join(found)}")
            working_url = url
    except Exception as e:
        print(f"✗ エラー: {url} → {e}")

# ══════════════════════════════════════════════════════════════
# ③ ホットペッパー: 検索フォームに「梅田」を送信
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("③ ホットペッパー: 検索フォーム送信テスト")
print("=" * 60)

# フォームのactionにPOST/GETで「梅田」を送信
search_urls = [
    "https://www.hotpepper.jp/Saccess0EntranceAction.do?sk={kw}&rsc=0&vn=1",
    "https://www.hotpepper.jp/rstSearch/?keyword={kw}",
    "https://www.hotpepper.jp/yoyaku/GourmetSearchAction.do?keyword={kw}",
    "https://www.hotpepper.jp/search/?keyword={kw}",
]
kw = quote("梅田", safe="")
for url_tpl in search_urls:
    url = url_tpl.format(kw=kw)
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string[:50] if soup.title else "?"
        found = []
        for sel in ["div.cassetteRestaurant", "li.cassetteRestaurant",
                    "div.shopDetailInfo", "div.rstCassette",
                    "div[class*='cassette']", "li[class*='restaurant']"]:
            c = soup.select(sel)
            if c:
                found.append(f"{sel}({len(c)}件)")
        status = "✓" if found else "✗"
        print(f"{status} [{r.status_code}] {url[:70]}")
        print(f"     タイトル: {title}")
        if found:
            print(f"     カード: {', '.join(found)}")
            # 最初のカードのclass一覧
            first = soup.select(found[0].split("(")[0])[0]
            all_classes = []
            for t in first.find_all(class_=True):
                for c in t.get("class", []):
                    if c not in all_classes:
                        all_classes.append(c)
            print(f"     クラス: {all_classes[:15]}")
    except Exception as e:
        print(f"✗ エラー: {url[:60]} → {e}")

# ══════════════════════════════════════════════════════════════
# ④ 食べログ: ジャンル・予算のセレクタを調査
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("④ 食べログ: ジャンル・予算のセレクタ調査")
print("=" * 60)

session.headers["Referer"] = "https://tabelog.com/"
url_tb = ("https://tabelog.com/osaka/rstLst/?"
          "vs=1&lat=34.7025&lon=135.4959&dist=0.5&price_max=6000&p=1")
resp_tb = session.get(url_tb, timeout=20)
soup_tb = BeautifulSoup(resp_tb.text, "lxml")
cards = soup_tb.select("div.list-rst__wrap")
print(f"カード数: {len(cards)}件")

if cards:
    card = cards[0]
    # 全クラスを列挙
    all_cls = []
    for tag in card.find_all(class_=True):
        for c in tag.get("class", []):
            if c not in all_cls:
                all_cls.append(c)

    # キーワードでフィルタ
    for kw in ["category", "genre", "budget", "price", "address", "seat", "area"]:
        hits = [c for c in all_cls if kw in c.lower()]
        for cls in hits:
            el = card.select_one(f".{cls}")
            if el:
                text = el.get_text(strip=True)[:40]
                print(f"  .{cls}: {text}")

    print(f"\n全クラス一覧:")
    for c in all_cls:
        print(f"  .{c}")

print()
print("=" * 60)
print("デバッグ完了。この出力を全部貼り付けてください。")
print("=" * 60)

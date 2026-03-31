"""
デバッグスクリプト v3
実行: python3 debug_scrapers.py
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── ① ホットペッパー: トップページから検索フォームのURLを調査 ──────
print("=" * 60)
print("① ホットペッパー: 正しい検索URLを調査")
print("=" * 60)

session = requests.Session()
session.headers.update(HEADERS)

# トップページを取得してフォームのaction URLを調べる
top = session.get("https://www.hotpepper.jp/", timeout=15)
soup_top = BeautifulSoup(top.text, "lxml")

# 検索フォームを探す
forms = soup_top.select("form")
print(f"フォーム数: {len(forms)}")
for f in forms[:5]:
    action = f.get("action", "")
    method = f.get("method", "")
    if action:
        print(f"  form action: {action}  method: {method}")

# ナビゲーションリンクから大阪エリアのURLを探す
osaka_links = []
for a in soup_top.select("a[href]"):
    href = a["href"]
    text = a.get_text(strip=True)
    if "大阪" in text or "osaka" in href.lower():
        osaka_links.append((text[:20], href[:60]))
if osaka_links:
    print(f"\n大阪関連リンク:")
    for text, href in osaka_links[:5]:
        print(f"  [{text}] {href}")

# 複数のURL形式を試す（大阪向け）
print("\n--- 大阪エリアURL試行 ---")
osaka_url_candidates = [
    "https://www.hotpepper.jp/SA27/",         # 大阪府コード27
    "https://www.hotpepper.jp/SA28/",
    "https://www.hotpepper.jp/SA13/",
    "https://www.hotpepper.jp/SACTG1201/",    # 梅田エリアコード
    "https://www.hotpepper.jp/SG271/",
    "https://www.hotpepper.jp/SA27/sk%E6%A2%85%E7%94%B0/",  # 大阪+梅田(URL encoded)
    "https://www.hotpepper.jp/Saccess0EntranceAction.do?sk=%E6%A2%85%E7%94%B0&sa=&rsc=0",
    "https://www.hotpepper.jp/rstSearch/?keyword=%E6%A2%85%E7%94%B0",
    "https://www.hotpepper.jp/GourmetSearch/search/?keyword=%E6%A2%85%E7%94%B0",
]

working_url = None
for url in osaka_url_candidates:
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string[:40] if soup.title else "?"
        # カードを探す
        card_count = 0
        card_sel = ""
        for sel in ["div.cassetteRestaurant", "li.cassetteRestaurant",
                    "div.shopDetailInfo", "div.rstCassette", "div[class*='cassette']",
                    "li[class*='cassette']", "article", "div.list-cassette__item"]:
            c = soup.select(sel)
            if c and len(c) > 2:
                card_count = len(c)
                card_sel = sel
                break
        status = "✓" if card_count > 0 else "✗"
        print(f"{status} [{r.status_code}] {url[:55]}")
        print(f"     タイトル: {title}  カード: {card_count}件 ({card_sel})")
        if card_count > 0 and not working_url:
            working_url = url
            print(f"  → 使えるURLが見つかりました！")
            # HTMLクラス一覧を表示
            first_card = soup.select(card_sel)[0]
            print(f"  カード内のクラス: {[t.get('class') for t in first_card.find_all(class_=True)[:5]]}")
    except Exception as e:
        print(f"✗ エラー: {url[:50]} → {e}")

# ── ② 食べログ: セレクタ詳細確認 ──────────────────────────────────
print()
print("=" * 60)
print("② 食べログ: セレクタ詳細確認")
print("=" * 60)

HEADERS["Referer"] = "https://tabelog.com/"
session.headers.update(HEADERS)

url_tb = ("https://tabelog.com/osaka/rstLst/?"
          "vs=1&lat=34.7025&lon=135.4959&dist=0.5&price_max=6000&p=1")
resp_tb = session.get(url_tb, timeout=20)
soup_tb = BeautifulSoup(resp_tb.text, "lxml")
cards = soup_tb.select("div.list-rst__wrap")
print(f"カード数: {len(cards)}件")

if cards:
    card = cards[0]
    print(f"\n最初のカードで見つかったセレクタ:")
    checks = {
        "店名":   "a.list-rst__rst-name-target",
        "ジャンル1": "span.list-rst__category-main-name",
        "ジャンル2": "p.list-rst__category",
        "ジャンル3": "span[class*='category']",
        "予算1":   "span.c-rating-v2__val--dinner",
        "予算2":   "em.list-rst__budget-dinner",
        "予算3":   "span[class*='budget']",
        "予算4":   "span[class*='price']",
        "住所1":   "p.list-rst__address",
        "住所2":   "p.list-rst__area-genre",
        "席数":    "li.list-rst__seat-count",
    }
    for label, sel in checks.items():
        el = card.select_one(sel)
        if el:
            print(f"  ✓ {label} [{sel}]: {el.get_text(strip=True)[:30]}")
        else:
            print(f"  ✗ {label} [{sel}]")

    # カード内の全クラスを表示
    print(f"\nカード内クラス一覧（参考）:")
    classes = []
    for tag in card.find_all(class_=True):
        for c in tag.get("class", []):
            if c not in classes:
                classes.append(c)
    for c in classes[:30]:
        print(f"  .{c}")

print()
print("=" * 60)
print("デバッグ完了。この出力をすべて貼り付けてください。")
print("=" * 60)

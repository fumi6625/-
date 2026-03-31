# 検索対象駅（名称: (緯度, 経度)）
STATIONS = {
    "梅田駅":       (34.7025, 135.4959),
    "本町駅":       (34.6839, 135.5002),
    "高井田中央駅": (34.6733, 135.5744),
    "心斎橋駅":     (34.6745, 135.5009),
    "谷町四丁目駅": (34.6867, 135.5139),
    "森之宮駅":     (34.6781, 135.5323),
    "淀屋橋駅":     (34.6926, 135.5009),
    "難波駅":       (34.6655, 135.5018),
    "阿波座駅":     (34.6833, 135.4919),
}

# 検索条件
SEARCH_RADIUS_KM = 0.5      # 500m
MAX_BUDGET = 6000           # 予算上限（円）

# ──────────────────────────────────────────
# ホットペッパー: 駅 → エリアコード マッピング
# SA23 = 大阪、Y*** = 大阪内エリアコード
# ──────────────────────────────────────────
HP_STATION_AREA = {
    "梅田駅":       "SA23/Y300",   # 梅田エリア
    "淀屋橋駅":     "SA23/Y300",   # 梅田エリア（淀屋橋含む）
    "本町駅":       "SA23/Y300",   # 梅田エリア（本町含む）
    "阿波座駅":     "SA23/Y300",   # 梅田エリア（阿波座含む）
    "心斎橋駅":     "SA23/Y315",   # 難波エリア（心斎橋含む）
    "難波駅":       "SA23/Y315",   # 難波エリア
    "谷町四丁目駅": "SA23/Y310",   # 京橋・城東エリア
    "森之宮駅":     "SA23/Y310",   # 京橋・城東エリア
    "高井田中央駅": "SA23",        # 大阪全体（東大阪のため広域）
}

# リクエスト設定
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

LIST_SLEEP_MIN = 1.5
LIST_SLEEP_MAX = 3.5
DETAIL_SLEEP_MIN = 2.0
DETAIL_SLEEP_MAX = 5.0

# 出力ファイル
OUTPUT_FILE = "restaurants.xlsm"
VBA_PROJECT_BIN = "output/vba_project.bin"

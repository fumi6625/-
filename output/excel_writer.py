"""
Excel 出力モジュール

- xlsxwriter で .xlsm（VBAマクロ付き）を生成
- vba_project.bin が存在しない場合は .xlsx（オートフィルター付き）で出力
"""
import os
import logging
from typing import TYPE_CHECKING

import xlsxwriter

if TYPE_CHECKING:
    from models.restaurant import Restaurant

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────────────────────────
HEADERS = [
    "店名", "最寄駅", "住所", "食べ物のジャンル",
    "コース料理", "飲み放題", "席数", "個室", "大体の予算（円）", "リンク",
]
COL_WIDTHS = [30, 12, 40, 18, 10, 10, 8, 8, 14, 55]

# ヘッダー行の色設定
HEADER_BG = {
    "食べログ":           "#C55A11",   # 食べログカラー（オレンジ系）
    "ホットペッパーグルメ": "#C00000",   # ホットペッパーカラー（赤系）
}
DEFAULT_HEADER_BG = "#4472C4"

# 予算別セル色（背景）
BUDGET_COLORS = [
    (0,    2999,  "#E2EFDA"),  # 〜2999円: 薄緑
    (3000, 4999,  "#FFEB9C"),  # 3000〜4999円: 薄黄
    (5000, 5999,  "#FFCC99"),  # 5000〜5999円: 薄オレンジ
]

# 駅並び順（sort用）
STATION_ORDER = [
    "梅田駅", "淀屋橋駅", "本町駅", "阿波座駅",
    "心斎橋駅", "難波駅", "谷町四丁目駅", "森之宮駅", "高井田中央駅",
]


def write_excel(
    tabelog_rows: "list[Restaurant]",
    hotpepper_rows: "list[Restaurant]",
    output_path: str = "restaurants.xlsm",
    vba_bin_path: str = "output/vba_project.bin",
) -> None:
    """
    レストランデータを Excel ファイルに書き出す。
    vba_bin_path が存在する場合は .xlsm (VBAマクロ付き)、
    存在しない場合は .xlsx (オートフィルター付き) で出力する。
    """
    has_vba = os.path.exists(vba_bin_path)
    if not has_vba:
        if output_path.endswith(".xlsm"):
            output_path = output_path.replace(".xlsm", ".xlsx")
        logger.warning(
            f"vba_project.bin が見つかりません。"
            f"オートフィルター付き .xlsx として出力します → {output_path}"
        )
    else:
        logger.info(f"VBAマクロ付き .xlsm として出力します → {output_path}")

    wb = xlsxwriter.Workbook(output_path, {"strings_to_urls": False})
    if has_vba:
        wb.add_vba_project(vba_bin_path)

    data_sheets = [
        ("食べログ", tabelog_rows),
        ("ホットペッパーグルメ", hotpepper_rows),
    ]

    for sheet_name, rows in data_sheets:
        sorted_rows = _sort_rows(rows)
        _write_data_sheet(wb, sheet_name, sorted_rows)

    _write_search_sheet(wb, has_vba)

    wb.close()
    logger.info(f"出力完了: {output_path}  "
                f"(食べログ {len(tabelog_rows)}件 / ホットペッパー {len(hotpepper_rows)}件)")


# ──────────────────────────────────────────────────────────────────
# データシート
# ──────────────────────────────────────────────────────────────────

def _write_data_sheet(wb: xlsxwriter.Workbook, sheet_name: str,
                      rows: "list[Restaurant]") -> None:
    ws = wb.add_worksheet(sheet_name)
    ws.set_zoom(90)

    header_bg = HEADER_BG.get(sheet_name, DEFAULT_HEADER_BG)
    fmt_header = wb.add_format({
        "bold": True, "bg_color": header_bg, "font_color": "white",
        "border": 1, "align": "center", "valign": "vcenter",
        "text_wrap": True,
    })
    fmt_cell = wb.add_format({
        "border": 1, "valign": "top", "text_wrap": True,
    })
    fmt_num = wb.add_format({
        "border": 1, "valign": "top", "num_format": "#,##0",
    })
    fmt_url = wb.add_format({
        "border": 1, "valign": "top", "font_color": "#0563C1", "underline": True,
    })

    # 予算別セル書式
    budget_fmts = []
    for _, _, bg in BUDGET_COLORS:
        budget_fmts.append(wb.add_format({
            "border": 1, "valign": "top", "num_format": "#,##0", "bg_color": bg,
        }))

    # ヘッダー行
    ws.set_row(0, 30)
    for col, (h, w) in enumerate(zip(HEADERS, COL_WIDTHS)):
        ws.write(0, col, h, fmt_header)
        ws.set_column(col, col, w)
    ws.freeze_panes(1, 0)

    # オートフィルター（VBAなし版でも機能する）
    if rows:
        ws.autofilter(0, 0, len(rows), len(HEADERS) - 1)

    # データ行
    for row_idx, r in enumerate(rows, start=1):
        data = r.to_row()
        for col, val in enumerate(data):
            if col == 6:  # 席数（数値）
                if isinstance(val, int) and val > 0:
                    ws.write_number(row_idx, col, val, fmt_num)
                else:
                    ws.write_blank(row_idx, col, fmt_cell)
            elif col == 8:  # 予算（数値・色付き）
                if isinstance(val, int) and val > 0:
                    bfmt = _get_budget_fmt(val, budget_fmts, fmt_num)
                    ws.write_number(row_idx, col, val, bfmt)
                else:
                    ws.write_blank(row_idx, col, fmt_cell)
            elif col == 9:  # リンク
                if val and isinstance(val, str) and val.startswith("http"):
                    ws.write_url(row_idx, col, val, fmt_url, "リンク")
                else:
                    ws.write(row_idx, col, val or "", fmt_cell)
            else:
                ws.write(row_idx, col, val if val is not None else "", fmt_cell)


def _get_budget_fmt(budget: int, budget_fmts: list, default_fmt) -> xlsxwriter.format.Format:
    for i, (lo, hi, _) in enumerate(BUDGET_COLORS):
        if lo <= budget <= hi:
            return budget_fmts[i]
    return default_fmt


# ──────────────────────────────────────────────────────────────────
# 検索条件シート
# ──────────────────────────────────────────────────────────────────

def _write_search_sheet(wb: xlsxwriter.Workbook, has_vba: bool) -> None:
    ws = wb.add_worksheet("検索条件")
    ws.set_zoom(110)
    ws.set_column("A:A", 20)
    ws.set_column("B:B", 25)

    fmt_title = wb.add_format({
        "bold": True, "font_size": 14, "font_color": "#1F497D",
        "bottom": 2, "bottom_color": "#1F497D",
    })
    fmt_label = wb.add_format({
        "bold": True, "bg_color": "#D6E4F0", "border": 1,
        "valign": "vcenter", "align": "right", "indent": 1,
    })
    fmt_input = wb.add_format({
        "border": 2, "border_color": "#2E75B6",
        "bg_color": "#FFFFFF", "valign": "vcenter",
    })
    fmt_note = wb.add_format({
        "italic": True, "font_color": "#7F7F7F", "font_size": 9,
    })
    fmt_budget_label = wb.add_format({
        "bold": True, "bg_color": "#D6E4F0", "border": 1,
        "valign": "vcenter", "align": "right", "indent": 1,
    })
    fmt_section = wb.add_format({
        "bold": True, "font_size": 11, "bg_color": "#BDD7EE",
        "border": 1, "valign": "vcenter",
    })

    # タイトル
    ws.merge_range("A1:C1", "レストラン検索条件入力", fmt_title)
    ws.set_row(0, 28)

    # ─── 検索条件入力欄 ───
    ws.write("A3", "── 検索条件 ──", fmt_section)
    ws.set_row(2, 22)

    conditions = [
        ("A4", "B4", "ジャンル",    "例: 居酒屋、焼肉、和食 など（部分一致）"),
        ("A5", "B5", "最寄駅",      "例: 梅田駅、心斎橋駅 など（部分一致）"),
        ("A6", "B6", "予算上限（円）", "例: 3000, 4000, 5000, 6000（0=上限なし）"),
        ("A7", "B7", "最低席数",    "例: 30（0=指定なし）"),
    ]
    for a_cell, b_cell, label, note in conditions:
        ws.write(a_cell, label, fmt_label)
        ws.write(b_cell, "", fmt_input)

    # 備考
    ws.write("C4", "例: 居酒屋、焼肉、和食 など（部分一致）", fmt_note)
    ws.write("C5", "例: 梅田駅、心斎橋駅 など（部分一致）", fmt_note)
    ws.write("C6", "例: 3000, 4000, 5000, 6000（0=上限なし）", fmt_note)
    ws.write("C7", "例: 30（0=指定なし）", fmt_note)

    # Named ranges (VBA マクロから参照)
    wb.define_name("SearchGenre",   "検索条件!$B$4")
    wb.define_name("SearchStation", "検索条件!$B$5")
    wb.define_name("SearchBudget",  "検索条件!$B$6")
    wb.define_name("SearchSeats",   "検索条件!$B$7")

    # ─── 操作説明 ───
    ws.write("A9", "── 操作方法 ──", fmt_section)
    ws.set_row(8, 22)

    if has_vba:
        instructions = [
            "① 上記の入力欄に検索条件を入力してください。",
            "② 「開発」タブ → 「マクロ」→ SearchRestaurants を実行、",
            "   または Alt+F8 キーでマクロダイアログを開いて実行します。",
            "③ 「食べログ」「ホットペッパーグルメ」シートで条件に一致した行のみ表示されます。",
            "④ リセットは ResetSearch マクロを同様に実行してください。",
            "",
            "【注意】マクロ実行には Excel のマクロ設定を「有効」にしてください。",
            "  セキュリティ設定: ファイル → オプション → セキュリティセンター → マクロの設定",
        ]
    else:
        instructions = [
            "【VBAマクロなし版 - オートフィルター使用方法】",
            "① 「食べログ」または「ホットペッパーグルメ」シートを開きます。",
            "② 各列ヘッダーのドロップダウン矢印（▼）をクリックします。",
            "③ 「テキストフィルター」または「数値フィルター」で条件を設定します。",
            "   ・ジャンル列: テキストフィルター → 指定の値を含む",
            "   ・最寄駅列:   テキストフィルター → 指定の値を含む",
            "   ・予算列:     数値フィルター → 指定の値以下",
            "   ・席数列:     数値フィルター → 指定の値以上",
            "④ 複数条件はそれぞれの列で設定すると AND 検索になります。",
            "",
            "VBAマクロを追加するには generate_vba.py を実行してください。",
        ]

    fmt_instr = wb.add_format({"valign": "top", "text_wrap": True})
    for i, line in enumerate(instructions):
        ws.write(9 + i, 0, line, fmt_instr)
        ws.merge_range(9 + i, 0, 9 + i, 3, line, fmt_instr)
        ws.set_row(9 + i, 18)

    ws.set_column("C:C", 55)


# ──────────────────────────────────────────────────────────────────
# ソート
# ──────────────────────────────────────────────────────────────────

def _sort_rows(rows: "list[Restaurant]") -> "list[Restaurant]":
    """駅順 → 予算昇順 でソート"""
    def sort_key(r):
        try:
            station_idx = STATION_ORDER.index(r.station)
        except ValueError:
            station_idx = len(STATION_ORDER)
        return (station_idx, r.budget or 99999)
    return sorted(rows, key=sort_key)

"""
Google ビジネス専用 Excel 出力モジュール
"""
import xlsxwriter
import logging

logger = logging.getLogger(__name__)

HEADERS = ["店名", "最寄駅", "住所", "ジャンル", "コースあり", "飲み放題",
           "席数", "個室", "予算(円)", "Google Maps URL"]

COL_BUDGET = 8   # I列（0始まり）


def write_excel_google(rows, output_path: str = "restaurants_google.xlsx"):
    wb = xlsxwriter.Workbook(output_path)

    # ─── フォーマット定義 ───────────────────────────
    hdr_fmt = wb.add_format({
        "bold": True, "bg_color": "#4472C4", "font_color": "white",
        "border": 1, "align": "center", "valign": "vcenter",
    })
    url_fmt  = wb.add_format({"font_color": "#0563C1", "underline": True})
    green_fmt  = wb.add_format({"bg_color": "#C6EFCE"})   # ≤2999
    yellow_fmt = wb.add_format({"bg_color": "#FFEB9C"})   # 3000-4999
    orange_fmt = wb.add_format({"bg_color": "#FFCC99"})   # 5000-5999

    # ─── Googleビジネス シート ────────────────────────
    ws = wb.add_worksheet("Googleビジネス")
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, 0, len(HEADERS) - 1)
    ws.set_column(0, 0, 28)   # 店名
    ws.set_column(1, 1, 14)   # 最寄駅
    ws.set_column(2, 2, 30)   # 住所
    ws.set_column(3, 3, 16)   # ジャンル
    ws.set_column(4, 6, 10)   # コース・飲み放題・席数
    ws.set_column(7, 7, 8)    # 個室
    ws.set_column(COL_BUDGET, COL_BUDGET, 12)  # 予算
    ws.set_column(len(HEADERS) - 1, len(HEADERS) - 1, 50)  # URL

    for col, h in enumerate(HEADERS):
        ws.write(0, col, h, hdr_fmt)

    for row_idx, r in enumerate(rows, start=1):
        data = r.to_row()
        for col, val in enumerate(data):
            if col == len(HEADERS) - 1 and val:   # URL列
                ws.write_url(row_idx, col, val, url_fmt, val)
            elif col == COL_BUDGET and isinstance(val, int) and val > 0:
                fmt = (green_fmt if val <= 2999 else
                       yellow_fmt if val <= 4999 else
                       orange_fmt if val <= 5999 else None)
                ws.write(row_idx, col, val, fmt)
            else:
                ws.write(row_idx, col, val)

    # ─── 検索条件シート ──────────────────────────────
    cfg = wb.add_worksheet("検索条件")
    cfg_title = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
    cfg_input = wb.add_format({"border": 1, "bg_color": "#FFFFC0"})
    cfg.set_column(0, 0, 16)
    cfg.set_column(1, 1, 20)

    labels = [
        ("対象エリア", "大阪 9駅（500m圏内）"),
        ("予算上限", "¥6,000"),
        ("データ件数", len(rows)),
        ("データソース", "Google ビジネス（Google Maps）"),
    ]
    for i, (label, val) in enumerate(labels):
        cfg.write(i + 3, 0, label, cfg_title)
        cfg.write(i + 3, 1, val, cfg_input)

    wb.close()
    logger.info(f"出力完了: {output_path}  (Googleビジネス {len(rows)}件)")

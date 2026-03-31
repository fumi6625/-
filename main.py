"""
大阪レストラン検索リスト作成ツール

食べログ・ホットペッパーグルメから大阪4駅周辺のレストランをスクレイピングし、
VBAマクロ付き Excel ファイルに出力します。

使い方:
    python main.py              # フル実行
    python main.py --dry-run    # 各サイト各駅1ページのみ（動作確認用）
    python main.py --no-tabelog # 食べログをスキップ
    python main.py --no-hotpepper # ホットペッパーをスキップ
"""
import argparse
import logging
import os
import sys

from config.settings import STATIONS, OUTPUT_FILE, VBA_PROJECT_BIN
from scrapers.tabelog_scraper import TabelogScraper
from scrapers.hotpepper_scraper import HotPepperScraper
from scrapers.base_scraper import BaseScraper
from output.excel_writer import write_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraping.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="大阪レストラン検索リスト作成ツール"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="各駅・各サイトで1〜2ページのみ取得（テスト用）",
    )
    parser.add_argument(
        "--no-tabelog", action="store_true",
        help="食べログのスクレイピングをスキップ",
    )
    parser.add_argument(
        "--no-hotpepper", action="store_true",
        help="ホットペッパーグルメのスクレイピングをスキップ",
    )
    parser.add_argument(
        "--output", default=OUTPUT_FILE,
        help=f"出力ファイル名（デフォルト: {OUTPUT_FILE}）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # VBAバイナリが存在しない場合は自動生成を試みる
    if not os.path.exists(VBA_PROJECT_BIN):
        logger.info("vba_project.bin が見つかりません。自動生成を試みます...")
        try:
            from generate_vba import main as gen_vba
            gen_vba()
        except Exception as e:
            logger.warning(f"VBAバイナリ生成に失敗しました: {e}")
            logger.warning("xlsx（オートフィルター付き）で出力します。")

    tabelog_results = []
    hotpepper_results = []

    # ─── 食べログ ───────────────────────────────────────────────────
    if not args.no_tabelog:
        logger.info("=" * 60)
        logger.info("食べログ スクレイピング開始")
        logger.info("=" * 60)
        tabelog_scraper = TabelogScraper(dry_run=args.dry_run)
        try:
            for station_name, (lat, lon) in STATIONS.items():
                logger.info(f"▶ {station_name} を検索中...")
                results = tabelog_scraper.search(station_name, lat, lon)
                logger.info(f"  {station_name}: {len(results)}件取得")
                tabelog_results.extend(results)
        finally:
            tabelog_scraper.close()

        tabelog_results = BaseScraper.dedup(tabelog_results)
        logger.info(f"食べログ 重複排除後: {len(tabelog_results)}件")
    else:
        logger.info("食べログ スキップ")

    # ─── ホットペッパーグルメ ────────────────────────────────────────
    if not args.no_hotpepper:
        logger.info("=" * 60)
        logger.info("ホットペッパーグルメ スクレイピング開始")
        logger.info("=" * 60)
        hotpepper_scraper = HotPepperScraper(dry_run=args.dry_run)
        for station_name, (lat, lon) in STATIONS.items():
            logger.info(f"▶ {station_name} を検索中...")
            results = hotpepper_scraper.search(station_name, lat, lon)
            logger.info(f"  {station_name}: {len(results)}件取得")
            hotpepper_results.extend(results)

        hotpepper_results = BaseScraper.dedup(hotpepper_results)
        logger.info(f"ホットペッパー 重複排除後: {len(hotpepper_results)}件")
    else:
        logger.info("ホットペッパーグルメ スキップ")

    # ─── Excel 出力 ─────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Excel ファイル生成中...")
    write_excel(
        tabelog_rows=tabelog_results,
        hotpepper_rows=hotpepper_results,
        output_path=args.output,
        vba_bin_path=VBA_PROJECT_BIN,
    )
    logger.info(f"完了！  {args.output}")
    logger.info(f"  食べログ:           {len(tabelog_results)} 件")
    logger.info(f"  ホットペッパーグルメ: {len(hotpepper_results)} 件")


if __name__ == "__main__":
    main()

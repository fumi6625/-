"""
Google ビジネス レストラン検索リスト作成ツール

Google Maps から大阪9駅周辺のレストランをスクレイピングし、
Excel ファイルに出力します。

使い方:
    python main_google.py              # フル実行
    python main_google.py --dry-run    # 各駅スクロール少なめ（動作確認用）
    python main_google.py --output 出力ファイル名.xlsx
"""
import argparse
import logging
import sys

from config.settings import STATIONS, VBA_PROJECT_BIN
from scrapers.google_business_scraper import GoogleBusinessScraper
from scrapers.base_scraper import BaseScraper
from output.excel_writer_google import write_excel_google

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraping_google.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Google ビジネス レストラン検索リスト作成ツール")
    parser.add_argument("--dry-run", action="store_true", help="スクロール回数を減らしてテスト実行")
    parser.add_argument("--output", default="restaurants_google.xlsx", help="出力ファイル名")
    return parser.parse_args()


def main():
    args = parse_args()
    scraper = GoogleBusinessScraper(dry_run=args.dry_run)
    all_results = []

    try:
        logger.info("=" * 60)
        logger.info("Google ビジネス スクレイピング開始")
        logger.info("=" * 60)

        for station_name, (lat, lon) in STATIONS.items():
            logger.info(f"▶ {station_name} を検索中...")
            results = scraper.search(station_name, lat, lon)
            logger.info(f"  {station_name}: {len(results)}件取得")
            all_results.extend(results)
            scraper._list_sleep()

    finally:
        scraper.close()

    all_results = BaseScraper.dedup(all_results)
    logger.info(f"重複排除後: {len(all_results)}件")

    logger.info("Excel ファイル生成中...")
    write_excel_google(all_results, args.output)
    logger.info(f"完了！ {args.output}  ({len(all_results)}件)")


if __name__ == "__main__":
    main()

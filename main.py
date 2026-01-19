import logging
import time
import datetime
import os
from dataclasses import dataclass

import pyrallis

from spider import PaiAppFetcher, PaiAppParser, PaiAppSaver


@dataclass
class RunConfig:
    months: int = 12
    output_dir: str = "data"
    page_size: int = 20
    log_file: str = "spider.log"


def setup_logging(path: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(path)],
    )


@pyrallis.wrap()
def main(args: RunConfig):
    assert args.months > 0, "时间范围不合法"
    assert args.page_size > 0, "分页大小不合法"

    end = datetime.datetime.now()
    start = end - datetime.timedelta(args.months * 30)

    if os.path.exists(args.output_dir) is False:
        os.makedirs(args.output_dir)

    setup_logging(args.log_file)
    logging.info("启动sspai爬虫...")

    fetcher = PaiAppFetcher()
    parser = PaiAppParser()
    saver = PaiAppSaver(output_dir=args.output_dir)

    offset = 0
    keep_going = True
    processed_count = 0

    while keep_going:
        logging.info(f"抓取文章列表，offset={offset}...")
        articles = fetcher.fetch_feed_articles(limit=args.page_size, offset=offset)

        if not articles:
            logging.info("没有更多文章，停止抓取")
            break

        for article in articles:
            # Check date
            released_time = article.get("released_time", 0)
            article_date = datetime.datetime.fromtimestamp(released_time)

            if article_date < start or article_date > end:
                logging.info(f"文章发表时间 {article_date} 超出时间范围")
                keep_going = False
                break

            # Filter by title
            title = article.get("title", "")
            if "派评" in title and "近期值得关注" in title:
                logging.info(f"发现目标文章: {title} ({article_date})")

                # Fetch Detail
                detail = fetcher.get_article_detail(article["id"])
                if not detail:
                    continue
                # Parse
                apps = parser.parse_article(detail, detail.get("body", ""))
                logging.info(f"文章中发现 {len(apps)} 个 app 推荐")

                for app in apps:
                    saver.save_app(app)
                    processed_count += 1

                # Be nice to the server
                time.sleep(1)

        offset += args.page_size
        time.sleep(1)  # Sleep between pages

    logging.info(f"完成。处理了 {processed_count} 个 app")


if __name__ == "__main__":
    main()

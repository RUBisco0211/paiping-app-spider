import datetime
import json
import logging
import os
import time
from dataclasses import asdict, dataclass

from pyrallis import argparsing

from spider import PaiAppParser, PaiAppSaver, PaiArticleFetcher


@dataclass
class RunConfig:
    months: int = 12
    output_dir: str = "data"
    page_size: int = 20
    log_file: str = "spider.log"
    sleep_time: int = 1


def setup_logging(path: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(path)],
    )


def main(args: RunConfig):
    if not args.months > 0:
        logging.error(f"main: 月范围 {args.months} 不合法")
        return
    if not args.page_size > 0:
        logging.error(f"main: 分页大小 {args.page_size} 不合法")
        return

    end = datetime.datetime.now()
    start = end - datetime.timedelta(args.months * 30)

    if os.path.exists(args.output_dir) is False:
        os.makedirs(args.output_dir)

    final_cfg = {
        **asdict(args),
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
    }

    setup_logging(args.log_file)
    logging.info("main: 启动sspai爬虫...")
    logging.info(f"main: 运行配置: {json.dumps(final_cfg)}")

    fetcher = PaiArticleFetcher()
    parser = PaiAppParser()
    saver = PaiAppSaver(output_dir=args.output_dir)

    offset = 0
    keep_going = True
    processed_count = 0

    while keep_going:
        articles = fetcher.fetch_feed_articles(limit=args.page_size, offset=offset)

        for article in articles:
            released_time = article.get("released_time", 0)
            article_date = datetime.datetime.fromtimestamp(released_time)

            if article_date < start or article_date > end:
                logging.info(
                    f"main: 文章发布时间 {article_date} 超出时间范围, 结束文章抓取"
                )
                keep_going = False
                break

            title = str(article.get("title", ""))
            aid = int(article["id"])
            if "派评" in title and "近期值得关注" in title:
                logging.info(f"main: 抓取目标文章: {aid} {title} ({article_date})")

                detail = fetcher.fetch_article_detail(aid)
                app_count = 0
                for app in parser.parse_apps(detail):
                    saver.save_app(app)
                    app_count += 1
                    processed_count += 1
                logging.info(f"main: 文章中发现 {app_count} 个 app 推荐")

                time.sleep(args.sleep_time)

        offset += args.page_size
        time.sleep(args.sleep_time)

    logging.info(f"完成. 处理了 {processed_count} 个 app")


if __name__ == "__main__":
    cfg = argparsing.parse(config_class=RunConfig)
    main(cfg)

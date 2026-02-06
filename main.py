import datetime as dt
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass

from pyrallis import argparsing

from spider import PaiAppParser, PaiAppSaver, PaiArticleFetcher
from spider.util import date_format


@dataclass
class RunConfig:
    months: int = 0
    update: bool = False
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


def get_latest_local_date(output_dir: str) -> dt.datetime | None:
    """获取最新文章的日期，如果不存在返回 None"""
    if not os.path.exists(output_dir):
        return None

    date_dirs = [
        d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))
    ]
    if not date_dirs:
        return None
    valid_dates = [dt.datetime.strptime(d, "%Y-%m-%d") for d in date_dirs]
    return max(valid_dates) if valid_dates else None


def calculate_time_range(
    args: RunConfig,
) -> tuple[dt.datetime, dt.datetime]:
    latest_local_date = get_latest_local_date(args.output_dir)

    if not latest_local_date:
        # 本地没有文章, 检查 months 参数
        logging.info("main: 本地没有已抓取文章, 使用 months 参数抓取")
        if args.update:
            logging.warning("main: 直接抓取模式下 update 参数无效")
        if args.months <= 0:
            logging.error(f"main: months={args.months} 不合法")
            sys.exit(0)

        end = dt.datetime.now()
        start = end - dt.timedelta(days=30 * args.months)
        return (start, end)

    # 本地已有文章, 优先使用 update 参数
    if args.update:
        # update 模式
        logging.info("main: 本地已有文章, 使用同步模式抓取新文章")
        if args.months > 0:
            logging.warning("main: 同步模式下 months 参数无效")

        start = latest_local_date + dt.timedelta(days=1)
        end = dt.datetime.now()
        return (start, end)

    # 本地已有文章, 但使用 months 参数抓取
    if args.months <= 0:
        logging.error(f"main: months={args.months} 不合法")
        sys.exit(0)

    end = dt.datetime.now()
    months_start = end - dt.timedelta(days=30 * args.months if args.months else 0)
    if latest_local_date >= months_start:
        logging.warn(
            f"main: 本地 {date_format(months_start)} 至 {date_format(latest_local_date)} 的文章将被覆盖"
        )
    return (months_start, end)


def main(args: RunConfig):
    setup_logging(args.log_file)

    if os.path.exists(args.output_dir) is False:
        os.makedirs(args.output_dir)

    if not args.page_size > 0:
        logging.error(f"main: 分页大小 {args.page_size} 不合法")
        return

    # 计算时间范围
    start, end = calculate_time_range(args)

    final_cfg = {
        **asdict(args),
        "start": date_format(start),
        "end": date_format(end),
    }

    setup_logging(args.log_file)
    logging.info("main: 启动sspai爬虫...")

    logging.info(f"main: 详细配置: {json.dumps(final_cfg)}")

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
            article_date = dt.datetime.fromtimestamp(released_time)

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
                processed_count += app_count
                logging.info(f"main: 文章中发现 {app_count} 个 app 推荐")

                time.sleep(args.sleep_time)

        offset += args.page_size
        time.sleep(args.sleep_time)

    logging.info(f"完成. 处理了 {processed_count} 个 app")


if __name__ == "__main__":
    cfg = argparsing.parse(config_class=RunConfig)
    main(cfg)

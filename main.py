import asyncio
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass

import aiohttp
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
    article_concurrency: int = 8
    image_concurrency: int = 16
    request_timeout: int = 15
    max_retries: int = 3
    retry_base_delay: float = 0.5


def setup_logging(path: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(path)],
    )


def get_latest_local_date(output_dir: str) -> dt.datetime | None:
    """获取本地最新文章的日期，如果不存在返回 None"""
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
        logging.warning(
            f"main: 本地 {date_format(months_start)} 至 {date_format(latest_local_date)} 的文章将被覆盖"
        )
    return (months_start, end)


async def async_main(args: RunConfig):
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

    logging.info("main: 启动sspai爬虫...")

    logging.info(f"main: 详细配置: {json.dumps(final_cfg)}")

    fetcher = PaiArticleFetcher(
        request_timeout=args.request_timeout,
        max_retries=args.max_retries,
        retry_base_delay=args.retry_base_delay,
    )
    parser = PaiAppParser()
    saver = PaiAppSaver(output_dir=args.output_dir)

    article_semaphore = asyncio.Semaphore(args.article_concurrency)
    image_semaphore = asyncio.Semaphore(args.image_concurrency)

    offset = 0
    keep_going = True
    article_tasks: list[asyncio.Task[tuple[int, int, int, bool]]] = []
    stats = {
        "articles_scanned": 0,
        "articles_matched": 0,
        "articles_succeeded": 0,
        "articles_failed": 0,
        "images_succeeded": 0,
        "images_failed": 0,
    }

    async with aiohttp.ClientSession(headers=PaiArticleFetcher.HEADERS) as image_session:
        await fetcher.start()
        try:
            while keep_going:
                articles = await fetcher.fetch_feed_articles(
                    limit=args.page_size, offset=offset
                )
                if not articles:
                    logging.info("main: 没有更多文章，结束抓取")
                    break

                for article in articles:
                    stats["articles_scanned"] += 1
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
                        stats["articles_matched"] += 1
                        logging.info(f"main: 抓取目标文章: {aid} {title} ({article_date})")
                        article_tasks.append(
                            asyncio.create_task(
                                process_article(
                                    aid=aid,
                                    fetcher=fetcher,
                                    parser=parser,
                                    saver=saver,
                                    article_semaphore=article_semaphore,
                                    image_semaphore=image_semaphore,
                                    image_session=image_session,
                                    request_timeout=args.request_timeout,
                                )
                            )
                        )

                offset += args.page_size
                if keep_going and args.sleep_time > 0:
                    await asyncio.sleep(args.sleep_time)

            if article_tasks:
                results = await asyncio.gather(*article_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        stats["articles_failed"] += 1
                        logging.error(f"main: 文章任务异常: {result}")
                        continue

                    app_count, img_success, img_failed, ok = result
                    if ok:
                        stats["articles_succeeded"] += 1
                    else:
                        stats["articles_failed"] += 1
                    stats["images_succeeded"] += img_success
                    stats["images_failed"] += img_failed
                    logging.info(f"main: 文章中发现 {app_count} 个 app 推荐")
        finally:
            await fetcher.close()

    logging.info(f"完成. 统计: {json.dumps(stats, ensure_ascii=False)}")


async def process_article(
    aid: int,
    fetcher: PaiArticleFetcher,
    parser: PaiAppParser,
    saver: PaiAppSaver,
    article_semaphore: asyncio.Semaphore,
    image_semaphore: asyncio.Semaphore,
    image_session: aiohttp.ClientSession,
    request_timeout: int,
) -> tuple[int, int, int, bool]:
    async with article_semaphore:
        detail = await fetcher.fetch_article_detail(aid)
        if detail is None:
            logging.error(f"main: 获取文章详情失败 article_id={aid}")
            return (0, 0, 0, False)

        try:
            apps = list(parser.parse_apps(detail))
        except Exception as e:
            logging.error(f"main: 解析文章失败 article_id={aid} error={e}")
            return (0, 0, 0, False)

        if not apps:
            return (0, 0, 0, True)

        save_tasks = [
            asyncio.create_task(
                saver.save_app_async(
                    app_data=app,
                    session=image_session,
                    image_semaphore=image_semaphore,
                    timeout=request_timeout,
                )
            )
            for app in apps
        ]
        save_results = await asyncio.gather(*save_tasks, return_exceptions=True)
        img_success = 0
        img_failed = 0
        ok = True
        for save_result in save_results:
            if isinstance(save_result, Exception):
                ok = False
                continue
            success, failed = save_result
            img_success += success
            img_failed += failed
        return (len(apps), img_success, img_failed, ok)


if __name__ == "__main__":
    cfg = argparsing.parse(config_class=RunConfig)
    asyncio.run(async_main(cfg))

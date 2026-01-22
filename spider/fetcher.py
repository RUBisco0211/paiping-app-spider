import logging
from typing import Any

import requests


class PaiArticleFetcher:
    BASE_URL = "https://sspai.com/api/v1"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://sspai.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_feed_articles(self, limit=20, offset=0) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/article/index/page/get"
        params = {
            "limit": limit,
            "offset": offset,
            "created_at": 0,
        }

        logging.info(f"Fetcher: 抓取文章列表, offset={offset} limit={limit}")
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            if data.get("error") == 0:
                return data.get("data", [])
            else:
                raise Exception("服务错误")
        except Exception as e:
            logging.error(f"Fetcher: 抓取失败: {e}")
            return []

    def fetch_article_detail(self, article_id: int) -> dict[str, Any] | None:
        url = f"{self.BASE_URL}/article/info/get"
        params = {"id": article_id, "view": "second"}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data["error"] == 0:
                return data["data"]
            return None
        except Exception as e:
            logging.error(f"Fetcher: 获取文章详情失败: {e}")
            return None

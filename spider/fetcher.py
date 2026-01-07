import requests
import logging


class SspaiFetcher:
    BASE_URL = "https://sspai.com/api/v1"
    HEADERS = {"User-Agent": "curl/7.64.1"}  # Mimic curl for now to see if it works

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_feed_articles(self, limit=20, offset=0):
        """
        Fetch articles from the main feed.
        Endpoint: /api/v1/article/index/page/get
        """
        url = f"{self.BASE_URL}/article/index/page/get"
        params = {
            "limit": limit,
            "offset": offset,
            "created_at": 0,  # Seems to be a required param, 0 for latest?
        }

        try:
            # print(f"DEBUG: Requesting {url} with params {params}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("error") == 0:
                return data.get("data", [])
            return []
        except Exception as e:
            logging.error(f"Fetcher:抓取失败 {e}")
            return []

    def get_article_detail(self, article_id):
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
            logging.error(f"Fetcher:获取文章详情失败: {e}")
            return None

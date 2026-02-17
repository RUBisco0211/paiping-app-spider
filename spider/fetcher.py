import asyncio
import json
import logging

import aiohttp

from .data import JSONObjdctType


class PaiArticleFetcher:
    BASE_URL = "https://sspai.com/api/v1"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://sspai.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }

    def __init__(
        self,
        request_timeout: int = 15,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
    ):
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        self.session = aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout)

    async def close(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()

    async def _request_json(
        self, url: str, params: dict[str, str | int], context: str
    ) -> JSONObjdctType | None:
        if self.session is None:
            raise RuntimeError("Fetcher session 未初始化，请先调用 start()")

        for retry_count in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    body = await response.text()
                    return json.loads(body)
            except asyncio.TimeoutError:
                logging.warning(
                    f"Fetcher: 请求超时 context={context} retry_count={retry_count + 1}"
                )
            except aiohttp.ClientResponseError as e:
                logging.error(
                    f"Fetcher: HTTP错误 context={context} status={e.status} retry_count={retry_count + 1}"
                )
            except (aiohttp.ClientError, json.JSONDecodeError) as e:
                logging.error(
                    f"Fetcher: 请求/解析错误 context={context} error={e} retry_count={retry_count + 1}"
                )

            if retry_count < self.max_retries - 1:
                await asyncio.sleep(self.retry_base_delay * (2**retry_count))

        return None

    async def fetch_feed_articles(self, limit=20, offset=0) -> list[JSONObjdctType]:
        url = f"{self.BASE_URL}/article/index/page/get"
        params = {
            "limit": limit,
            "offset": offset,
            "created_at": 0,
        }

        logging.info(f"Fetcher: 抓取文章列表, offset={offset} limit={limit}")
        data = await self._request_json(
            url=url,
            params=params,
            context=f"feed offset={offset}",
        )
        if data is None:
            return []
        if data.get("error") == 0:
            return data.get("data", [])

        logging.error(
            f"Fetcher: 服务返回错误 context=feed offset={offset} error={data.get('error')}"
        )
        return []

    async def fetch_article_detail(self, article_id: int) -> JSONObjdctType | None:
        url = f"{self.BASE_URL}/article/info/get"
        params = {"id": article_id, "view": "second"}
        data = await self._request_json(
            url=url,
            params=params,
            context=f"detail article_id={article_id}",
        )
        if data is None:
            return None
        if data.get("error") == 0:
            return data.get("data")

        logging.error(
            f"Fetcher: 服务返回错误 context=detail article_id={article_id} error={data.get('error')}"
        )
        return None

import asyncio
import datetime as dt
import logging

import aiohttp
import requests


def date_format(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d")


def datetime_format(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def fetch_image_bytes(url, timeout=10, headers=None) -> bytes:
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://sspai.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }

    resp = requests.get(url, stream=True, timeout=timeout, headers=headers)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"url 无法指向图片: {content_type}")

    return resp.content


async def fetch_image_bytes_async(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int = 10,
) -> bytes:
    try:
        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                raise ValueError(f"url 无法指向图片: {content_type}")
            return await resp.read()
    except asyncio.TimeoutError as e:
        logging.error(f"图片下载超时: {url}")
        raise TimeoutError(url) from e

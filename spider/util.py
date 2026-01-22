import requests


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

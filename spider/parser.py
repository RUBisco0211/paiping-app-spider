import datetime
import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify as md

from .data import PaiAppData, PaiAppRawData


class PaiAppParser:
    SPECIAL_IMAGE_SUFFIX = (".png", ".jpg", ".jpeg", "PNG", ".JPG", ".JPEG")

    def parse_apps(self, article: dict[str, Any] | None) -> list[PaiAppData]:
        if article is None:
            logging.info("文章内容不存在")
            return []

        pub_date = "1970-01-01"
        if "released_time" in article:
            dt = datetime.datetime.fromtimestamp(article["released_time"])
            pub_date = dt.strftime("%Y-%m-%d")

        # 新返回格式
        if article["body_extends"] and len(article["body_extends"]) > 2:
            return self._parse_apps_new(article, pub_date)

        html_content = article.get("body", "")
        soup = BeautifulSoup(html_content, "html.parser")
        current_app = None
        apps: list[PaiAppData] = []
        h2_els = soup.find_all("h2")

        # 新返回格式
        if len(h2_els) == 0:
            return self._parse_apps_new(article, pub_date)

        # IMPORTANT: 只取第一个和第二个h2之间的元素
        content = h2_els[0].next_siblings
        for element in content:
            if not isinstance(element, Tag):
                continue
            if len(h2_els) > 1 and element == h2_els[1]:
                break
            if element.name == "h3":
                if current_app:
                    apps.append(self._finalize_app(current_app, pub_date))
                current_app = PaiAppRawData(
                    title=element.get_text().strip(),
                    html_elements=[],
                )

            else:
                if current_app and not isinstance(current_app.html_elements, str):
                    current_app.html_elements.append(element)

        if current_app:
            apps.append(self._finalize_app(current_app, pub_date))

        return apps

    def _parse_apps_new(self, article: dict[str, Any], date: str) -> list[PaiAppData]:
        """
        新文章 api 返回格式不同
        """
        raw_list: list[dict[str, Any]] = list(article.get("body_extends", []))
        if len(raw_list) <= 2:
            logging.info("没有找到 app")
            return []

        raw_list = raw_list[1:-1]
        apps: list[PaiAppData] = []
        for app_raw in raw_list:
            title = str(app_raw.get("title", ""))
            html_elements = str(app_raw.get("body", ""))
            app = PaiAppRawData(title=title, html_elements=html_elements)
            apps.append(self._finalize_app(app, date))
        return apps

    def _finalize_app(self, app_data: PaiAppRawData, date: str) -> PaiAppData:
        if isinstance(app_data.html_elements, str):
            html_frag = app_data.html_elements
        else:
            html_frag = "".join([str(e) for e in app_data.html_elements])

        img_list = []
        soup_frag = BeautifulSoup(html_frag, "html.parser")
        for img in soup_frag.find_all("img"):
            img_src = str(img.get("src"))
            if not img_src:
                continue
            # IMPORTANT: 特殊格式需要特殊路径处理
            if img_src.split("?")[0].endswith(self.SPECIAL_IMAGE_SUFFIX):
                img_src = f"{img_src}/format/webp"
            logging.info(f"Parser:获取图片下载链接 {img_src}")
            img_list.append(img_src)
            filename = img_src.split("?")[0].split("/")[-1]

            img["src"] = f"images/{filename}"
        html_frag = str(soup_frag)

        platforms = self._extract_platforms(html_frag)
        content_md = f"# {app_data.title}\n\n" + md(html_frag, heading_style="ATX")
        safe_title = self._clean_filename(app_data.title)

        return PaiAppData(
            date=date,
            title=safe_title,
            platforms=platforms,
            content=content_md,
            img_list=img_list,
        )

    def _extract_platforms(self, html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        platforms = []
        # Pattern: <li>平台：iOS</li> or <li>平台：iOS, Android</li>
        for li in soup.find_all("li"):
            text = li.get_text()
            if "平台" in text:
                match = re.search(r"平台[：:]\s*(.*)", text)
                if match:
                    p_str = match.group(1)
                    parts = re.split(r"[,，/、]", p_str)
                    platforms = [p.strip() for p in parts if p.strip()]
                    break

        return platforms

    def _clean_filename(self, text: str) -> str:
        text = text.replace("：", "-").replace(":", "-")
        return re.sub(r'[\\/*?"<>|]', "", text).strip()

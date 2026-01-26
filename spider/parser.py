import datetime
import logging
import re
from typing import Any, Iterator

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify as md

from .data import PaiAppData, PaiAppMdFrontmatter, PaiAppRawData, PaiArticleData


class PaiAppParser:
    SSPAI_ARTICLE_BASE_URL = "https://sspai.com/post"
    SPECIAL_IMAGE_SUFFIX = (".png", ".jpg", ".jpeg", "PNG", ".JPG", ".JPEG")
    DATE_FORMAT = "%Y-%m-%d"
    DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def parse_apps(self, article_raw: dict[str, Any] | None) -> Iterator[PaiAppData]:
        if article_raw is None:
            logging.info("文章内容不存在")
            return

        date = "1970-01-01"
        time = "1970-01-01 00:00:00"
        if "released_time" in article_raw:
            dt = datetime.datetime.fromtimestamp(article_raw["released_time"])
            date = dt.strftime(self.DATE_FORMAT)
            time = dt.strftime(self.DATE_TIME_FORMAT)

        article_data = PaiArticleData(
            id=article_raw["id"],
            title=article_raw["title"],
            url=f"{self.SSPAI_ARTICLE_BASE_URL}/{article_raw['id']}",
            release_time=time,
            released_date=date,
        )

        # 新返回格式
        if "body_extends" in article_raw and len(article_raw["body_extends"]) > 2:
            yield from self._parse_apps_new(article_raw, article_data)
            return

        html_content = article_raw.get("body", "")
        soup = BeautifulSoup(html_content, "html.parser")
        current_app = None
        h2_els = soup.find_all("h2")

        # 新返回格式
        if len(h2_els) == 0:
            yield from self._parse_apps_new(article_raw, article_data)
            return

        # IMPORTANT: 只取第一个和第二个h2之间的元素
        content = h2_els[0].next_siblings
        for element in content:
            if not isinstance(element, Tag):
                continue
            if len(h2_els) > 1 and element == h2_els[1]:
                break
            if element.name == "h3":
                if current_app:
                    yield self._finalize_app(current_app, article_data)
                current_app = PaiAppRawData(
                    title=element.get_text().strip(),
                    html_elements=[],
                )

            else:
                if current_app and not isinstance(current_app.html_elements, str):
                    current_app.html_elements.append(element)

        if current_app:
            yield self._finalize_app(current_app, article_data)

    def _parse_apps_new(
        self, article: dict[str, Any], article_data: PaiArticleData
    ) -> Iterator[PaiAppData]:
        """
        新文章 api 返回格式, app html 在 data.body_extends[].body中
        """
        raw_list: list[dict[str, Any]] = list(article.get("body_extends", []))
        if len(raw_list) <= 2:
            logging.info("没有找到 app")
            return

        raw_list = raw_list[1:-1]
        for app_raw in raw_list:
            title = str(app_raw.get("title", ""))
            html_elements = str(app_raw.get("body", ""))
            app = PaiAppRawData(title=title, html_elements=html_elements)
            yield self._finalize_app(app, article_data)

    def _finalize_app(
        self, app_data: PaiAppRawData, article_data: PaiArticleData
    ) -> PaiAppData:
        if isinstance(app_data.html_elements, str):
            html_frag = app_data.html_elements
        else:
            html_frag = "".join([str(e) for e in app_data.html_elements])

        soup_frag = BeautifulSoup(html_frag, "html.parser")

        img_list, soup_frag = self._extract_and_transform_imgs(soup_frag)
        platforms = self._extract_platforms(soup_frag)
        keywords = self._extract_keywords(soup_frag)
        app_name = re.split(r"[：:]", app_data.title)[0].strip()

        frontmatter = PaiAppMdFrontmatter(
            app_name=app_name,
            title=app_data.title,
            article_id=article_data.id,
            article_title=article_data.title,
            article_url=article_data.url,
            platforms=platforms,
            keywords=keywords,
            released_time=article_data.release_time,
        )

        safe_title = self._clean_filename(app_data.title)
        content_md = self._construct_content(frontmatter, soup_frag)
        return PaiAppData(
            article=article_data,
            file_title=safe_title,
            platforms=platforms,
            content=content_md,
            img_list=img_list,
        )

    def _construct_content(
        self, frontmatter: PaiAppMdFrontmatter, soup: BeautifulSoup
    ) -> str:
        """
        拼接 app markdown 文档内容
        """
        return f"{str(frontmatter)}\n{self._md_title(1, frontmatter.title)}\n{md(str(soup), heading_style='ATX')}"

    def _extract_and_transform_imgs(
        self, soup: BeautifulSoup
    ) -> tuple[list[str], BeautifulSoup]:
        """
        提取可供下载的图片链接列表
        并将 html 内 img.src 转换为本地图片相对路径
        """
        img_list = []
        for img in soup.find_all("img"):
            img_src = str(img.get("src"))
            if not img_src:
                continue
            # IMPORTANT: 特殊格式需要特殊路径处理
            if img_src.split("?")[0].endswith(self.SPECIAL_IMAGE_SUFFIX):
                img_src = f"{img_src}/format/webp"
            logging.info(f"Parser: 获取图片下载链接 {img_src}")
            # TODO: 尝试请求图片
            img_list.append(img_src)
            filename = img_src.split("?")[0].split("/")[-1]
            img["src"] = f"images/{filename}"
        return img_list, soup

    def _extract_platforms(self, soup: BeautifulSoup) -> list[str]:
        """
        提取 app 平台列表
        """
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

    def _extract_keywords(self, soup: BeautifulSoup) -> list[str]:
        """
        提取 app 关键词列表
        """
        keywords = []
        for li in soup.find_all("li"):
            text = li.get_text()
            if "关键词" in text:
                match = re.search(r"关键词[：:]\s*(.*)", text)
                if match:
                    p_str = match.group(1)
                    parts = re.split(r"[,，/、]", p_str)
                    keywords = [p.strip() for p in parts if p.strip()]
                    break
        return keywords

    def _clean_filename(self, text: str) -> str:
        text = text.replace("：", "-").replace(":", "-")
        return re.sub(r'[\\/*?"<>|]', "", text).strip()

    def _md_title(self, level: int, text: str) -> str:
        if level not in range(1, 7):
            logging.error(f"markdown 标题层级 {level} 错误")
        return f"{'#' * level} {text}"

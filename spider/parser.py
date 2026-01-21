import datetime
import logging
import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md


class PaiAppParser:
    def parse_article(self, article, html_content):
        """
        Parse the article HTML and split into app sections.
        Returns a list of dicts: {'title': str, 'platforms': list, 'content': str, 'date': str}
        """
        soup = BeautifulSoup(html_content, "html.parser")

        pub_date = "1970-01-01"
        if "released_time" in article:
            dt = datetime.datetime.fromtimestamp(article["released_time"])
            pub_date = dt.strftime("%Y-%m-%d")

        current_app = None
        apps = []
        h2_els = soup.find_all("h2")
        if len(h2_els) == 0:
            return apps
        # IMPORTANT: 只取第一个和第二个h2之间的元素
        content = h2_els[0].next_siblings
        for element in content:
            if element == h2_els[1]:
                break
            if element.name == "h3":
                if current_app:
                    self._finalize_app(current_app, apps, pub_date)

                current_app = {
                    "title": element.get_text().strip(),
                    "html_elements": [],
                    "article_title": article["title"],
                }
            else:
                if current_app:
                    current_app["html_elements"].append(element)

        if current_app:
            self._finalize_app(current_app, apps, pub_date)

        return apps

    def _finalize_app(self, app_data, apps_list, date):
        html_frag = "".join([str(e) for e in app_data["html_elements"]])

        img_list = []
        soup_frag = BeautifulSoup(html_frag, "html.parser")
        for img in soup_frag.find_all("img"):
            img_src = img.get("src")
            if not img_src:
                continue
            # IMPORTANT: 特殊格式需要特殊路径处理
            if img_src.split("?")[0].endswith(
                (".png", ".jpg", ".jpeg", "PNG", ".JPG", ".JPEG")
            ):
                img_src = f"{img_src}/format/webp"
            logging.info(f"Parser:获取图片下载链接 {img_src}")
            img_list.append(img_src)
            filename = img_src.split("?")[0].split("/")[-1]

            img["src"] = f"images/{filename}"
            logging.info(f"Parser:转换图片为本地引用 images/{filename}")
        html_frag = str(soup_frag)

        platforms = self._extract_platforms(html_frag)
        content_md = f"# {app_data['title']}\n\n" + md(html_frag, heading_style="ATX")
        safe_title = self._clean_filename(app_data["title"])

        parsed_app = {
            "date": date,
            "title": safe_title,
            "original_title": app_data["title"],
            "platforms": platforms,
            "content": content_md,
            "img_list": img_list,
        }

        apps_list.append(parsed_app)

    def _extract_platforms(self, html_content):
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

        if not platforms:
            platforms = ["Unknown"]

        return platforms

    def _clean_filename(self, text):
        text = text.replace("：", "-").replace(":", "-")
        return re.sub(r'[\\/*?"<>|]', "", text).strip()

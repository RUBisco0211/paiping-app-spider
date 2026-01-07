import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import logging


class SspaiParser:
    def parse_article(self, article, html_content):
        """
        Parse the article HTML and split into app sections.
        Returns a list of dicts: {'title': str, 'platforms': list, 'content': str, 'date': str}
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # We split by H3 tags usually.
        # Strategy: Find all H3. Each H3 starts a new section.
        # The content between H3 and next Hn is the section.

        sections = []

        # Get publish date
        pub_date = "1970-01-01"
        if "released_time" in article:
            import datetime

            dt = datetime.datetime.fromtimestamp(article["released_time"])
            pub_date = dt.strftime("%Y-%m-%d")

        # Find all headers. In "派评", apps are usually H3. H2 are used for grouping like "Worth Checking", "Updates", etc.
        # However, we only want to split the Apps.
        # Let's verify if specific H3s are apps.
        # Usually checking the content following it.

        # Let's iterate over ALL siblings in the body to form chunks
        # This is a bit manual but robust.

        # Actually, simpler: markdownify the whole thing, then split by `### `
        # But extracting platforms from Markdown might be harder/easier?
        # HTML extraction of platforms is reliable because of <ul> structure.

        # Hybrid approach:
        # iterate elements. If current is H3, start new item.
        # Append elements to current item.
        # At end of item, parse platforms from the collected HTML elements, then convert content to MD.

        current_app = None
        apps = []

        # We process direct children of specific container or just all tags?
        # The sample showed content is a string of tags. BeautifulSoup handles that.

        for element in soup.contents:
            if element.name == "h3":
                # Save previous app if valid
                if current_app:
                    self._finalize_app(current_app, apps, pub_date)

                # Start new app
                current_app = {
                    "title": element.get_text().strip(),
                    "html_elements": [],
                    "article_title": article["title"],  # Context
                }
            elif current_app:
                # Add to current app
                current_app["html_elements"].append(element)

        # Finalize last app
        if current_app:
            self._finalize_app(current_app, apps, pub_date)

        return apps

    def _finalize_app(self, app_data, apps_list, date):
        # Convert HTML list to string
        html_frag = "".join([str(e) for e in app_data["html_elements"]])

        img_list = []
        # Process images to fix lazy loading and convert to local references
        soup_frag = BeautifulSoup(html_frag, "html.parser")
        for img in soup_frag.find_all("img"):
            img_src = img.get("src")
            if not img_src:
                continue
            if img_src.split("?")[0].endswith(
                (".png", ".jpg", ".jpeg", "PNG", ".JPG", ".JPEG")
            ):
                img_src = f"{img_src}/format/webp"

            # Keep original URL for downloader
            logging.info(f"Parser:获取图片下载链接 {img_src}")
            img_list.append(img_src)
            # Extract filename from URL
            filename = img_src.split("?")[0].split("/")[-1]

            # Convert to relative path: images/filename
            img["src"] = f"images/{filename}"
            logging.info(f"Parser:转换图片为本地引用 images/{filename}")
        # Update html_frag with processed images
        html_frag = str(soup_frag)

        # Extract Platform
        # Look for "平台：xxx" in list items
        platforms = self._extract_platforms(html_frag)

        # Convert to Markdown
        # We include the title as a header in the markdown?
        # User wants the file content to be the section.
        # It's good to keep the header in the file content too.
        content_md = f"### {app_data['title']}\n\n" + md(html_frag, heading_style="ATX")

        # Clean title for filename (remove special chars)
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
        # Iterate all li
        for li in soup.find_all("li"):
            text = li.get_text()
            if "平台" in text:
                # Extract value after colon
                # Support Chinese and English colon
                match = re.search(r"平台[：:]\s*(.*)", text)
                if match:
                    p_str = match.group(1)
                    # Split by comma or similar
                    # Check for "iOS / Android" or "iOS, Android"
                    parts = re.split(r"[,，/、]", p_str)
                    platforms = [p.strip() for p in parts if p.strip()]
                    break  # Usually only one platform line

        if not platforms:
            platforms = ["Unknown"]

        return platforms

    def _clean_filename(self, text):
        # Remove invalid chars for filename
        # Allow Chinese, letters, numbers, _, -
        # Replace colon with dash maybe?
        text = text.replace("：", "-").replace(":", "-")
        return re.sub(r'[\\/*?"<>|]', "", text).strip()

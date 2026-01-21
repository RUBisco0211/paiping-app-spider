import logging
import os

from spider.data import PaiAppData

from .util import fetch_image_bytes


class PaiAppSaver:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def save_app(self, app_data: PaiAppData):
        platforms_str = ",".join(app_data.platforms)
        filename = f"{app_data.title}-[{platforms_str}].md"

        date_dir = os.path.join(self.output_dir, app_data.date)
        if not os.path.exists(date_dir):
            os.makedirs(date_dir)

        filename = filename.replace("/", "-").replace("\\", "-")

        app_img_dir = os.path.join(date_dir, "images")
        if not os.path.exists(app_img_dir):
            os.makedirs(app_img_dir)

        content = app_data.content
        self._download_images(app_data.img_list, app_img_dir)

        filepath = os.path.join(date_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info(f"Saver:保存了文章 {filename}")
        except Exception as e:
            logging.error(f"Saver:保存失败 {filename}: {e}")

    def _download_images(self, list: list[str], img_dir: str):
        for img_src in list:
            filename = img_src.split("?")[0].split("/")[-1]
            local_path = os.path.join(img_dir, filename)

            if os.path.exists(local_path):
                logging.info(f"Saver:图片已存在, 跳过 {filename}")
                continue

            try:
                image_data = fetch_image_bytes(img_src)
                if image_data:
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    logging.info(f"Saver:下载图片成功 {img_src}")
                else:
                    raise Exception(f"Saver:下载图片失败 {img_src}")
            except Exception as e:
                logging.error(e)

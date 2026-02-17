import asyncio
import logging
import os

import aiohttp

from .data import PaiAppData

from .util import fetch_image_bytes, fetch_image_bytes_async


class PaiAppSaver:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def save_app(self, app_data: PaiAppData):
        platforms_str = ",".join(app_data.platforms)
        filename = f"{app_data.file_title}-[{platforms_str}].md"
        filename = filename.replace("/", "-").replace("\\", "-")

        date_dir = os.path.join(self.output_dir, app_data.article.released_date)
        if not os.path.exists(date_dir):
            os.makedirs(date_dir)

        app_img_dir = os.path.join(date_dir, "images")
        if not os.path.exists(app_img_dir):
            os.makedirs(app_img_dir)

        self._download_images(app_data.img_list, app_img_dir)

        content = app_data.content
        filepath = os.path.join(date_dir, filename)

        if os.path.exists(filepath):
            logging.info(f"Saver: 文件 {filepath} 将被覆盖")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info(f"Saver: 保存文章 {filename}")
        except Exception as e:
            logging.error(f"Saver: 保存失败 {filename}: {e}")

    async def save_app_async(
        self,
        app_data: PaiAppData,
        session: aiohttp.ClientSession,
        image_semaphore: asyncio.Semaphore,
        timeout: int = 15,
    ) -> tuple[int, int]:
        platforms_str = ",".join(app_data.platforms)
        filename = f"{app_data.file_title}-[{platforms_str}].md"
        filename = filename.replace("/", "-").replace("\\", "-")

        date_dir = os.path.join(self.output_dir, app_data.article.released_date)
        app_img_dir = os.path.join(date_dir, "images")
        await asyncio.to_thread(os.makedirs, date_dir, exist_ok=True)
        await asyncio.to_thread(os.makedirs, app_img_dir, exist_ok=True)

        img_success, img_failed = await self._download_images_async(
            app_data.img_list,
            app_img_dir,
            session=session,
            image_semaphore=image_semaphore,
            timeout=timeout,
        )

        content = app_data.content
        filepath = os.path.join(date_dir, filename)

        if os.path.exists(filepath):
            logging.info(f"Saver: 文件 {filepath} 将被覆盖")

        try:
            await asyncio.to_thread(self._write_text_file, filepath, content)
            logging.info(f"Saver: 保存文章 {filename}")
        except Exception as e:
            logging.error(f"Saver: 保存失败 {filename}: {e}")

        return img_success, img_failed

    def _download_images(self, imgs: list[str], img_dir: str):
        for img_src in imgs:
            filename = img_src.split("?")[0].split("/")[-1]
            local_path = os.path.join(img_dir, filename)

            if os.path.exists(local_path):
                logging.info(f"Saver: 图片已存在, 跳过 {filename}")
                continue

            try:
                image_data = fetch_image_bytes(img_src)
                if image_data:
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    logging.info(f"Saver: 下载图片成功 {img_src}")
                else:
                    raise Exception(img_src)
            except Exception as e:
                logging.error(f"Saver: 下载图片失败 {e}")

    async def _download_images_async(
        self,
        imgs: list[str],
        img_dir: str,
        session: aiohttp.ClientSession,
        image_semaphore: asyncio.Semaphore,
        timeout: int = 15,
    ) -> tuple[int, int]:
        tasks = [
            asyncio.create_task(
                self._download_one_image(
                    img_src=img_src,
                    img_dir=img_dir,
                    session=session,
                    image_semaphore=image_semaphore,
                    timeout=timeout,
                )
            )
            for img_src in imgs
        ]
        if not tasks:
            return 0, 0

        results = await asyncio.gather(*tasks, return_exceptions=False)
        success = sum(1 for result in results if result)
        failed = len(results) - success
        return success, failed

    async def _download_one_image(
        self,
        img_src: str,
        img_dir: str,
        session: aiohttp.ClientSession,
        image_semaphore: asyncio.Semaphore,
        timeout: int = 15,
    ) -> bool:
        filename = img_src.split("?")[0].split("/")[-1]
        local_path = os.path.join(img_dir, filename)

        if os.path.exists(local_path):
            logging.info(f"Saver: 图片已存在, 跳过 {filename}")
            return True

        async with image_semaphore:
            try:
                image_data = await fetch_image_bytes_async(
                    session=session,
                    url=img_src,
                    timeout=timeout,
                )
                await asyncio.to_thread(self._write_binary_file, local_path, image_data)
                logging.info(f"Saver: 下载图片成功 {img_src}")
                return True
            except Exception as e:
                logging.error(f"Saver: 下载图片失败 {img_src}: {e}")
                return False

    def _write_binary_file(self, path: str, content: bytes):
        with open(path, "wb") as f:
            f.write(content)

    def _write_text_file(self, path: str, content: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

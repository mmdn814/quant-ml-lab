# ✅ 文件：shared/edgar_downloader.py
# 功能：根据 accession 列表下载 Form 4 XML 文件，支持 daily-index 和 atom feed 两种抓取模式

import os
import time
import logging
import requests
from typing import List, Tuple
from shared.daily_index_parser import get_form4_accessions_range

logger = logging.getLogger("insider_ceo")

class EdgarDownloader:
    @staticmethod
    def download_latest_form4(days_back: int = 3, mode: str = "index") -> List[str]:
        """
        下载最新的 Form 4 XML 文件，返回文件路径列表。

        参数：
            days_back (int): 回溯天数，默认3天
            mode (str): 'index' 或 'atom' 模式（目前仅实现 index）
        """
        logger.info(f"🔍 使用 {mode}-based 模式，回溯 {days_back} 天")

        if mode == "index":
            accessions = get_form4_accessions_range(days_back)
        else:
            logger.warning("⚠️ 当前仅支持 index 模式，atom 模式暂未实现")
            return []

        save_dir = "data/sec_forms"
        os.makedirs(save_dir, exist_ok=True)

        downloaded_files = []
        for cik, accession, url in accessions:
            cik_dir = os.path.join(save_dir, cik)
            os.makedirs(cik_dir, exist_ok=True)
            file_path = os.path.join(cik_dir, f"{accession}.xml")

            if os.path.exists(file_path):
                logger.info(f"🟡 已存在，跳过: {file_path}")
                downloaded_files.append(file_path)
                continue

            try:
                headers = {"User-Agent": "quant-ml-lab/1.0 (mmdn814@gmail.com)"}
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                with open(file_path, "w") as f:
                    f.write(res.text)
                logger.info(f"✅ 成功下载: {file_path}")
                downloaded_files.append(file_path)
                time.sleep(0.3)  # 防止过快请求
            except Exception as e:
                logger.warning(f"❌ 下载失败: {url}")
                logger.warning(f"原因: {e}")

        logger.info(f"📥 下载 Form 4 文件数: {len(downloaded_files)}")
        return downloaded_files

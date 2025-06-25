# edgar_downloader.py
# 最后修改时间：2025-06-25
# 功能：从 SEC 获取 Form 4 文件，支持传统 URL 构建 + SEC API 模式

import os
import requests
import zipfile
import io
import time
from datetime import datetime, timedelta
from shared.sec_api_helper import SecApiHelper

class EdgarDownloader:
    def __init__(self, logger):
        self.logger = logger
        self.base_url = "https://www.sec.gov/Archives/edgar/daily-index"
        self.headers = {
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)"
        }

    def download_latest_form4(self, days_back=3, use_sec_api=False):
        save_dir = "data/form4"
        os.makedirs(save_dir, exist_ok=True)

        if use_sec_api:
            self.logger.info("✅ 使用 SEC API 下载最新 Form 4 报告")
            helper = SecApiHelper(self.logger)
            return helper.download_recent_form4s(save_dir, limit=100)

        self.logger.info(f"📦 使用 EDGAR daily-index 下载过去 {days_back} 天的 Form 4")
        downloaded_files = []
        today = datetime.utcnow()

        for i in range(days_back):
            date = today - timedelta(days=i)
            year = date.year
            quarter = (date.month - 1) // 3 + 1
            date_str = date.strftime("%Y%m%d")
            zip_url = f"{self.base_url}/{year}/QTR{quarter}/form.idx"

            try:
                self.logger.info(f"➡️ 解析 daily-index: {zip_url}")
                resp = requests.get(zip_url, headers=self.headers, timeout=15)
                resp.raise_for_status()

                lines = resp.text.splitlines()
                form4_links = []

                for line in lines:
                    if "FORM 4" in line.upper():
                        parts = line.split()
                        if len(parts) >= 5:
                            path = parts[-1]
                            if path.endswith(".txt"):
                                form4_links.append(path)

                for rel_path in form4_links:
                    full_url = f"https://www.sec.gov/Archives/{rel_path}"
                    try:
                        self.logger.info(f"下载 Form 4: {full_url}")
                        r = requests.get(full_url, headers=self.headers, timeout=15)
                        r.raise_for_status()

                        accession = rel_path.split("/")[-1].replace(".txt", "").replace("-", "")
                        cik = rel_path.split("/")[2]
                        filename = f"{cik}-{accession}.xml"
                        path = os.path.join(save_dir, filename)
                        with open(path, 'wb') as f:
                            f.write(r.content)

                        downloaded_files.append(path)
                        time.sleep(0.4)
                    except Exception as e:
                        self.logger.warning(f"单条下载失败: {e}")

            except Exception as e:
                self.logger.warning(f"跳过 {zip_url} 失败: {e}")

        return downloaded_files

# sec_api_helper.py
# 最后修改时间：2025-06-25
# 功能：辅助从 SEC 的 JSON API 获取最新 Form 4 报告，并保存 XML 文件

import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class SecApiHelper:
    def __init__(self, logger):
        self.logger = logger
        self.api_key = os.getenv("SEC_API_KEY")
        if not self.api_key:
            raise ValueError("未设置 SEC_API_KEY 环境变量")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)"
        })

    def download_recent_form4s(self, save_dir, limit=50):
        url = f"https://api.sec-api.io/form4?limit={limit}&sort=-filedAt"
        self.logger.info(f"[SEC API] 获取最近 {limit} 条 Form 4 报告: {url}")

        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            items = resp.json().get("data", [])
        except Exception as e:
            self.logger.error(f"[SEC API] 请求失败: {e}")
            return []

        downloaded_files = []

        for item in items:
            try:
                xml_url = item.get("linkToXml")
                if not xml_url:
                    continue

                accession = item.get("accessionNumber", "noaccession").replace("-", "")
                cik = item.get("cik")
                filename = f"{cik}-{accession}.xml"
                local_path = os.path.join(save_dir, filename)

                self.logger.info(f"[SEC API] 下载 XML: {xml_url}")
                r = self.session.get(xml_url, timeout=15)
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    f.write(r.content)

                downloaded_files.append(local_path)
                time.sleep(0.5)  # 避免过快请求
            except Exception as e:
                self.logger.warning(f"[SEC API] 单条下载失败: {e}")

        return downloaded_files

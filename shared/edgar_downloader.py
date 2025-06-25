# edgar_downloader.py
# 最后修改时间：2025-06-25
# 功能：从 SEC EDGAR 抓取最近 N 天的 Form 4 XML 文件，包含 retry、限流、合规 user-agent、错误记录等

import os
import requests
import time
import random
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from time import sleep
from shared.sec_api_helper import SecApiHelper  # ✅ 用于构造稳定 XML 下载链接

class EdgarDownloader:
    """
    用于从 SEC EDGAR 获取最新 Form 4 报告的下载器，带 retry 和限流。
    """

    def __init__(self, logger, data_dir='data/insider_ceo'):
        self.logger = logger
        self.data_dir = data_dir
        self.headers = {
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)",  # ✅ 合规 UA
            "Accept": "application/atom+xml",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "From": "mmdn814@gmail.com"
        }

        os.makedirs(self.data_dir, exist_ok=True)

    def download_latest_form4(self, days_back=7, use_sec_api=False):
        """
        下载最近 N 天内 Form 4 报告（支持用稳定 URL 构造函数）
        """
        self.logger.info(f"开始下载最近 {days_back} 天内 Form 4 报告")
        downloaded_files = []

        for delta in range(days_back):
            target_date = datetime.now() - timedelta(days=delta)
            date_str = target_date.strftime("%Y-%m-%d")

            for attempt in range(1, 4):
                try:
                    self.logger.info(f"[尝试 {attempt}/3] 抓取 Atom Feed: {date_str}")
                    daily_files = self._download_daily_atom(target_date, use_sec_api)
                    downloaded_files.extend(daily_files)
                    break
                except Exception as e:
                    self.logger.warning(f"[尝试 {attempt}/3] 获取 Atom Feed 失败: {e}")
                    time.sleep(2 + attempt)
            else:
                self.logger.warning(f"❌ 日期 {date_str} 下载失败，跳过")

            time.sleep(random.uniform(2.5, 4.0))  # 限流

        self.logger.info(f"下载完成，共获取 {len(downloaded_files)} 份 Form 4")
        return downloaded_files

    def _download_daily_atom(self, target_date, use_sec_api=False):
        """
        抓取指定日期的 SEC Atom feed 并解析出 Form 4 XML 文件
        """
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&dateb={date_str}&owner=only&type=4&output=atom"
        self.logger.info(f"抓取 Atom Feed: {url}")

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning(f"[尝试 {attempt + 1}/3] 获取 Atom Feed 失败: {e}")
                sleep(2)
        else:
            raise RuntimeError("❌ 三次尝试仍然失败，跳过")

        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        self.logger.info(f"当天发现 {len(entries)} 条 Form 4 记录")

        daily_files = []

        for entry in entries:
            try:
                html_url = entry.find('atom:link', ns).attrib['href']
                if use_sec_api:
                    form4_url = SecApiHelper.construct_xml_url(html_url)
                else:
                    form4_url = html_url.replace("-index.html", ".xml")

                filename = form4_url.split("/")[-1]
                local_path = os.path.join(self.data_dir, filename)

                self._download_single_form4(form4_url, local_path)
                daily_files.append(local_path)

            except Exception as e:
                self.logger.warning(f"单条下载失败: {e}")

        return daily_files

    def _download_single_form4(self, filing_url, local_path):
        """
        下载并保存单个 XML 报告文件
        """
        self.logger.info(f"下载 Form 4: {filing_url}")
        resp = requests.get(filing_url, headers=self.headers, timeout=10)
        resp.raise_for_status()

        with open(local_path, 'wb') as f:
            f.write(resp.content)

        self.logger.info(f"已保存: {local_path}")

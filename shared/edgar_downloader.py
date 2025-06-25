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


class EdgarDownloader:
    """
    用于从 SEC EDGAR 获取最新 Form 4 报告的下载器，带 retry 和限流。
    """

    def __init__(self, logger, data_dir='data/insider_ceo'):
        self.logger = logger
        self.data_dir = data_dir
        self.headers = {
            # ✅ 必须包含声明身份的 User-Agent（SEC 官方要求）
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)",
            "Accept": "application/atom+xml",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "From": "mmdn814@gmail.com"
        }

        # 如果数据目录不存在则创建
        os.makedirs(self.data_dir, exist_ok=True)

    def download_latest_form4(self, days_back=7):
        """
        主函数：下载最近 N 天 Form 4 报告（XML 文件）
        :param days_back: 最近几天（整数）
        :return: 下载的本地 XML 文件路径列表
        """
        self.logger.info(f"开始下载最近 {days_back} 天内 Form 4 报告")
        downloaded_files = []

        for delta in range(days_back):
            target_date = datetime.now() - timedelta(days=delta)
            date_str = target_date.strftime("%Y-%m-%d")

            for attempt in range(1, 4):  # 最多 3 次尝试抓取 Atom feed
                try:
                    self.logger.info(f"[尝试 {attempt}/3] 抓取 Atom Feed: {date_str}")
                    daily_files = self._download_daily_atom(target_date)
                    downloaded_files.extend(daily_files)
                    break
                except Exception as e:
                    self.logger.warning(f"[尝试 {attempt}/3] 获取 Atom Feed 失败: {e}")
                    time.sleep(2 + attempt)  # 增量回退等待时间
            else:
                self.logger.warning(f"日期 {target_date.strftime('%Y%m%d')} 下载失败: ❌ 三次尝试仍然失败，跳过")

            # 限流等待，避免触发反爬机制
            time.sleep(random.uniform(2.5, 4.0))

        self.logger.info(f"下载完成，共获取 {len(downloaded_files)} 份 Form 4")
        return downloaded_files

    def _download_daily_atom(self, target_date):
        """
        抓取指定日期的 SEC Atom feed 并解析出 Form 4 XML 文件
        :param target_date: datetime 类型
        :return: 下载的文件路径列表
        """
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&dateb={date_str}&owner=only&type=4&output=atom"
        self.logger.info(f"抓取 Atom Feed: {url}")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning(f"[尝试 {attempt + 1}/{max_attempts}] 获取 Atom Feed 失败: {e}")
                sleep(2)
        else:
            raise RuntimeError("❌ 三次尝试仍然失败，跳过")

        # 解析 XML 内容
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        self.logger.info(f"当天发现 {len(entries)} 条 Form 4 记录")

        daily_files = []

        for entry in entries:
            try:
                # 从 link 标签提取实际可访问的 HTML 页面链接
                html_url = entry.find('atom:link', ns).attrib['href']
                # 替换 -index.html 为 .xml（EDGAR 规则）
                form4_url = html_url.replace("-index.html", ".xml")
        
                # 提取 accession 编号作为文件名
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

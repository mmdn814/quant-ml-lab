#完全使用 SEC 官方 API (Atom feed)，避免中间第三方失效问题；
#支持多天抓取兜底；
#单文件独立错误捕捉，最大限度提升稳定性；
#日志打印非常详细，方便后续监控；
#后续兼容你当前 main.py 完全一致，已准备好集成。

import os
import requests
import gzip
import shutil
from datetime import datetime, timedelta
from time import sleep
from xml.etree import ElementTree as ET

class EdgarDownloader:
    """
    用于从 SEC EDGAR 获取最新 Form 4 报告的下载器
    """

    def __init__(self, logger, data_dir='data/insider_ceo'):
        self.logger = logger
        self.data_dir = data_dir
        self.base_feed_url = "https://www.sec.gov/Archives/edgar/daily-index/xbrl"
        self.headers = {
            'User-Agent': 'Quant-ML-Lab SEC Downloader (mmdn814)',  # 改为你自己 github id
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }
        os.makedirs(self.data_dir, exist_ok=True)

    def download_latest_form4(self, days_back=2):
        """
        下载最近 N 天内所有 Form 4 XML 文件
        """
        self.logger.info(f"开始下载最近 {days_back} 天内 Form 4 报告")
        downloaded_files = []

        for delta in range(days_back):
            target_date = datetime.now() - timedelta(days=delta)
            date_str = target_date.strftime("%Y%m%d")
            atom_url = f"https://www.sec.gov/Archives/edgar/usgaap.rss.xml"

            try:
                feed_url = f"https://www.sec.gov/Archives/edgar/daily-index/{target_date.year}/QTR{(target_date.month - 1) // 3 + 1}/index.json"
                self.logger.info(f"抓取日期: {target_date.strftime('%Y-%m-%d')} -> {feed_url}")
                daily_files = self._download_daily_atom(target_date)
                downloaded_files.extend(daily_files)
            except Exception as e:
                self.logger.warning(f"日期 {date_str} 下载失败: {e}")

            sleep(1)  # 防止频率过快被SEC限制

        self.logger.info(f"下载完成，共获取 {len(downloaded_files)} 份 Form 4")
        return downloaded_files

    def _download_daily_atom(self, target_date):
        """
        直接读取 SEC 的每日 atom feed (官方API源头)
        """
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&dateb={date_str}&owner=only&type=4&output=atom"
        self.logger.info(f"抓取 Atom Feed: {url}")

        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.raise_for_status()

        # 解析 XML
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        self.logger.info(f"当天发现 {len(entries)} 条 Form 4 记录")

        daily_files = []

        for entry in entries:
            try:
                filing_href = entry.find('atom:link', ns).attrib['href']
                accession = filing_href.split('/')[-2]
                filename = f"{accession}.xml"
                local_path = os.path.join(self.data_dir, filename)
                self._download_single_form4(filing_href, local_path)
                daily_files.append(local_path)
            except Exception as e:
                self.logger.warning(f"单条下载失败: {e}")

        return daily_files

    def _download_single_form4(self, filing_url, local_path):
        """
        下载并保存单份 Form 4 XML 文件
        """
        self.logger.info(f"下载 Form 4: {filing_url}")
        resp = requests.get(filing_url, headers=self.headers, timeout=10)
        resp.raise_for_status()

        # SEC Form 4文件一般直接是 xml，无需解压
        with open(local_path, 'wb') as f:
            f.write(resp.content)

        self.logger.info(f"已保存: {local_path}")


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
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)",
            "Accept": "application/atom+xml",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "From": "mmdn814@gmail.com"
        }

        os.makedirs(self.data_dir, exist_ok=True)

    def download_latest_form4(self, days_back=7):
        self.logger.info(f"\u5f00\u59cb\u4e0b\u8f7d\u6700\u8fd1 {days_back} \u5929\u5185 Form 4 \u62a5\u544a")
        downloaded_files = []

        for delta in range(days_back):
            target_date = datetime.now() - timedelta(days=delta)
            date_str = target_date.strftime("%Y-%m-%d")

            for attempt in range(1, 4):
                try:
                    self.logger.info(f"[\u5c1d\u8bd5 {attempt}/3] \u6293\u53d6 Atom Feed: {date_str}")
                    daily_files = self._download_daily_atom(target_date)
                    downloaded_files.extend(daily_files)
                    break
                except Exception as e:
                    self.logger.warning(f"[\u5c1d\u8bd5 {attempt}/3] \u83b7\u53d6 Atom Feed \u5931\u8d25: {e}")
                    time.sleep(2 + attempt)
            else:
                self.logger.warning(f"\u65e5\u671f {target_date.strftime('%Y%m%d')} \u4e0b\u8f7d\u5931\u8d25: \u274c \u4e09\u6b21\u5c1d\u8bd5\u4ecd\u7136\u5931\u8d25\uff0c\u8df3\u8fc7")

            time.sleep(random.uniform(2.5, 4.0))

        self.logger.info(f"\u4e0b\u8f7d\u5b8c\u6210\uff0c\u5171\u83b7\u53d6 {len(downloaded_files)} \u4efd Form 4")
        return downloaded_files

    def _download_daily_atom(self, target_date):
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&dateb={date_str}&owner=only&type=4&output=atom"
        self.logger.info(f"\u6293\u53d6 Atom Feed: {url}")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning(f"[\u5c1d\u8bd5 {attempt + 1}/{max_attempts}] \u83b7\u53d6 Atom Feed \u5931\u8d25: {e}")
                sleep(2)
        else:
            raise RuntimeError("\u274c \u4e09\u6b21\u5c1d\u8bd5\u4ecd\u7136\u5931\u8d25\uff0c\u8df3\u8fc7")

        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        self.logger.info(f"\u5f53\u5929\u53d1\u73b0 {len(entries)} \u6761 Form 4 \u8bb0\u5f55")

        daily_files = []

        for entry in entries:
            try:
                accession_id_elem = entry.find('atom:accession-number', ns)
                cik_elem = entry.find('atom:category', ns)
                if accession_id_elem is None or cik_elem is None or 'term' not in cik_elem.attrib:
                    continue

                accession = accession_id_elem.text.strip()
                cik = cik_elem.attrib['term'].split(':')[-1].zfill(10)
                accession_nodash = accession.replace("-", "")
                filename = f"{accession}.xml"

                form4_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{accession}.xml"
                local_path = os.path.join(self.data_dir, filename)

                self._download_single_form4(form4_url, local_path)
                daily_files.append(local_path)
            except Exception as e:
                self.logger.warning(f"\u5355\u6761\u4e0b\u8f7d\u5931\u8d25: {e}")

        return daily_files

    def _download_single_form4(self, filing_url, local_path):
        self.logger.info(f"\u4e0b\u8f7d Form 4: {filing_url}")
        resp = requests.get(filing_url, headers=self.headers, timeout=10)
        resp.raise_for_status()

        with open(local_path, 'wb') as f:
            f.write(resp.content)

        self.logger.info(f"\u5df2\u4fdd\u5b58: {local_path}")

# ✅ 文件：shared/edgar_downloader.py
# 功能：支持 SEC Form 4 下载（支持 atom feed 和 daily index 两种模式）

import os
import time
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from shared.daily_index_parser import get_form4_accessions_range

class EdgarDownloader:
    def __init__(self, logger, max_retries: int = 3, timeout: int = 15, request_interval: float = 1.0, cache_dir: str = ".cache"):
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.request_interval = request_interval
        self.base_url = "https://www.sec.gov"
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "quant-ml-lab/1.0 (mmdn814@gmail.com)",
            "Accept": "application/xml, text/xml, text/html"
        }

    def download_latest_form4(self, days_back: int = 3, save_dir: str = "data/form4", mode: str = "atom") -> List[str]:
        os.makedirs(save_dir, exist_ok=True)
        downloaded_files = []
        seen = set()

        if mode == "index":
            self.logger.info(f"🔍 使用 daily-index 模式，回溯 {days_back} 天")
            accessions = get_form4_accessions_range(days_back, cache_dir=self.cache_dir)

            for idx, (cik, accession, filing_url) in enumerate(accessions):
                key = f"{cik}_{accession}"
                if key in seen:
                    continue
                seen.add(key)
                try:
                    filepath = self._download_by_cik_accession(cik, accession, save_dir)
                    if filepath:
                        downloaded_files.append(filepath)
                        self.logger.debug(f"[{idx+1}/{len(accessions)}] 下载成功: {filepath}")
                except Exception as e:
                    self.logger.warning(f"下载失败: {filing_url}，错误: {e}")
                time.sleep(self.request_interval)

        else:
            # 默认 atom 模式
            feed_url = self._build_feed_url(days_back)
            entries = self._fetch_atom_feed(feed_url)
            self.logger.info(f"📥 Atom Feed 中发现 {len(entries)} 条 Form 4 报告")
            for idx, entry in enumerate(entries):
                try:
                    filepath = self._process_entry(entry, save_dir)
                    if filepath:
                        downloaded_files.append(filepath)
                        self.logger.debug(f"[{idx+1}/{len(entries)}] 下载完成: {filepath}")
                except Exception as e:
                    self.logger.warning(f"跳过失败条目: {e}", exc_info=True)
                time.sleep(self.request_interval)

        self.logger.info(f"✅ 总共成功下载 {len(downloaded_files)} 个 Form 4 XML 文件")
        return downloaded_files

    def _build_feed_url(self, days_back: int) -> str:
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        params = {
            "action": "getcurrent",
            "type": "4",
            "datea": start_date.strftime("%Y%m%d"),
            "output": "atom"
        }
        return urljoin(self.base_url, "/cgi-bin/browse-edgar?" + urlencode(params))

    def _fetch_atom_feed(self, url: str):
        try:
            res = self.session.get(url, timeout=self.timeout)
            res.raise_for_status()
            soup = BeautifulSoup(res.content, "xml")
            return [e for e in soup.find_all("entry") if e.find("category", {"term": "4"})]
        except Exception as e:
            self.logger.error(f"获取 Atom Feed 失败: {e}")
            return []

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        url = entry.link["href"]
        try:
            cik, accession = self._extract_identifiers(url)
            return self._download_by_cik_accession(cik, accession, save_dir)
        except Exception as e:
            self.logger.warning(f"跳过条目，无法解析 URL: {url}，错误: {e}")
            return None

    def _extract_identifiers(self, url: str) -> tuple:
        import re
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url)
        if not match:
            raise ValueError("URL 格式无效，无法提取 CIK 和 Accession")
        return match.group(1).zfill(10), match.group(2)

    def _download_by_cik_accession(self, cik: str, accession: str, save_dir: str) -> Optional[str]:
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)
        if os.path.exists(filepath):
            return filepath

        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}/"
        candidates = [
            "primary_doc.xml", "form4.xml", "doc4.xml", "ownership.xml",
            f"{accession}.xml", accession.replace("-", "") + ".xml"
        ]
        for name in candidates:
            url = urljoin(base_path, name)
            try:
                res = self.session.get(url, timeout=self.timeout)
                res.raise_for_status()
                ET.fromstring(res.content)  # validate xml
                with open(filepath, "wb") as f:
                    f.write(res.content)
                return filepath
            except Exception:
                continue
        return None

#最后更新时间6/27/25 17:40

import os
import re
import time
import hashlib
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

class EdgarDownloader:
    def __init__(
        self,
        logger,
        max_retries: int = 3,
        timeout: int = 15,
        request_interval: float = 0.5,
        base_url: str = "https://www.sec.gov",
        cache_dir: str = ".cache"
    ):
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url
        self.request_interval = request_interval
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "quant-ml-lab/1.0 (mmdn814@gmail.com)",
            "Accept": "application/xml, text/xml, text/html"
        }
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def download_latest_form4(self, days_back: int = 7, save_dir: str = "data/form4") -> List[str]:
        os.makedirs(save_dir, exist_ok=True)
        feed_url = self._build_feed_url(days_back)
        entries = self._fetch_atom_feed(feed_url)

        downloaded_files = []
        for idx, entry in enumerate(entries, 1):
            try:
                filepath = self._process_entry(entry, save_dir)
                if filepath:
                    downloaded_files.append(filepath)
                    self.logger.debug(f"[{idx}/{len(entries)}] 下载完成: {os.path.basename(filepath)}")
            except Exception as e:
                self.logger.error(f"[{idx}/{len(entries)}] 处理条目失败: {e}")
            finally:
                time.sleep(self.request_interval)

        self.logger.info(f"✅ 下载完成: 成功 {len(downloaded_files)} / 共 {len(entries)} 个文件")
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
        self.logger.info(f"📡 加载 Feed: {url}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        all_entries = soup.find_all("entry")

        form4_entries = []
        for entry in all_entries:
            try:
                title = entry.title.get_text() if entry.title else ""
                summary = entry.summary.get_text() if entry.summary else ""
                if self._is_form4_entry(title, summary):
                    form4_entries.append(entry)
            except Exception:
                continue

        self.logger.info(f"从 {len(all_entries)} 个条目中筛选出 {len(form4_entries)} 个 Form 4 条目")
        return form4_entries

    def _is_form4_entry(self, title: str, summary: str) -> bool:
        title_lower = title.lower()
        summary_lower = summary.lower()
        indicators = ["form 4", "form4", "statement of changes", "ownership"]
        return any(ind in title_lower or ind in summary_lower for ind in indicators)

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        filing_url = entry.link["href"]
        cik, accession = self._extract_identifiers(filing_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        if os.path.exists(filepath):
            self.logger.debug(f"已存在，跳过: {filename}")
            return filepath

        content = self._download_with_fallback(filing_url, cik, accession)
        if not content:
            self.logger.warning(f"🚫 所有下载方式失败: {filing_url}")
            return None

        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def _download_with_fallback(self, filing_url: str, cik: str, accession: str) -> Optional[bytes]:
        urls = self._get_xml_urls_from_index(filing_url)
        if not urls:
            urls = self._generate_candidate_urls(filing_url, cik, accession)

        for url in urls:
            content = self._try_download(url)
            if content:
                return content
        return None

    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
        try:
            response = self.session.get(filing_url, timeout=self.timeout)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.content, "html.parser")
            urls = []

            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.endswith(".xml"):
                    full_url = urljoin(self.base_url, href) if href.startswith("/") else urljoin(filing_url, href)
                    urls.append(full_url)

            return list(dict.fromkeys(urls))
        except Exception as e:
            self.logger.debug(f"解析 index 页面失败: {e}")
            return []

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}"
        clean_accession = ''.join(filter(str.isdigit, accession))
        return list(dict.fromkeys([
            filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"),
            f"{base_path}/form4.xml",
            f"{base_path}/primary_doc.xml",
            f"{base_path}/wf-form4_{clean_accession}.xml",
            f"{base_path}/xslForm4_{clean_accession}.xml",
            f"{base_path}/doc4.xml"
        ]))

    def _extract_identifiers(self, url: str) -> tuple[str, str]:
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url)
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")
        cik = match.group(1).zfill(10)
        accession = re.sub(r"[^\d\-]", "", match.group(2))
        return cik, accession

    def _try_download(self, url: str) -> Optional[bytes]:
        cache_path = os.path.join(self.cache_dir, hashlib.md5(url.encode()).hexdigest())
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                content = f.read()
                if self._is_valid_form4_xml(content):
                    return content

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    content = resp.content
                    if self._is_valid_form4_xml(content):
                        with open(cache_path, "wb") as f:
                            f.write(content)
                        return content
            except Exception as e:
                self.logger.debug(f"下载失败: {url}，第 {attempt+1} 次，错误: {e}")
                time.sleep(min(2 ** attempt, 10))
        return None

    def _is_valid_form4_xml(self, content: bytes) -> bool:
        if len(content) < 500:
            return False
        text = content.decode("utf-8", errors="ignore").lower()
        return all(tag in text for tag in ["<ownershipdocument>", "<issuer>"]) and "form 4" in text

#最后更新时间：6/27/25 17:57
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
    """
    用于从 SEC EDGAR Atom Feed 下载最近 Form 4 报告的核心类。
    支持自动 URL 修复、内容验证、重试机制与缓存策略。
    """

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
                else:
                    self.logger.warning(f"[{idx}/{len(entries)}] 跳过无效条目")
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

        # ✅ 新判断逻辑：使用 <category term="4"> 判断是否是 Form 4
        form4_entries = []
        for entry in all_entries:
            try:
                categories = entry.find_all("category")
                if any(cat.get("term", "") == "4" for cat in categories):
                    form4_entries.append(entry)
                else:
                    self.logger.debug(f"跳过非 Form 4 条目: {entry.title.text if entry.title else '无标题'}")
            except Exception as e:
                self.logger.warning(f"⚠️ 解析 entry 出错: {e}")
        self.logger.info(f"从 {len(all_entries)} 个条目中筛选出 {len(form4_entries)} 个 Form 4 条目")
        return form4_entries

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        filing_url = entry.link["href"]
        cik, accession = self._extract_identifiers(filing_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        if os.path.exists(filepath):
            self.logger.debug(f"文件已存在，跳过: {filename}")
            return filepath

        content = self._download_with_fallback(filing_url, cik, accession)
        if not content:
            self.logger.warning(f"🚫 所有下载方式失败: {filing_url}")
            return None

        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def _download_with_fallback(self, filing_url: str, cik: str, accession: str) -> Optional[bytes]:
        xml_urls = self._get_xml_urls_from_index(filing_url)

        if not xml_urls:
            xml_urls = self._generate_candidate_urls(filing_url, cik, accession)

        for url in xml_urls:
            content = self._try_download(url)
            if content:
                self.logger.debug(f"✅ 成功下载: {url}")
                return content

        return None

    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
        try:
            self.logger.debug(f"解析 index 页面: {filing_url}")
            response = self.session.get(filing_url, timeout=self.timeout)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.content, "html.parser")
            xml_urls = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.endswith(".xml"):
                    if href.startswith("/"):
                        full_url = self.base_url + href
                    else:
                        full_url = urljoin(filing_url, href)
                    xml_urls.append(full_url)

            return list(dict.fromkeys(xml_urls))
        except Exception as e:
            self.logger.debug(f"解析 index 页面失败: {e}")
            return []

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        clean_accession = ''.join(c for c in accession if c.isdigit())
        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}"

        candidates = [
            filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"),
            f"{base_path}/primary_doc.xml",
            f"{base_path}/form4.xml",
            f"{base_path}/doc4.xml",
            f"{base_path}/{accession}.xml",
            f"{base_path}/wf-form4_{clean_accession}.xml",
            f"{base_path}/xslForm4_{clean_accession}.xml"
        ]
        return list(dict.fromkeys(candidates))

    def _try_download(self, url: str) -> Optional[bytes]:
        cache_key = self._get_cache_key(url)
        cache_path = os.path.join(self.cache_dir, cache_key)

        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                content = f.read()
                if self._is_valid_form4_xml(content):
                    return content

        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"尝试下载 [{attempt+1}/{self.max_retries}]: {url}")
                response = self.session.get(url, timeout=self.timeout)

                if response.status_code == 200:
                    content = response.content
                    if self._is_valid_form4_xml(content):
                        with open(cache_path, "wb") as f:
                            f.write(content)
                        return content
            except Exception as e:
                self.logger.debug(f"下载异常: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(min(2 ** attempt, 10))

        return None

    def _extract_identifiers(self, url: str) -> tuple[str, str]:
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url)
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")

        cik = match.group(1).zfill(10)
        accession_raw = match.group(2)
        accession = re.sub(r'[^\d\-]', '', accession_raw)
        return cik, accession

    def _get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _is_valid_form4_xml(self, content: bytes) -> bool:
        if len(content) < 500:
            return False

        text = content.decode("utf-8", errors="ignore").lower()
        return (
            "<ownershipdocument>" in text and
            "<issuer>" in text and
            ("form 4" in text or "form4" in text)
        )

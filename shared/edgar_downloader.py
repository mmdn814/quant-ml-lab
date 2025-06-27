# ✅ 这是优化后的 `edgar_downloader.py`，具备完整注释、清晰结构和更高的健壮性
#主要特性：
#结构清晰：模块化设计，职责单一。
#URL 容错增强：构造多个候选 URL，并自动尝试。
#内容验证：下载内容必须包含 <ownershipDocument> 和 <issuer> 且长度合理。
#缓存机制：避免重复请求，提升性能与稳定性。
#重试机制：指数退避策略，自动恢复临时失败。
#日志可观测性：详细记录进度与失败原因。
#参数可配置：超时、重试、间隔、缓存目录均支持自定义。
#最后修改时间6/27/25 15:29

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
        """
        初始化下载器

        Args:
            logger: 日志记录器
            max_retries: 最大重试次数
            timeout: 每次请求超时
            request_interval: 请求之间的间隔秒数
            base_url: SEC 基础地址
            cache_dir: 用于存储缓存的目录
        """
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url
        self.request_interval = request_interval
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "quant-ml-lab/1.0 (mmdn814@gmail.com)",
            "Accept": "application/xml, text/xml"
        }

        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def download_latest_form4(self, days_back: int = 7, save_dir: str = "data/form4", max_workers: int = 1) -> List[str]:
        """
        下载最近 N 天的 Form 4 XML 文件

        Args:
            days_back: 回溯天数
            save_dir: 本地保存目录

        Returns:
            下载成功的 XML 文件路径列表
        """
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
                self.logger.error(f"处理条目失败: {e}", exc_info=True)
            finally:
                time.sleep(self.request_interval)

        self.logger.info(f"✅ 下载完成: 成功 {len(downloaded_files)} / 共 {len(entries)} 个文件")
        return downloaded_files

    def _build_feed_url(self, days_back: int) -> str:
        """
        构造 SEC Atom Feed URL

        Args:
            days_back: 回溯天数

        Returns:
            完整 URL
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        params = {
            "action": "getcurrent",
            "type": "4",
            "datea": start_date.strftime("%Y%m%d"),
            "output": "atom"
        }
        return urljoin(self.base_url, "/cgi-bin/browse-edgar?" + urlencode(params))

    def _fetch_atom_feed(self, url: str):
        """请求并解析 Atom Feed"""
        self.logger.info(f"📡 加载 Feed: {url}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        return soup.find_all("entry")

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        """处理单个 Atom 项，尝试下载并保存对应 Form 4 XML"""
        filing_url = entry.link["href"]
        cik, accession = self._extract_identifiers(filing_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        content = self._download_with_fallback(filing_url, cik, accession)
        if not content:
            raise ValueError(f"🚫 所有下载方式失败: {filing_url}")

        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def _download_with_fallback(self, filing_url: str, cik: str, accession: str) -> Optional[bytes]:
        """尝试多种方式下载 Form 4 XML 内容"""
        urls = self._generate_candidate_urls(filing_url, cik, accession)
        for url in urls:
            content = self._try_download(url)
            if content:
                return content
        return None

    def _try_download(self, url: str) -> Optional[bytes]:
        """执行单次下载尝试，包含缓存机制"""
        cache_key = self._get_cache_key(url)
        cache_path = os.path.join(self.cache_dir, cache_key)

        # 优先返回缓存
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return f.read()

        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"尝试下载: {url}")
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200 and self._is_valid_form4_xml(response.content):
                    with open(cache_path, "wb") as f:
                        f.write(response.content)
                    return response.content
            except Exception as e:
                wait = 2 ** attempt
                self.logger.warning(f"下载失败 [{attempt+1}/{self.max_retries}] {url}：{e}，等待 {wait}s")
                time.sleep(wait)
        return None

    def _extract_identifiers(self, url: str) -> tuple[str, str]:
        """
        从 URL 中提取 CIK 和 Accession Number

        Raises:
            ValueError: 无法识别的 URL 格式
        """
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url)
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")
        cik = match.group(1).zfill(10)
        accession_raw = match.group(2)
        accession = ''.join(c for c in accession_raw if c.isdigit())
        if len(accession) != 18:
            raise ValueError(f"非法Accession Number格式: {accession}")
        return cik, accession

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        """
        构造多个候选 XML 下载地址以提升容错性
        """
        clean_accession = ''.join(c for c in accession if c.isdigit())
        return [
            filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"),
            f"{self.base_url}/Archives/edgar/data/{int(cik)}/{clean_accession}/primary_doc.xml"
        ]

    def _get_cache_key(self, url: str) -> str:
        """生成 URL 的唯一缓存键"""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_valid_form4_xml(self, content: bytes) -> bool:
        """验证是否为有效的 Form 4 XML"""
        return b"<ownershipDocument>" in content and b"<issuer>" in content and len(content) > 1024


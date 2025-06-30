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
    简化版 EdgarDownloader：用于下载 SEC Form 4 XML 文件。
    
    ✅ 仅依赖 <category term="4"> 判断是否为 Form 4
    ✅ 不再验证 XML 内容结构
    ✅ 支持 index 页面解析 和 fallback 路径拼接下载
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
        初始化 downloader 对象

        Args:
            logger: 日志记录器对象
            max_retries: 每个链接最多重试次数
            timeout: 每次 HTTP 请求的超时时间（秒）
            request_interval: 每个条目下载之间的等待时间
            base_url: SEC 主站 URL
            cache_dir: 下载缓存目录
        """
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
        """
        主函数：下载最近 N 天内的 Form 4 报告
        
        Args:
            days_back: 回溯天数
            save_dir: XML 文件保存目录

        Returns:
            所有成功保存的文件路径列表
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
                else:
                    self.logger.warning(f"[{idx}/{len(entries)}] 跳过无效条目")
            except Exception as e:
                self.logger.error(f"[{idx}/{len(entries)}] 处理条目失败: {e}")
            finally:
                time.sleep(self.request_interval)

        self.logger.info(f"✅ 下载完成: 成功 {len(downloaded_files)} / 共 {len(entries)} 个文件")
        return downloaded_files

    def _build_feed_url(self, days_back: int) -> str:
        """
        构造 Atom Feed 请求链接，用于获取最近 N 天内的 Form 4 报告

        Args:
            days_back: 回溯天数

        Returns:
            完整 URL 字符串
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        params = {
            "action": "getcurrent",
            "type": "4",  # Form 4 类型
            "datea": start_date.strftime("%Y%m%d"),
            "output": "atom"
        }
        return urljoin(self.base_url, "/cgi-bin/browse-edgar?" + urlencode(params))

    def _fetch_atom_feed(self, url: str):
        """
        请求 Atom Feed 并筛选出 <category term="4"> 的 Form 4 报告

        Args:
            url: Feed 页面 URL

        Returns:
            所有 Form 4 类型的 entry 列表
        """
        self.logger.info(f"📡 加载 Feed: {url}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        entries = soup.find_all("entry")

        # ✅ 只保留 <category term="4"> 的条目
        form4_entries = [e for e in entries if e.find("category", {"term": "4"})]
        self.logger.info(f"🎯 共 {len(entries)} 个条目，筛选出 {len(form4_entries)} 个 Form 4")
        return form4_entries

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        """
        处理单个 Form 4 entry，下载并保存 XML 文件

        Args:
            entry: 单个 <entry> 节点
            save_dir: 本地保存目录

        Returns:
            成功保存的文件路径，或 None
        """
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
        """
        尝试多种 URL 下载 XML 文件（index 页面 + fallback 路径）

        Returns:
            下载到的 XML 内容，或 None
        """
        xml_urls = self._get_xml_urls_from_index(filing_url)
        if not xml_urls:
            xml_urls = self._generate_candidate_urls(filing_url, cik, accession)

        for url in xml_urls:
            content = self._try_download(url)
            if content:
                return content
        return None

    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
        """
        尝试解析 index 页面，提取 XML 文件真实路径

        Returns:
            所有找到的 XML 下载链接
        """
        try:
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
        except Exception:
            return []

    def _extract_identifiers(self, url: str) -> tuple[str, str]:
        """
        从 URL 中提取 CIK 和 accession number
        
        Raises:
            ValueError: 如果格式不匹配
        """
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url)
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")
        cik = match.group(1).zfill(10)
        accession = re.sub(r'[^\d\-]', '', match.group(2))
        return cik, accession

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        """
        在无法解析 index 页时，拼出所有常见 Form 4 XML 文件名作为候选链接
        """
        clean_accession = ''.join(c for c in accession if c.isdigit())
        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}"
        return list(dict.fromkeys([
            filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"),
            f"{base_path}/primary_doc.xml",
            f"{base_path}/form4.xml",
            f"{base_path}/doc4.xml",
            f"{base_path}/{accession}.xml",
            f"{base_path}/wf-form4_{clean_accession}.xml",
            f"{base_path}/xslForm4_{clean_accession}.xml"
        ]))

    def _try_download(self, url: str) -> Optional[bytes]:
        """
        单链接下载，支持缓存和最多 N 次重试

        Returns:
            成功的二进制内容或 None
        """
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, cache_key)

        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return f.read()

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    content = response.content
                    with open(cache_path, "wb") as f:
                        f.write(content)
                    return content
            except Exception:
                time.sleep(min(2 ** attempt, 10))  # 指数退避
        return None

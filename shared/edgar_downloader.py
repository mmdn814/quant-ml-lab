import os
import re
import time
import hashlib
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET # Import for XML validation


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
        # Log the total number of entries to process
        self.logger.info(f"📥 即将下载 Form 4 文件数: {len(entries)}")

        for idx, entry in enumerate(entries, 1):
            try:
                filepath = self._process_entry(entry, save_dir)
                if filepath:
                    downloaded_files.append(filepath)
                    self.logger.debug(f"[{idx}/{len(entries)}] 下载完成: {os.path.basename(filepath)}")
                else:
                    self.logger.warning(f"[{idx}/{len(entries)}] 跳过无效或无法下载的条目")
            except Exception as e:
                self.logger.error(f"[{idx}/{len(entries)}] 处理条目失败: {e}", exc_info=True) # Print detailed stack trace
            finally:
                time.sleep(self.request_interval)

        self.logger.info(f"✅ 下载完成: 成功 {len(downloaded_files)} / 共 {len(entries)} 个文件")
        return downloaded_files

    def _build_feed_url(self, days_back: int) -> str:
        """
        Constructs the Atom Feed request URL to get Form 4 reports from the last N days.

        Args:
            days_back: Number of days to look back.

        Returns:
            Full URL string.
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        params = {
            "action": "getcurrent",
            "type": "4",  # Form 4 type
            "datea": start_date.strftime("%Y%m%d"),
            "output": "atom"
        }
        return urljoin(self.base_url, "/cgi-bin/browse-edgar?" + urlencode(params))

    def _fetch_atom_feed(self, url: str):
        """
        Requests the Atom Feed and filters out Form 4 reports with <category term="4">.

        Args:
            url: Feed page URL.

        Returns:
            List of all Form 4 type entries.
        """
        self.logger.info(f"📡 加载 Feed: {url}")
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status() # Check for HTTP errors
            soup = BeautifulSoup(response.content, "xml")
            entries = soup.find_all("entry")

            # ✅ Only keep entries with <category term="4">
            form4_entries = [e for e in entries if e.find("category", {"term": "4"})]
            self.logger.info(f"🎯 共 {len(entries)} 个条目，筛选出 {len(form4_entries)} 个 Form 4")
            return form4_entries
        except requests.exceptions.RequestException as e:
            self.logger.error(f"加载 Feed 失败: {url}，错误: {e}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"解析 Feed 失败: {url}，错误: {e}", exc_info=True)
            return []

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        """
        Processes a single Form 4 entry, downloads and saves the XML file.

        Args:
            entry: Single <entry> node.
            save_dir: Local save directory.

        Returns:
            Path to the successfully saved file, or None.
        """
        filing_url = entry.link["href"]
        try:
            cik, accession = self._extract_identifiers(filing_url)
        except ValueError as e:
            self.logger.warning(f"🚫 无法从 filing URL 提取标识符，跳过: {filing_url}，错误: {e}")
            return None

        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        if os.path.exists(filepath):
            # This can be extended to re-download if the cached file is found invalid
            # For now, it skips if the file exists, as the primary validation is during download
            self.logger.debug(f"文件已存在，跳过: {filename}")
            return filepath

        content = self._download_with_fallback(filing_url, cik, accession)
        if not content:
            self.logger.warning(f"🚫 所有下载方式失败，无法获取 XML 内容: {filing_url}")
            return None

        try:
            with open(filepath, "wb") as f:
                f.write(content)
            return filepath
        except IOError as e:
            self.logger.error(f"🚫 写入文件失败: {filepath}，错误: {e}")
            return None

    def _download_with_fallback(self, filing_url: str, cik: str, accession: str) -> Optional[bytes]:
        """
        Attempts to download the XML file from multiple URLs (index page + fallback paths).

        Returns:
            Downloaded XML content, or None.
        """
        xml_urls = self._get_xml_urls_from_index(filing_url)
        if not xml_urls:
            # If no XML URLs were extracted from the index page, generate candidate URLs
            xml_urls = self._generate_candidate_urls(filing_url, cik, accession)

        # Ensure there is at least one URL to try, even fallback might be empty
        if not xml_urls:
            self.logger.warning(f"无法为 {filing_url} 生成任何候选 XML 下载链接。")
            return None

        for url in xml_urls:
            content = self._try_download(url)
            if content:
                return content
        return None

    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
        """
        尝试解析 index 页面，提取 XML 文件真实路径。
        修改：更智能地处理从索引页获取的XML URL，确保它直接位于归档路径下，
        去除可能存在的子目录路径，如 "xslF345X05/"。

        Returns:
            所有找到的 XML 下载链接
        """
        try:
            response = self.session.get(filing_url, timeout=self.timeout)
            if response.status_code != 200:
                self.logger.debug(f"访问索引页失败: {filing_url}，状态码: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, "html.parser") 
            xml_urls = []

            # Extract CIK and Accession from the filing_url to construct the expected base path
            # Example filing_url: https://www.sec.gov/Archives/edgar/data/17313/000001731325000061/0000017313-25-000061-index.htm
            filing_url_parts = filing_url.split('/')
            
            try:
                # Find the "data" segment and then CIK and Accession
                data_idx = filing_url_parts.index('data')
                cik_from_url = filing_url_parts[data_idx + 1]
                accession_from_url = filing_url_parts[data_idx + 2]
                # Construct the direct base path for the XML files
                # This should be the path where primary XMLs usually reside
                expected_base_archive_path = urljoin(self.base_url, 
                                                     f"/Archives/edgar/data/{cik_from_url}/{accession_from_url}/")
            except (ValueError, IndexError):
                self.logger.warning(f"无法从 filing URL {filing_url} 提取 CIK 和 Accession，无法确定预期XML基路径。将使用 filing_url 的基路径作为回退。")
                # Fallback: if CIK/Accession cannot be extracted from the URL structure, use the base of the filing URL itself.
                # This might still lead to subdirectories if the filing_url itself contains them.
                parsed_filing_url = urlparse(filing_url)
                expected_base_archive_path = f"{parsed_filing_url.scheme}://{parsed_filing_url.netloc}{os.path.dirname(parsed_filing_url.path)}/"


            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Look for links ending in .xml and containing "form" (heuristic to exclude stylesheets like .xsl)
                # Convert href to lowercase for robust matching
                if href.lower().endswith(".xml") and "form" in href.lower():
                    # Get the actual filename from the href (e.g., wk-form4_1750708963.xml from xslF345X05/wk-form4_1750708963.xml)
                    xml_filename = os.path.basename(href) 

                    # Construct the full URL directly under the expected base archive path.
                    # This explicitly removes any intermediate directories from the href.
                    full_url = urljoin(expected_base_archive_path, xml_filename)
                    xml_urls.append(full_url)

            # Use dict.fromkeys to remove duplicates and convert back to list
            return list(dict.fromkeys(xml_urls))
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"尝试解析索引页 {filing_url} 时发生网络错误: {e}")
            return []
        except Exception as e:
            self.logger.debug(f"解析索引页 {filing_url} 时发生未知错误: {e}")
            return []

    def _extract_identifiers(self, url: str) -> tuple[str, str]:
        """
        Extracts CIK and accession number from the URL.
        
        Raises:
            ValueError: If the format does not match.
        """
        # Modified regex to more precisely match the accession number, especially before the final '-index.htm'
        match = re.search(r"data/(\d+)/([0-9\-]+)/?", url) 
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")
        cik = match.group(1).zfill(10) # Ensure CIK is 10 digits, padded with leading zeros
        # Accession number is usually 18 digits. Remove non-digit and non-hyphen characters,
        # but preserve hyphens for the original structure to match file naming conventions.
        # SEC's accession number format is YYYYMMDD-XXXXXX-XXXXX, here we retain hyphens.
        accession_raw = match.group(2)
        accession = re.sub(r'[^0-9\-]', '', accession_raw) 
        # Example: 0001127602-25-017854
        return cik, accession

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        """
        When the index page cannot be parsed, constructs all common Form 4 XML filenames as candidate links.
        """
        # Clean the accession number, keeping only digits for filename construction
        clean_accession = ''.join(c for c in accession if c.isdigit())
        # Construct the base path, converting CIK to int to remove leading zeros, then back to string
        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}"
        
        candidate_urls = [
            # 1. Try directly replacing -index.htm/.html with .xml in the index page URL
            filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"),
            # 2. Common generic XML filenames
            f"{base_path}/primary_doc.xml",
            f"{base_path}/form4.xml",
            f"{base_path}/doc4.xml",
            # 3. XML with accession number as filename
            f"{base_path}/{accession}.xml", # Original accession with hyphens
            f"{base_path}/{clean_accession}.xml", # Purely numeric accession
            # 4. Common SEC-generated filename patterns
            f"{base_path}/wf-form4_{clean_accession}.xml",
            f"{base_path}/xslForm4_{clean_accession}.xml",
            f"{base_path}/nc-form4_{clean_accession}.xml", # Another common pattern
            f"{base_path}/e{clean_accession}.xml" # Pattern starting with 'e'
        ]
        # Use dict.fromkeys to remove duplicates and preserve order
        return list(dict.fromkeys(candidate_urls))

    def _try_download(self, url: str) -> Optional[bytes]:
        """
        Downloads a single link, supports caching and up to N retries.
        Adds XML content validity check.

        Returns:
            Successful binary content or None.
        """
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, cache_key)

        # Check cache, if it exists and is valid, return directly
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                content = f.read()
                try:
                    ET.fromstring(content) # Attempt to parse, ensure cached file is valid XML
                    self.logger.debug(f"从缓存加载并验证成功: {os.path.basename(url)}")
                    return content
                except ET.ParseError:
                    self.logger.warning(f"缓存文件 {os.path.basename(url)} XML 格式无效，尝试重新下载。")
                    os.remove(cache_path) # Delete invalid cached file

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status() # Check HTTP status code (4xx, 5xx)

                content = response.content
                # !!! Key modification: Validate XML content before saving !!!
                try:
                    ET.fromstring(content) # Attempt to parse downloaded content, raises ParseError if not valid XML
                except ET.ParseError:
                    self.logger.warning(f"下载文件 {url} XML 格式无效（非良好格式XML），尝试重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(min(2 ** (attempt + 1), 10)) # Exponential backoff, starting from 1 second
                    continue # Skip this loop, go to next retry

                # If XML content is valid, save to cache
                with open(cache_path, "wb") as f:
                    f.write(content)
                return content
            except requests.exceptions.RequestException as e: # Catch requests library errors (network issues, timeouts, HTTP errors, etc.)
                self.logger.warning(f"下载 {url} 失败: {e}，尝试重试 ({attempt + 1}/{self.max_retries})")
                time.sleep(min(2 ** (attempt + 1), 10)) # Exponential backoff, starting from 1 second
            except Exception as e: # Catch other unknown errors
                self.logger.error(f"下载 {url} 时发生未知错误: {e}，尝试重试 ({attempt + 1}/{self.max_retries})", exc_info=True)
                time.sleep(min(2 ** (attempt + 1), 10))
        
        self.logger.error(f"达到最大重试次数，无法成功下载并验证 {url}")
        return None


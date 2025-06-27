# ✅ 修复后的 `edgar_downloader.py` - 解决 XML 文件定位问题/claude
# 主要修复：
# 1. 改进 XML 文件 URL 构造策略
# 2. 先解析 index 页面获取实际的 XML 文件名
# 3. 增加更多候选 URL 模式
# 4. 改进错误处理和日志记录
# 最后修改时间: 6/27/25

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
            "Accept": "application/xml, text/xml, text/html"
        }

        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def download_latest_form4(self, days_back: int = 7, save_dir: str = "data/form4", max_workers: int = 1) -> List[str]:
        """
        下载最近 N 天的 Form 4 XML 文件

        Args:
            days_back: 回溯天数
            save_dir: 本地保存目录
            max_workers: 并发数（暂未使用）

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
        """请求并解析 Atom Feed，过滤出真正的 Form 4 条目"""
        self.logger.info(f"📡 加载 Feed: {url}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        all_entries = soup.find_all("entry")
        
        # 过滤出真正的 Form 4 条目
        form4_entries = []
        for entry in all_entries:
            try:
                # 检查条目标题和摘要是否包含 Form 4 相关信息
                title = entry.title.get_text() if entry.title else ""
                summary = entry.summary.get_text() if entry.summary else ""
                
                # Form 4 的特征：标题包含 "4"，摘要包含 "Form 4" 或相关关键词
                if self._is_form4_entry(title, summary):
                    form4_entries.append(entry)
                else:
                    self.logger.debug(f"跳过非 Form 4 条目: {title}")
            except Exception as e:
                self.logger.debug(f"解析条目时出错: {e}")
                continue
        
        self.logger.info(f"从 {len(all_entries)} 个条目中筛选出 {len(form4_entries)} 个 Form 4 条目")
        return form4_entries

    def _process_entry(self, entry, save_dir: str) -> Optional[str]:
        """处理单个 Atom 项，尝试下载并保存对应 Form 4 XML"""
        filing_url = entry.link["href"]
        cik, accession = self._extract_identifiers(filing_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        # 如果文件已存在，跳过下载
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
        """尝试多种方式下载 Form 4 XML 内容"""
        self.logger.debug(f"开始下载: CIK={cik}, Accession={accession}")
        
        # 首先尝试从 index 页面解析实际的 XML 文件名
        xml_urls = self._get_xml_urls_from_index(filing_url)
        
        # 如果解析失败，使用传统的候选 URL 方法
        if not xml_urls:
            self.logger.debug("Index 页面解析失败，使用候选 URL 策略")
            xml_urls = self._generate_candidate_urls(filing_url, cik, accession)
        else:
            self.logger.debug(f"从 Index 页面解析出 {len(xml_urls)} 个候选 URL")
        
        # 记录所有候选 URL
        for i, url in enumerate(xml_urls):
            self.logger.debug(f"候选 URL {i+1}: {url}")
        
        for i, url in enumerate(xml_urls):
            self.logger.debug(f"尝试候选 URL {i+1}/{len(xml_urls)}: {url}")
            content = self._try_download(url)
            if content:
                self.logger.debug(f"✅ 成功下载: {url}")
                return content
            else:
                self.logger.debug(f"❌ 下载失败: {url}")
        
        self.logger.debug(f"所有 {len(xml_urls)} 个候选 URL 均下载失败")
        return None

    def _is_form4_entry(self, title: str, summary: str) -> bool:
        """
        判断 Atom Feed 条目是否为 Form 4
        
        Args:
            title: 条目标题
            summary: 条目摘要
            
        Returns:
            是否为 Form 4 条目
        """
        title_lower = title.lower()
        summary_lower = summary.lower()
        
        # Form 4 的明确标识
        form4_indicators = [
            "form 4", "form4", "statement of changes in beneficial ownership"
        ]
        
        # 检查标题和摘要
        for indicator in form4_indicators:
            if indicator in title_lower or indicator in summary_lower:
                return True
        
        # 额外检查：标题包含数字 "4" 且摘要包含相关关键词
        if "4" in title and any(keyword in summary_lower for keyword in [
            "beneficial ownership", "insider", "section 16", "ownership"
        ]):
            return True
            
        return False

    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
    def _get_xml_urls_from_index(self, filing_url: str) -> List[str]:
        """
        从 filing index 页面解析出实际的 XML 文件链接
        """
        try:
            self.logger.debug(f"解析 index 页面: {filing_url}")
            response = self.session.get(filing_url, timeout=self.timeout)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, "html.parser")
            xml_urls = []
            
            # 方法1: 查找文档表格中的 XML 文件
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 3:  # 通常有 Seq, Description, Document, Type, Size 列
                        for cell in cells:
                            link = cell.find("a", href=True)
                            if link and link["href"].endswith(".xml"):
                                href = link["href"]
                                if href.startswith("/"):
                                    full_url = self.base_url + href
                                else:
                                    full_url = urljoin(filing_url, href)
                                xml_urls.append(full_url)
            
            # 方法2: 查找所有 XML 链接
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.endswith(".xml"):
                    if href.startswith("/"):
                        full_url = self.base_url + href
                    else:
                        full_url = urljoin(filing_url, href)
                    xml_urls.append(full_url)
            
            # 去重并优先选择主文档
            xml_urls = list(dict.fromkeys(xml_urls))
            
            # 根据文件名排序，优先选择可能的主文档
            def get_priority(url):
                filename = url.split("/")[-1].lower()
                if "primary" in filename or "form4" in filename:
                    return 0
                elif filename.startswith("wf-form4") or filename.startswith("xslform4"):
                    return 1
                elif filename == "form4.xml":
                    return 2
                else:
                    return 3
            
            xml_urls.sort(key=get_priority)
            
            self.logger.debug(f"从 index 页面找到 {len(xml_urls)} 个 XML 候选")
            return xml_urls
            
        except Exception as e:
            self.logger.debug(f"解析 index 页面失败: {e}")
            return []

    def _try_download(self, url: str) -> Optional[bytes]:
        """执行单次下载尝试，包含缓存机制"""
        cache_key = self._get_cache_key(url)
        cache_path = os.path.join(self.cache_dir, cache_key)

        # 优先返回缓存
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
                        # 缓存有效内容
                        with open(cache_path, "wb") as f:
                            f.write(content)
                        return content
                    else:
                        self.logger.debug(f"内容验证失败: {url}")
                else:
                    self.logger.debug(f"HTTP {response.status_code}: {url}")
                    
            except Exception as e:
                wait = min(2 ** attempt, 10)  # 最大等待 10 秒
                self.logger.debug(f"下载异常 [{attempt+1}/{self.max_retries}] {url}：{e}")
                if attempt < self.max_retries - 1:
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
        # 清理 accession number，保留数字和连字符
        accession = re.sub(r'[^\d\-]', '', accession_raw)
        
        return cik, accession

    def _generate_candidate_urls(self, filing_url: str, cik: str, accession: str) -> List[str]:
        """
        构造多个候选 XML 下载地址以提升容错性
        """
        clean_accession = ''.join(c for c in accession if c.isdigit())
        base_path = f"{self.base_url}/Archives/edgar/data/{int(cik)}/{accession}"
        
        candidates = []
        
        # 方法1: 简单替换 index 后缀
        candidates.append(filing_url.replace("-index.htm", ".xml").replace("-index.html", ".xml"))
        
        # 方法2: 基于真实的 SEC 文件结构
        # 从 filing_url 中提取路径信息
        url_parts = filing_url.split('/')
        if len(url_parts) >= 2:
            accession_part = url_parts[-2]  # 获取 accession number 部分
            
            # 常见的 Form 4 XML 文件名模式
            candidates.extend([
                f"{base_path}/primary_doc.xml",
                f"{base_path}/form4.xml",
                f"{base_path}/{accession_part}.xml",
                f"{base_path}/wf-form4_{clean_accession}.xml",
                f"{base_path}/xslForm4_{clean_accession}.xml",
                f"{base_path}/doc4.xml"
            ])
        
        # 方法3: 基于 index 文件名构造
        index_filename = filing_url.split('/')[-1]
        if index_filename.endswith('-index.htm') or index_filename.endswith('-index.html'):
            # 移除 -index 后缀，添加 .xml
            base_filename = index_filename.replace('-index.htm', '').replace('-index.html', '')
            candidates.append(f"{base_path}/{base_filename}.xml")
        
        # 去重
        return list(dict.fromkeys(candidates))

    def _get_cache_key(self, url: str) -> str:
        """生成 URL 的唯一缓存键"""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_valid_form4_xml(self, content: bytes) -> bool:
        """验证是否为有效的 Form 4 XML"""
        if len(content) < 500:  # 太短的内容不太可能是有效的 Form 4
            return False
        
        content_str = content.decode('utf-8', errors='ignore').lower()
        
        # 检查必要的 XML 标签
        required_tags = ["<ownershipdocument>", "<issuer>"]
        for tag in required_tags:
            if tag not in content_str:
                return False
        
        # 检查是否确实是 Form 4
        form4_indicators = ["form4", "form 4", "ownershipdocument"]
        if not any(indicator in content_str for indicator in form4_indicators):
            return False
            
        return True

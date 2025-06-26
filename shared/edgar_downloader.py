# edgar_downloader.py
# 优化版本：增强稳定性、边缘情况处理和日志可观测性

import os
import re
import requests
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class EdgarDownloader:
    def __init__(self, logger, max_retries=3):
        """
        初始化下载器
        :param logger: 日志记录器
        :param max_retries: 单文件下载最大重试次数
        """
        self.logger = logger
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)",
            "Accept": "application/xml, text/xml"
        }
        # SEC推荐的最小请求间隔(秒)
        self.request_interval = 0.5  

    def download_latest_form4(self, days_back=3):
        """
        下载最近N天的Form 4申报文件
        :param days_back: 回溯天数
        :return: 成功下载的文件路径列表
        """
        save_dir = os.path.abspath("data/form4")
        os.makedirs(save_dir, exist_ok=True)
        
        self.logger.info(f"🚀 开始获取最近 {days_back} 天的Form 4申报文件")
        downloaded_files = []

        try:
            # 1. 获取Atom Feed列表
            feed_url = self._build_feed_url(days_back)
            entries = self._fetch_atom_feed(feed_url)
            if not entries:
                self.logger.warning("未获取到任何申报条目")
                return []

            # 2. 处理每个申报条目
            for idx, entry in enumerate(entries, 1):
                try:
                    filepath = self._process_entry(entry, save_dir)
                    if filepath:
                        downloaded_files.append(filepath)
                        self.logger.debug(f"进度: {idx}/{len(entries)}")
                except Exception as e:
                    self.logger.error(f"处理条目失败: {str(e)}", exc_info=True)
                finally:
                    time.sleep(self.request_interval)

        except Exception as e:
            self.logger.critical(f"主流程异常: {str(e)}", exc_info=True)
        
        self.logger.info(f"🎉 完成! 成功下载 {len(downloaded_files)}/{len(entries)} 个文件")
        return downloaded_files

    def _build_feed_url(self, days_back):
        """构建Atom Feed URL（考虑时区）"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        return (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcurrent&type=4"
            f"&datea={start_date.strftime('%Y%m%d')}"
            "&output=atom"
        )

    def _fetch_atom_feed(self, url):
        """获取并解析Atom Feed"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            
            # 验证内容类型
            if "application/atom+xml" not in resp.headers.get("Content-Type", ""):
                raise ValueError("无效的Atom Feed内容类型")
                
            soup = BeautifulSoup(resp.text, "xml")
            return soup.find_all("entry")
        except Exception as e:
            self.logger.error(f"获取Atom Feed失败: {str(e)}")
            raise

    def _process_entry(self, entry, save_dir):
        """处理单个Atom条目"""
        if not entry.link:
            raise ValueError("条目缺少link标签")
            
        # 1. 提取元数据
        filing_url = entry.link["href"]
        company_name = entry.find("title").text.split(" - ")[0]
        updated = entry.find("updated").text if entry.find("updated") else "N/A"
        
        # 2. 构建XML文件URL（兼容新旧格式）
        xml_url = self._normalize_xml_url(filing_url)
        if not xml_url:
            raise ValueError("无法规范化XML URL")
            
        # 3. 下载文件
        cik, accession = self._extract_identifiers(xml_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)
        
        self.logger.info(
            f"下载 {company_name} 的申报 (CIK:{cik}, 更新:{updated})"
        )
        
        content = self._download_with_retry(xml_url)
        if content:
            with open(filepath, "wb") as f:
                f.write(content)
            return filepath
        return None

    def _normalize_xml_url(self, filing_url):
        """规范化XML文件URL（处理历史格式变化）"""
        base_url = filing_url.replace("-index.htm", "").replace("-index.html", "")
        
        # 尝试常见格式
        for ext in ["/primary_doc.xml", ".xml", "/index.xml"]:
            test_url = base_url + ext
            if self._validate_url(test_url):
                return test_url
        return None

    def _validate_url(self, url):
        """验证URL格式有效性"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc, result.path])
        except:
            return False

    def _extract_identifiers(self, url):
        """从URL提取CIK和Accession Number"""
        match = re.search(r"data/(\d{10})/([^/]+?)(/|\.xml|$)", url)
        if not match:
            raise ValueError(f"无法从URL提取标识符: {url}")
        cik, accession = match.groups()[:2]
        return cik.zfill(10), accession.replace("-", "")

    def _download_with_retry(self, url):
        """带重试机制的文件下载"""
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    timeout=15,
                    stream=True  # 流式下载避免大文件内存问题
                )
                resp.raise_for_status()
                
                # 验证内容
                if resp.status_code == 200 and "xml" in resp.headers.get("Content-Type", "").lower():
                    return resp.content
                    
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    self.logger.warning(
                        f"下载失败 (尝试 {attempt + 1}/{self.max_retries}), "
                        f"{wait_time}秒后重试: {url}"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"下载失败 (最终尝试): {url}, 错误: {str(e)}"
                    )
        return None

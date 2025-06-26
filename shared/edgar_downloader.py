import os
import re
import requests
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class EdgarDownloader:
    def __init__(self, logger, max_retries=3):
        self.logger = logger
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": "QuantMLLabBot/1.0 (Contact: mmdn814@gmail.com)",
            "Accept": "application/xml, text/xml"
        }
        self.request_interval = 0.5  # SEC推荐最小间隔

    def download_latest_form4(self, days_back=3):
        """
        下载最近N天的Form 4申报文件
        """
        save_dir = os.path.abspath("data/form4")
        os.makedirs(save_dir, exist_ok=True)
        
        self.logger.info(f"🚀 获取最近 {days_back} 天的Form 4申报")
        downloaded_files = []

        try:
            feed_url = self._build_feed_url(days_back)
            entries = self._fetch_atom_feed(feed_url)
            if not entries:
                self.logger.warning("❌ 未获取到任何条目")
                return []

            for idx, entry in enumerate(entries, 1):
                try:
                    filepath = self._process_entry(entry, save_dir)
                    if filepath:
                        downloaded_files.append(filepath)
                        self.logger.debug(f"[{idx}/{len(entries)}] 成功下载")
                except Exception as e:
                    self.logger.error(f"处理条目失败: {e}", exc_info=True)
                finally:
                    time.sleep(self.request_interval)

        except Exception as e:
            self.logger.critical(f"主流程异常: {e}", exc_info=True)
        
        self.logger.info(f"✅ 下载完成: 成功 {len(downloaded_files)} / 共 {len(entries)} 个文件")
        return downloaded_files

    def _build_feed_url(self, days_back):
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        return (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcurrent&type=4"
            f"&datea={start_date.strftime('%Y%m%d')}"
            "&output=atom"
        )

    def _fetch_atom_feed(self, url):
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()

            if "xml" not in resp.headers.get("Content-Type", ""):
                raise ValueError("非XML响应，可能被SEC限制")

            soup = BeautifulSoup(resp.text, "xml")
            return soup.find_all("entry")
        except Exception as e:
            self.logger.error(f"❌ 获取 Atom Feed 失败: {e}")
            raise

    def _process_entry(self, entry, save_dir):
        if not entry.link:
            raise ValueError("❌ 条目缺少 link 标签")

        filing_url = entry.link["href"]
        company_name = entry.find("title").text.split(" - ")[0]
        updated = entry.find("updated").text if entry.find("updated") else "N/A"

        xml_url = self._normalize_xml_url(filing_url)
        if not xml_url:
            raise ValueError("❌ 无法生成 XML 链接")

        cik, accession = self._extract_identifiers(xml_url)
        filename = f"{cik}_{accession}.xml"
        filepath = os.path.join(save_dir, filename)

        self.logger.info(f"📥 下载 {company_name} (CIK:{cik}) 文件")
        content = self._download_with_retry(xml_url)
        if content:
            with open(filepath, "wb") as f:
                f.write(content)
            return filepath
        return None

    def _normalize_xml_url(self, filing_url):
        base_url = filing_url.replace("-index.htm", "").replace("-index.html", "")

        for ext in ["/primary_doc.xml", ".xml", "/index.xml"]:
            test_url = base_url + ext
            if self._validate_url(test_url):
                return test_url
        return None

    def _validate_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc, result.path])
        except:
            return False

    def _extract_identifiers(self, url):
        """
        提取 CIK 和 Accession 编号，处理如：
        https://www.sec.gov/Archives/edgar/data/9631/000183988225034027/0001839882-25-034027/primary_doc.xml
        """
        try:
            match = re.search(r"/data/(\d{1,10})/(\d{18})/", url)
            if not match:
                raise ValueError("URL 格式不符，无法提取标识符")

            cik_raw, accession = match.groups()
            cik = cik_raw.zfill(10)

            if not re.fullmatch(r"\d{18}", accession):
                raise ValueError(f"Accession 格式非法: {accession}")

            return cik, accession
        except Exception as e:
            raise ValueError(f"无法从URL提取标识符: {url}，错误: {str(e)}")

    def _download_with_retry(self, url):
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15, stream=True)
                resp.raise_for_status()

                if resp.status_code == 200 and "xml" in resp.headers.get("Content-Type", "").lower():
                    return resp.content
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    self.logger.warning(f"第 {attempt+1} 次重试失败: {e}，等待 {wait}s")
                    time.sleep(wait)
                else:
                    self.logger.error(f"🚫 下载失败: {url}，错误: {e}")
        return None

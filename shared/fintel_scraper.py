#完整抓取逻辑（Insider Ownership、Institutional Ownership、Float、Short Interest）
#高容错（重试机制、单票失败不影响整体）
#日志记录
#防止风控（每票延时控制）
#清晰注释，方便你未来扩展

import requests
from bs4 import BeautifulSoup
import time
from shared.logger import setup_logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class FintelScraper:
    def __init__(self, logger=None):
        self.base_url = "https://fintel.io/s/us/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        self.logger = logger or setup_logger("fintel_scraper")
        self.session = self._create_session()

    def _create_session(self):
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        return session

    def fetch_fintel_data(self, ticker):
        """
        核心抓取函数：输入 ticker，输出结构评分所需四大指标
        """
        url = self.base_url + ticker.lower()
        try:
            resp = self.session.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')

            # 核心信息抓取 (需与 Fintel 页面结构保持同步)
            data = {
                'insider': self._extract_metric(soup, 'Insider Ownership'),
                'institutional': self._extract_metric(soup, 'Institutional Ownership'),
                'float': self._extract_metric(soup, 'Float'),
                'short_interest': self._extract_metric(soup, 'Short Interest')
            }
            time.sleep(0.5)  # 每票延时，防止风控
            return data

        except Exception as e:
            self.logger.warning(f"⚠ 抓取 Fintel 数据失败: {ticker} - {e}")
            return None

    def _extract_metric(self, soup, keyword):
        """
        通用字段提取逻辑：根据 Fintel 页面上的指标名称进行提取
        """
        try:
            row = soup.find('td', string=keyword)
            if not row:
                return None
            value_td = row.find_next_sibling('td')
            value_text = value_td.text.strip()

            # 根据指标类型进行不同处理
            if '%' in value_text:
                return float(value_text.replace('%', '').replace(',', '').strip())
            elif 'M' in value_text:
                return float(value_text.replace('M', '').replace(',', '').strip())
            else:
                return float(value_text.replace(',', '').strip())
        except Exception as e:
            self.logger.warning(f"⚠ 解析 {keyword} 失败: {e}")
            return None

    def compute_structure_score(self, data):
        """
        结构评分 (满分3分)
        """
        score = 0
        if data['insider'] is not None and data['insider'] > 60:
            score += 1
        if data['institutional'] is not None and data['institutional'] < 20:
            score += 1
        if data['float'] is not None and data['float'] < 20:
            score += 1
        return score

    def compute_squeeze_score(self, data):
        """
        Squeeze评分 (满分4分)
        """
        score = 0
        if data['short_interest'] is not None:
            if data['short_interest'] > 10:
                score += 1
            if data['short_interest'] > 20:
                score += 1
        if data['float'] is not None and data['float'] < 20:
            score += 1
        if data['insider'] is not None and data['insider'] > 60:
            score += 1
        return score

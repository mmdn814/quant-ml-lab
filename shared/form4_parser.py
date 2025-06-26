# shared/form4_parser.py
# 解析 Form 4 XML 文件，提取 CEO 买入交易数据

import os
import xml.etree.ElementTree as ET
from typing import List, Dict

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, file_paths: List[str]) -> List[Dict]:
        """提取 CEO 的买入交易记录"""
        results = []

        for path in file_paths:
            try:
                tree = ET.parse(path)
                root = tree.getroot()

                issuer_cik = self._safe_find_text(root, ".//issuerCik")
                insider_name = self._safe_find_text(root, ".//reportingOwner//rptOwnerName")

                transactions = root.findall(".//nonDerivativeTransaction")
                for txn in transactions:
                    code = self._safe_find_text(txn, ".//transactionCoding/transactionCode")
                    if code not in ("P",):  # 只保留 Purchase
                        continue

                    shares = float(self._safe_find_text(txn, ".//transactionAmounts/transactionShares/value", 0))
                    price = float(self._safe_find_text(txn, ".//transactionAmounts/transactionPricePerShare/value", 0))
                    date = self._safe_find_text(txn, ".//transactionDate/value")
                    filing_url = self._construct_filing_url(path)

                    results.append({
                        "ticker": issuer_cik,
                        "insider_name": insider_name,
                        "shares": int(shares),
                        "price": float(price),
                        "trade_date": date,
                        "filing_url": filing_url,
                        "transaction_type": "Purchase"
                    })

            except Exception as e:
                self.logger.warning(f"⚠️ 解析失败: {path} -> {str(e)}")

        return results

    def _safe_find_text(self, root, xpath: str, default=None):
        try:
            el = root.find(xpath)
            return el.text.strip() if el is not None and el.text else default
        except:
            return default

    def _construct_filing_url(self, file_path: str) -> str:
        """从文件路径构建 EDGAR 查看链接"""
        # 示例路径: data/form4/0000320193_000110465923063014.xml
        base = os.path.basename(file_path)
        cik, accession = base.replace(".xml", "").split("_")
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.html"


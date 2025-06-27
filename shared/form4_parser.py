from pathlib import Path

form4_parser_code = """
# shared/form4_parser.py
# 功能：用于解析 SEC Form 4 XML 文件，提取 CEO 买入交易记录
# 依赖：仅依赖标准库，兼容新版 edgar_downloader 的文件结构
#最后修改时间6/27/25 15:33

import xml.etree.ElementTree as ET
from typing import List, Dict
import os

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, filepaths: List[str]) -> List[Dict]:
        \"\"\"从多个 Form 4 文件中提取 CEO 买入交易记录\"\"\"
        transactions = []
        for path in filepaths:
            try:
                txns = self._parse_form4_file(path)
                transactions.extend(txns)
            except Exception as e:
                self.logger.error(f"❌ 解析失败: {path} | 错误: {str(e)}", exc_info=True)
        return transactions

    def _parse_form4_file(self, filepath: str) -> List[Dict]:
        \"\"\"解析单个 Form 4 XML 文件，提取 CEO 买入交易\"\"\"
        tree = ET.parse(filepath)
        root = tree.getroot()

        ns = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}
        issuer_node = root.find(".//issuer")
        if issuer_node is None:
            raise ValueError("找不到 issuer 节点")

        ticker = issuer_node.findtext("issuerTradingSymbol") or "UNKNOWN"
        issuer_cik = issuer_node.findtext("issuerCik") or "UNKNOWN"

        owner_node = root.find(".//reportingOwner")
        insider_name = owner_node.findtext("reportingOwnerId/rptOwnerName") or "UNKNOWN"
        is_ceo = "ceo" in insider_name.lower()

        if not is_ceo:
            return []

        # 获取非衍生证券交易
        result = []
        for txn in root.findall(".//nonDerivativeTransaction"):
            code = txn.findtext("transactionCoding/transactionCode", "").strip()
            if code != "P":  # 'P' 代表买入
                continue

            shares = txn.findtext("transactionAmounts/transactionShares/value")
            price = txn.findtext("transactionAmounts/transactionPricePerShare/value")
            date = txn.findtext("transactionDate/value")

            if not all([shares, price, date]):
                continue

            result.append({
                "ticker": ticker,
                "insider_name": insider_name,
                "shares": int(float(shares)),
                "price": float(price),
                "trade_date": date,
                "filing_url": self._construct_edgar_link_from_path(filepath),
                "transaction_type": "Purchase"
            })

        return result

    def _construct_edgar_link_from_path(self, filepath: str) -> str:
        \"\"\"根据本地文件路径构造 EDGAR 网页链接\"\"\"
        filename = os.path.basename(filepath)
        try:
            cik, accession = filename.replace(".xml", "").split("_")
            clean_accession = ''.join(c for c in accession if c.isdigit())
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/primary_doc.xml"
        except Exception:
            return "N/A"
"""

file_path = "/mnt/data/form4_parser.py"
with open(file_path, "w") as f:
    f.write(form4_parser_code)

file_path

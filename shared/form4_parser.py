# shared/form4_parser.py
# 功能：解析 Form 4 XML 文件中的 CEO 买入信息

import xml.etree.ElementTree as ET
from typing import List
import os

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, file_paths: List[str]) -> List[dict]:
        ceo_trades = []

        for path in file_paths:
            try:
                tree = ET.parse(path)
                root = tree.getroot()

                # issuer / reporting owner
                issuer_elem = root.find(".//issuer")
                if issuer_elem is None:
                    continue
                ticker_elem = issuer_elem.find("issuerTradingSymbol")
                cik_elem = issuer_elem.find("issuerCik")
                if ticker_elem is None or cik_elem is None:
                    continue

                ticker = ticker_elem.text
                cik = cik_elem.text

                # 判断是否为CEO
                is_ceo = False
                insider_name = None
                for owner in root.findall(".//reportingOwner"):
                    title = owner.findtext(".//officerTitle", "").lower()
                    if "ceo" in title:
                        is_ceo = True
                        insider_name = owner.findtext(".//rptOwnerName", "Unknown")
                        break

                if not is_ceo:
                    continue

                # 提取非衍生证券的买入记录
                for tx in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
                    code = tx.findtext(".//transactionCode", "")
                    if code != "P":  # P = Purchase, 其他如 G=Gift、A=Award等
                        continue

                    shares = float(tx.findtext(".//transactionShares/value", "0"))
                    price = float(tx.findtext(".//transactionPricePerShare/value", "0"))
                    date = tx.findtext(".//transactionDate/value", "")
                    filing_url = self._construct_edgar_link_from_path(path)

                    ceo_trades.append({
                        "ticker": ticker,
                        "insider_name": insider_name,
                        "shares": int(shares),
                        "price": round(price, 2),
                        "trade_date": date,
                        "filing_url": filing_url,
                        "transaction_type": "Purchase"
                    })

            except Exception as e:
                self.logger.warning(f"❌ 解析失败: {path}, 错误: {e}")
                continue

        return ceo_trades

    def _construct_edgar_link_from_path(self, filepath: str) -> str:
        """根据本地路径还原EDGAR原始链接"""
        filename = os.path.basename(filepath)
        cik, accession = filename.replace(".xml", "").split("_")
        accession_dash = accession[:10] + "-" + accession[10:12] + "-" + accession[12:]
        return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/primary_doc.xml"



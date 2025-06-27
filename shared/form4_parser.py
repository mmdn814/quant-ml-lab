# 最后修改时间：6/27/25 16:07
# 功能：解析 SEC Form 4 XML 文件，提取 CEO 的非衍生公开市场买入记录

import os
import xml.etree.ElementTree as ET
from typing import List, Dict

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, filepaths: List[str]) -> List[Dict]:
        """从多个 Form 4 XML 文件中提取 CEO 的公开市场买入记录"""
        results = []

        for path in filepaths:
            try:
                trades = self._parse_single_file(path)
                results.extend(trades)
            except Exception as e:
                self.logger.warning(f"⚠️ 解析失败: {path}，错误: {e}")
        return results

    def _parse_single_file(self, path: str) -> List[Dict]:
        """解析单个 XML 文件，提取所有 CEO 买入记录"""
        tree = ET.parse(path)
        root = tree.getroot()

        # 验证是否为 Form 4 文件
        if root.tag != "ownershipDocument":
            raise ValueError("不是有效的 Form 4 文件")

        issuer_ticker = root.findtext("issuer/issuerTradingSymbol", default=None)
        if not issuer_ticker:
            raise ValueError("未找到 issuerTradingSymbol")

        insider_name = root.findtext("reportingOwner/reportingOwnerId/rptOwnerName", default="N/A")
        is_ceo = self._is_ceo(root)
        if not is_ceo:
            return []

        trade_date = root.findtext("periodOfReport", default="")

        results = []
        for txn in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
            code = txn.findtext("transactionCoding/transactionCode", default="")
            if code != "P":  # 仅提取买入（Purchase）交易
                continue

            txn_price = txn.findtext("transactionPricePerShare/value")
            txn_shares = txn.findtext("transactionShares/value")

            try:
                shares = int(float(txn_shares))
                price = float(txn_price)
            except (TypeError, ValueError):
                continue

            result = {
                "ticker": issuer_ticker,
                "insider_name": insider_name,
                "shares": shares,
                "price": price,
                "trade_date": trade_date,
                "filing_url": self._construct_edgar_link_from_path(path),
                "transaction_type": "Purchase"
            }
            results.append(result)

        return results

    def _is_ceo(self, root: ET.Element) -> bool:
        """判断是否为 CEO 报告人"""
        positions = root.findall("reportingOwner/reportingOwnerRelationship/officerTitle")
        for pos in positions:
            if "ceo" in pos.text.lower():
                return True
        return False

    def _construct_edgar_link_from_path(self, filepath: str) -> str:
        """从文件路径构建 EDGAR 原始链接"""
        filename = os.path.basename(filepath).replace(".xml", "")
        try:
            cik, accession = filename.split("_")
            accession = ''.join(filter(str.isdigit, accession))
            if len(accession) != 18:
                raise ValueError(f"无效的 Accession Number: {accession}")
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/primary_doc.xml"
        except Exception as e:
            self.logger.warning(f"构建 EDGAR URL 失败: {filepath} | 错误: {e}")
            return "N/A"

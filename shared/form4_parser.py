# 最后修改时间：6/30/25 17:07
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
            except ET.ParseError as e: # 明确捕获XML解析错误
                self.logger.warning(f"⚠️ XML解析失败: {os.path.basename(path)}，错误: {e}")
            except ValueError as e: # 明确捕获自定义数据提取错误
                self.logger.warning(f"⚠️ 数据提取失败: {os.path.basename(path)}，错误: {e}")
            except Exception as e: # 捕获其他未知错误
                self.logger.warning(f"⚠️ 解析失败（未知错误）: {os.path.basename(path)}，错误: {e}")
        return results

    def _parse_single_file(self, path: str) -> List[Dict]:
        """解析单个 XML 文件，提取所有 CEO 买入记录"""
        tree = ET.parse(path)
        root = tree.getroot()

        # 验证是否为 Form 4 文件
        # 注意：这里假设根标签一定是 "ownershipDocument"。如果SEC有其他根标签，可能需要调整。
        if root.tag != "ownershipDocument":
            raise ValueError(f"不是有效的 Form 4 文件，根标签为: {root.tag}")

        issuer_ticker = root.findtext("issuer/issuerTradingSymbol", default=None)
        if not issuer_ticker:
            # 某些Form 4可能没有ticker，这可能是正常情况或需要根据实际情况决定是否跳过
            self.logger.debug(f"文件 {os.path.basename(path)} 未找到 issuerTradingSymbol")
            return [] # 如果没有ticker，则无法进行后续处理

        insider_name = root.findtext("reportingOwner/reportingOwnerId/rptOwnerName", default="N/A")
        
        # 判断是否为 CEO 报告人
        is_ceo = self._is_ceo(root)
        if not is_ceo:
            return []

        trade_date = root.findtext("periodOfReport", default="")
        if not trade_date:
            self.logger.debug(f"文件 {os.path.basename(path)} 未找到 periodOfReport")
            trade_date = "N/A"

        results = []
        # 查找非衍生品交易表
        for txn in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
            code = txn.findtext("transactionCoding/transactionCode", default="").strip().upper()
            if code != "P":  # 仅提取买入（Purchase）交易, 'P'代表购买
                continue

            # 交易价格和股数可能缺失或为空
            txn_price_str = txn.findtext("transactionPricePerShare/value")
            txn_shares_str = txn.findtext("transactionShares/value")

            try:
                shares = int(float(txn_shares_str)) if txn_shares_str else 0
                price = float(txn_price_str) if txn_price_str else 0.0
                
                # 检查是否为有效的买入交易（股数和价格都应大于0）
                if shares <= 0 or price <= 0:
                    self.logger.debug(f"文件 {os.path.basename(path)} 中发现非正股数或价格的买入交易，跳过。Shares: {shares}, Price: {price}")
                    continue

            except (TypeError, ValueError) as e:
                self.logger.debug(f"文件 {os.path.basename(path)} 中交易价格或股数转换失败: Price='{txn_price_str}', Shares='{txn_shares_str}', 错误: {e}")
                continue # 数据格式不正确，跳过此交易

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
        # 考虑多种可能表示CEO的职位字符串，并转换为小写进行匹配
        ceo_keywords = ["chief executive officer", "ceo", "president and chief executive officer", 
                        "chief exective officer", "principal executive officer"] # 常见拼写错误也考虑
        
        # 查找所有 officerTitle 或 officerTitleText 标签
        # SEC文档中可能使用officerTitleText代替officerTitle
        positions = root.findall("reportingOwner/reportingOwnerRelationship/officerTitle")
        positions.extend(root.findall("reportingOwner/reportingOwnerRelationship/officerTitleText"))

        for pos in positions:
            if pos.text: # 确保文本内容不为空
                if any(keyword in pos.text.lower() for keyword in ceo_keywords):
                    return True
        return False

    def _construct_edgar_link_from_path(self, filepath: str) -> str:
        """从文件路径构建 EDGAR 原始链接"""
        filename = os.path.basename(filepath).replace(".xml", "")
        try:
            cik, accession_full = filename.split("_")
            # 原始 accession_full 可能是 000001731325000061 这样的，需要转换回 SEC URL 格式
            # SEC URL 格式通常是 YYYYMMDD-NN-XXXXXX，或只有纯数字
            # 从文件命名来看，accession_full 是纯数字，需要处理成 000...0061 这种形式
            
            # SEC filing URL 的 accession format: 0001127602-25-017854
            # 您的文件名格式: {cik}_{pure_digits_accession}
            # 我们需要把 pure_digits_accession 转换为 SEC URL 格式

            # 假设 filepath 中的 accession 是纯数字，需要重新格式化
            # 例如 "000001731325000061" -> "0000017313-25-000061" (这是一个示例转换逻辑，可能需要根据实际SEC URL模式调整)
            
            # 重新从 filename 中提取 accession number，并尝试适配 SEC 格式
            # 这是从 Form 4 自身 URL 格式反推的，通常是 YYYYMMDD + document_sequence_number
            # 考虑到您下载的 filing_url 格式是：
            # https://www.sec.gov/Archives/edgar/data/8858/000112760225017854/0001127602-25-017854-index.htm
            # 这里的 000112760225017854 是 accession number 的纯数字形式
            # 我们需要将其转换为 0001127602-25-017854 这种带横线的形式
            
            # SEC accession number 的标准格式是 10位 CIK + 2位年 + 8位月日 + 6位序列号
            # 或者更常见的是 10位数字 + 8位日期 + 6位序列号
            # filing_url 中的 accession_number 是 0001127602-25-017854
            # 对应的文件名中是 000112760225017854
            
            # 如果文件名中的 accession_full 是纯数字且长度为18 (例如000112760225017854)
            if len(accession_full) == 18 and accession_full.isdigit():
                # 转换为 SEC 档案路径中的格式：前10位-2位-后6位
                sec_accession = f"{accession_full[:10]}-{accession_full[10:12]}-{accession_full[12:]}"
            else:
                # 否则，使用原始的 accession_full
                sec_accession = accession_full 

            # 注意：这里我们尝试指向 primary_doc.xml，因为这是最标准的报告XML文件
            # 但实际上，如果下载时是从其他XML文件名（如form4.xml, wk-form4_xxx.xml）下载的，
            # 那么这个链接可能会导致404，如果需要精确匹配，需要调整存储文件名
            # 当前的 _download_with_fallback 会尝试多种，而这里只提供一个通用链接。
            # 对于展示给用户的链接，通常 primary_doc.xml 是一个不错的选择
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{sec_accession}/primary_doc.xml"
        except Exception as e:
            self.logger.warning(f"构建 EDGAR URL 失败: {filepath} | 错误: {e}")
            return "N/A"


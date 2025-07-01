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
            self.logger.debug(f"开始解析文件: {os.path.basename(path)}")
            try:
                trades = self._parse_single_file(path)
                results.extend(trades)
            except ET.ParseError as e: # 明确捕获XML解析错误
                self.logger.warning(f"⚠️ XML解析失败: {os.path.basename(path)}，错误: {e}")
            except ValueError as e: # 明确捕获自定义数据提取错误
                self.logger.warning(f"⚠️ 数据提取失败: {os.path.basename(path)}，错误: {e}")
            except Exception as e: # 捕获其他未知错误
                self.logger.warning(f"⚠️ 解析失败（未知错误）: {os.path.basename(path)}，错误: {e}")
            self.logger.debug(f"文件 {os.path.basename(path)} 解析完成。")
        return results

    def _parse_single_file(self, path: str) -> List[Dict]:
        """解析单个 XML 文件，提取所有 CEO 买入记录"""
        tree = ET.parse(path)
        root = tree.getroot()

        # 验证是否为 Form 4 文件
        if root.tag != "ownershipDocument":
            self.logger.debug(f"文件 {os.path.basename(path)} 不是有效的 Form 4 文件，根标签为: {root.tag}。跳过。")
            raise ValueError(f"不是有效的 Form 4 文件，根标签为: {root.tag}")

        issuer_ticker = root.findtext("issuer/issuerTradingSymbol", default=None)
        if not issuer_ticker:
            self.logger.debug(f"文件 {os.path.basename(path)} 未找到 issuerTradingSymbol。跳过。")
            return [] # 如果没有ticker，则无法进行后续处理

        insider_name = root.findtext("reportingOwner/reportingOwnerId/rptOwnerName", default="N/A")
        
        # 判断是否为 CEO 报告人
        is_ceo = self._is_ceo(root)
        self.logger.debug(f"文件 {os.path.basename(path)} - 报告人: {insider_name}, 是否为CEO: {is_ceo}")
        if not is_ceo:
            self.logger.debug(f"文件 {os.path.basename(path)} 报告人 {insider_name} 不是CEO。跳过。")
            return []

        trade_date = root.findtext("periodOfReport", default="")
        if not trade_date:
            self.logger.debug(f"文件 {os.path.basename(path)} 未找到 periodOfReport。使用N/A。")
            trade_date = "N/A"

        results = []
        # 查找非衍生品交易表
        non_derivative_transactions = root.findall("nonDerivativeTable/nonDerivativeTransaction")
        self.logger.debug(f"文件 {os.path.basename(path)} 找到 {len(non_derivative_transactions)} 条非衍生品交易。")

        for idx, txn in enumerate(non_derivative_transactions):
            code = txn.findtext("transactionCoding/transactionCode", default="").strip().upper()
            self.logger.debug(f"文件 {os.path.basename(path)} - 交易 {idx+1}: TransactionCode={code}")

            if code != "P":  # 仅提取买入（Purchase）交易, 'P'代表购买
                self.logger.debug(f"文件 {os.path.basename(path)} - 交易 {idx+1}: 非买入交易 ({code})。跳过。")
                continue

            # 交易价格和股数可能缺失或为空
            txn_price_str = txn.findtext("transactionPricePerShare/value")
            txn_shares_str = txn.findtext("transactionShares/value")

            try:
                shares = int(float(txn_shares_str)) if txn_shares_str else 0
                price = float(txn_price_str) if txn_price_str else 0.0
                
                # 检查是否为有效的买入交易（股数和价格都应大于0）
                if shares <= 0 or price <= 0:
                    self.logger.debug(f"文件 {os.path.basename(path)} - 交易 {idx+1}: 股数或价格非正值。Shares: {shares}, Price: {price}。跳过。")
                    continue

            except (TypeError, ValueError) as e:
                self.logger.debug(f"文件 {os.path.basename(path)} - 交易 {idx+1}: 交易价格或股数转换失败: Price='{txn_price_str}', Shares='{txn_shares_str}', 错误: {e}。跳过。")
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
            self.logger.debug(f"文件 {os.path.basename(path)} - 交易 {idx+1}: 成功识别为CEO买入。")

        return results

    def _is_ceo(self, root: ET.Element) -> bool:
        """
        判断是否为 CEO 报告人。
        增强识别逻辑，使用更灵活的关键词匹配。
        """
        # 扩展 CEO 关键词列表，包括常见缩写、变体和复合职位
        ceo_keywords = [
            "chief executive officer", "ceo", "president and chief executive officer", 
            "chief exective officer", "principal executive officer", "co-chief executive officer",
            "chief operating officer and chief executive officer", # 常见复合职位
            "chief executive officer and president",
            "chief executive officer and chairman",
            "principal officer", # 有时也指CEO
            "c.e.o." # 考虑带点的缩写
        ]
        
        # 查找所有 officerTitle 或 officerTitleText 标签
        positions = root.findall("reportingOwner/reportingOwnerRelationship/officerTitle")
        positions.extend(root.findall("reportingOwner/reportingOwnerRelationship/officerTitleText"))

        found_titles = []
        for pos in positions:
            if pos.text: # 确保文本内容不为空
                normalized_title = pos.text.lower().strip() # 转换为小写并去除首尾空格
                found_titles.append(pos.text) # 记录原始标题

                # 使用更灵活的匹配：只要标题中包含任何一个关键词，就认为是CEO
                if any(keyword in normalized_title for keyword in ceo_keywords):
                    self.logger.debug(f"识别到CEO职位关键词: '{pos.text}' (匹配到: {normalized_title})")
                    return True
        
        self.logger.debug(f"未识别到CEO职位关键词。找到的职位: {found_titles}")
        return False

    def _construct_edgar_link_from_path(self, filepath: str) -> str:
        """从文件路径构建 EDGAR 原始链接"""
        filename = os.path.basename(filepath).replace(".xml", "")
        try:
            cik, accession_full = filename.split("_")
            
            if len(accession_full) == 18 and accession_full.isdigit():
                sec_accession = f"{accession_full[:10]}-{accession_full[10:12]}-{accession_full[12:]}"
            else:
                sec_accession = accession_full 

            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{sec_accession}/primary_doc.xml"
        except Exception as e:
            self.logger.warning(f"构建 EDGAR URL 失败: {filepath} | 错误: {e}")
            return "N/A"


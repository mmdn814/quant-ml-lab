# shared/form4_parser.py
# 最后修改时间：2025-06-25
# 功能：解析本地 Form 4 XML 文件，提取 CEO 买入交易记录

import xml.etree.ElementTree as ET
import os


class Form4Parser:
    def __init__(self, logger):
        """
        初始化解析器
        :param logger: 外部传入的日志记录器
        """
        self.logger = logger

    def extract_ceo_purchases(self, file_paths):
        """
        解析一批 XML 文件，提取 CEO 买入记录（非期权、非赠与）
        :param file_paths: 本地 Form 4 XML 文件路径列表
        :return: 包含结构化买入记录的列表
        """
        results = []

        for file_path in file_paths:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                # 解析公司信息
                issuer = root.find('issuer')
                if issuer is None:
                    continue
                ticker = issuer.findtext('issuerTradingSymbol')
                company_name = issuer.findtext('issuerName')

                # 获取 insider 信息
                insider = root.find('reportingOwner')
                if insider is None:
                    continue
                insider_name = insider.findtext('reportingOwnerName')
                title = insider.findtext('reportingOwnerRelationship/officerTitle')

                # 只关注 CEO 的记录
                if not title or 'CEO' not in title.upper():
                    continue

                # 遍历非衍生证券的买入交易
                transactions = root.findall('nonDerivativeTable/nonDerivativeTransaction')
                for txn in transactions:
                    txn_code = txn.findtext('transactionCoding/transactionCode')
                    if txn_code != 'P':  # 只保留 "Purchase" 类型
                        continue

                    shares = float(txn.findtext('transactionAmounts/transactionShares/value', '0'))
                    price = float(txn.findtext('transactionAmounts/transactionPricePerShare/value', '0'))
                    date = txn.findtext('transactionDate/value')

                    if shares == 0 or price == 0:
                        continue

                    filing_url = self._build_filing_url(file_path)

                    results.append({
                        'ticker': ticker,
                        'company': company_name,
                        'insider_name': insider_name,
                        'shares': int(shares),
                        'price': round(price, 2),
                        'trade_date': date,
                        'filing_url': filing_url
                    })

            except Exception as e:
                self.logger.warning(f"❌ 解析失败: {file_path} | 错误: {e}")
                continue

        return results

    def _build_filing_url(self, local_path):
        """
        从本地文件名构造 EDGAR 原始链接
        :param local_path: 本地文件路径
        :return: EDGAR 可访问链接
        """
        try:
            filename = os.path.basename(local_path)
            parts = filename.replace('.xml', '').split('-')
            acc_no = ''.join(parts)
            cik = parts[0]
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}-index.html"
        except Exception:
            return ""

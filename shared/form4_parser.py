#解析 SEC Form 4 原始 XML 文件
#只筛选出 CEO 买入行为（P - Purchase）
#结构化数据供后续评分与推送使用

import os
import xml.etree.ElementTree as ET
from datetime import datetime

class Form4Parser:
    """
    解析本地已下载好的 Form 4 XML 文件，提取 CEO 买入记录。
    """

    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, file_list):
        """
        解析文件列表，返回符合条件的 CEO 买入列表
        """
        ceo_buys = []

        for file_path in file_list:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                # 提取基本元信息
                reporting_owner = root.findtext('.//reportingOwner/reportingOwnerId/rptOwnerName')
                ticker = root.findtext('.//issuer/issuerTradingSymbol')
                filing_date = root.findtext('.//periodOfReport')

                # 确认职位信息
                is_ceo = False
                for relationship in root.findall('.//reportingOwner/reportingOwnerRelationship/officerTitle'):
                    title = relationship.text.upper()
                    if 'CEO' in title or 'CHIEF EXECUTIVE' in title:
                        is_ceo = True
                        break
                if not is_ceo:
                    continue  # 非 CEO 直接跳过

                # 查找每一笔交易明细
                for txn in root.findall('.//nonDerivativeTable/nonDerivativeTransaction'):
                    txn_code = txn.findtext('transactionCoding/transactionCode')
                    if txn_code != 'P':  # 只关注买入 (P - Purchase)
                        continue

                    shares = txn.findtext('transactionAmounts/transactionShares')
                    price = txn.findtext('transactionAmounts/transactionPricePerShare')
                    trade_date = txn.findtext('transactionDate/value')

                    # 有些老报告缺少字段，跳过异常
                    if not all([shares, price, trade_date]):
                        continue

                    filing_url = self.build_edgar_url(file_path)

                    ceo_buys.append({
                        'ticker': ticker,
                        'insider_name': reporting_owner,
                        'trade_date': trade_date,
                        'shares': int(float(shares)),
                        'price': round(float(price), 2),
                        'filing_url': filing_url
                    })

            except Exception as e:
                self.logger.warning(f"解析失败: {file_path} -> {e}")
                continue

        self.logger.info(f"成功提取 CEO 买入记录数量: {len(ceo_buys)}")
        return ceo_buys

    def build_edgar_url(self, local_path):
        """
        根据本地文件路径还原 EDGAR 在线链接（供推送时使用）
        """
        filename = os.path.basename(local_path)
        accession = filename.replace('.xml', '')
        accession_formatted = accession.replace('-', '')
        url = f"https://www.sec.gov/Archives/edgar/data/{accession_formatted}/primary-doc.xml"
        return url


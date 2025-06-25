# form4_parser.py
# 最后修改时间：2025-06-25
# 功能：解析 SEC Form 4 XML 文件，提取 CEO 的股票购买记录

from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, downloaded_files):
        """
        解析 Form 4 XML 文件列表，提取所有 CEO 的股票购买记录（P 类型交易）
        :param downloaded_files: 本地下载的 Form 4 XML 文件路径列表
        :return: 结构化记录列表，每条包含 ticker、insider_name、title、日期、股数、价格、链接等
        """
        result = []
        for file_path in downloaded_files:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                # 获取内幕人姓名
                reporting_owner = root.find('.//reportingOwner/reportingOwnerId/rptOwnerName')
                insider_name = reporting_owner.text.strip() if reporting_owner is not None else ""

                # 获取交易股票代码
                issuer_ticker = root.find('.//issuer/issuerTradingSymbol')
                ticker = issuer_ticker.text.strip() if issuer_ticker is not None else ""

                # 获取申报日期
                filing_date_elem = root.find('.//periodOfReport')
                filing_date = datetime.strptime(filing_date_elem.text.strip(), "%Y-%m-%d") if filing_date_elem is not None else None

                # 获取头衔，判断是否为 CEO
                officer_title_elem = root.find('.//reportingOwner/reportingOwnerRelationship/officerTitle')
                title = officer_title_elem.text.strip().lower() if officer_title_elem is not None else ""

                # 跳过非 CEO 记录（模糊匹配 "ceo"）
                if "ceo" not in title:
                    continue

                # 遍历所有 non-derivative 的购买记录
                for txn in root.findall('.//nonDerivativeTable/nonDerivativeTransaction'):
                    txn_code = txn.find('./transactionCoding/transactionCode')
                    if txn_code is None or txn_code.text != "P":
                        continue  # 只保留 P - Purchase 类型交易

                    # 交易日期
                    trade_date_elem = txn.find('./transactionDate/value')
                    trade_date = datetime.strptime(trade_date_elem.text.strip(), "%Y-%m-%d") if trade_date_elem is not None else None

                    # 容忍 trade_date 比 filing_date 最多早 7 天（处理延迟申报）
                    if trade_date and filing_date:
                        if trade_date < filing_date - timedelta(days=7):
                            continue

                    # 成交股数
                    shares_elem = txn.find('./transactionAmounts/transactionShares/value')
                    shares = int(float(shares_elem.text.strip())) if shares_elem is not None else 0

                    # 成交价格
                    price_elem = txn.find('./transactionAmounts/transactionPricePerShare/value')
                    price = round(float(price_elem.text.strip()), 2) if price_elem is not None else 0.0

                    # 构造网页链接（便于用户点击）
                    filing_url = self.build_filing_url(file_path)

                    record = {
                        "ticker": ticker,
                        "insider_name": insider_name,
                        "title": title,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "shares": shares,
                        "price": price,
                        "filing_url": filing_url
                    }
                    result.append(record)

            except Exception as e:
                self.logger.error(f"解析文件失败 {file_path}: {e}")
                continue

        return result

    def build_filing_url(self, file_path):
        """
        将本地文件路径转为 EDGAR 报告网页地址
        示例：data/insider_ceo/20240612/0001654954-24-006789.xml -> 
        https://www.sec.gov/Archives/edgar/data/0001654954/000165495424006789/0001654954-24-006789.xml
        """
        parts = file_path.split('/')
        if len(parts) < 3:
            return ""
        accession = parts[-1].replace('.xml', '')
        cik = accession.split('-')[0].zfill(10)
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.xml"
        return url


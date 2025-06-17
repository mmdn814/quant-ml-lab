#将 trade_date < filing_date - timedelta(days=3) 改为 days=7，更好容忍实际申报与交易存在 7 天以内的时间差；
#解析 SEC Form 4 原始 XML 文件
#只筛选出 CEO 买入行为，（模糊包含）
#结构化数据供后续评分与推送使用
#保持了日志、异常捕获、解析逻辑完整性；


from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

class Form4Parser:
    def __init__(self, logger):
        self.logger = logger

    def extract_ceo_purchases(self, downloaded_files):
        """
        解析 Form 4 文件，提取 CEO 买入记录
        """
        result = []
        for file_path in downloaded_files:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                # 解析基础信息
                reporting_owner = root.find('.//reportingOwner/reportingOwnerId/rptOwnerName')
                insider_name = reporting_owner.text.strip() if reporting_owner is not None else ""

                issuer_ticker = root.find('.//issuer/issuerTradingSymbol')
                ticker = issuer_ticker.text.strip() if issuer_ticker is not None else ""

                filing_date_elem = root.find('.//periodOfReport')
                filing_date = datetime.strptime(filing_date_elem.text.strip(), "%Y-%m-%d") if filing_date_elem is not None else None

                officer_title_elem = root.find('.//reportingOwner/reportingOwnerRelationship/officerTitle')
                title = officer_title_elem.text.strip().lower() if officer_title_elem is not None else ""

                # 只保留 CEO 角色（模糊包含）
                if "ceo" not in title:
                    continue

                # 遍历每笔交易明细
                for txn in root.findall('.//nonDerivativeTable/nonDerivativeTransaction'):
                    txn_code = txn.find('./transactionCoding/transactionCode')
                    if txn_code is None or txn_code.text != "P":
                        continue  # 只保留 P - Purchase

                    # 交易日期
                    trade_date_elem = txn.find('./transactionDate/value')
                    trade_date = datetime.strptime(trade_date_elem.text.strip(), "%Y-%m-%d") if trade_date_elem is not None else None

                    # 增加延迟容忍窗口：允许 trade_date 比 filing_date 最多早 7 天
                    if trade_date and filing_date:
                        if trade_date < filing_date - timedelta(days=7):
                            continue

                    # 成交股数
                    shares_elem = txn.find('./transactionAmounts/transactionShares/value')
                    shares = int(float(shares_elem.text.strip())) if shares_elem is not None else 0

                    # 成交价格
                    price_elem = txn.find('./transactionAmounts/transactionPricePerShare/value')
                    price = round(float(price_elem.text.strip()), 2) if price_elem is not None else 0.0

                    # 构建完整记录
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
        将本地文件路径转回 EDGAR 报告网页地址
        """
        # 示例路径: data/insider_ceo/20240612/0001654954-24-006789.xml
        parts = file_path.split('/')
        if len(parts) < 3:
            return ""
        accession = parts[-1].replace('.xml', '')
        cik = accession.split('-')[0]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.txt"
        return url


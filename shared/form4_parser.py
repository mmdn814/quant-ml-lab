# form4_ceo_selector.py
# 优化版本：增强稳定性、可观测性和扩展性

from dataclasses import dataclass
from typing import List, Dict, Optional
import traceback
from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
from shared.form4_parser import Form4Parser

@dataclass
class CEOTransaction:
    """结构化存储CEO交易数据"""
    ticker: str
    insider_name: str
    shares: int
    price: float
    trade_date: str
    filing_url: str
    transaction_type: str  # 'Purchase'/'Sale'

@dataclass
class FintelMetrics:
    """Fintel数据容器"""
    insider_ownership: Optional[float]
    institutional_ownership: Optional[float]
    float_shares: Optional[float]  # in millions
    short_interest: Optional[float]  # in percentage

class CEOTradeStrategy:
    def __init__(self, logger, days_back: int = 3, top_n: int = 20):
        self.logger = logger
        self.days_back = days_back
        self.top_n = top_n
        self.fintel = FintelScraper(logger)
        self.parser = Form4Parser(logger)

    def run(self):
        """策略主入口"""
        self.logger.info("🚀 启动CEO交易策略")
        
        try:
            # 1. 数据获取层
            transactions = self._fetch_ceo_transactions()
            if not transactions:
                self._notify_no_data("未发现CEO公开市场买入记录")
                return

            # 2. 数据处理层
            enriched_data = self._enrich_with_fintel(transactions)
            save_ceo_trades_to_csv(enriched_data)

            # 3. 分析层
            top_stocks = self._select_top_stocks(enriched_data)

            # 4. 通知层
            self._send_telegram_report(top_stocks)

        except Exception as e:
            self._handle_error(e)

    def _fetch_ceo_transactions(self) -> List[CEOTransaction]:
        """获取CEO交易数据"""
        downloader = EdgarDownloader(self.logger)
        files = downloader.download_latest_form4(days_back=self.days_back)
        self.logger.info(f"下载到{len(files)}份Form4文件")

        if not files:
            self.logger.warning("⚠️ 无Form4文件下载，跳过后续解析")
            return []

        # 加载CIK映射（用于后续扩展）
        cik_mapping = load_latest_cik_mapping()
        if not cik_mapping:
            self.logger.warning("⚠️ 未加载到任何 CIK 映射，后续可能无法反查公司信息")
        else:
            self.logger.debug(f"加载{len(cik_mapping)}条CIK映射")

        raw_transactions = self.parser.extract_ceo_purchases(files)
        return [
            CEOTransaction(
                ticker=t['ticker'],
                insider_name=t['insider_name'],
                shares=t['shares'],
                price=t['price'],
                trade_date=t['trade_date'],
                filing_url=t['filing_url'],
                transaction_type=t.get('transaction_type', 'Purchase')
            ) for t in raw_transactions
        ]

    def _enrich_with_fintel(self, transactions: List[CEOTransaction]) -> List[Dict]:
        """补充Fintel数据"""
        enriched = []
        for t in transactions:
            try:
                metrics = self.fintel.get_fintel_data(t.ticker)
                enriched.append({
                    **t.__dict__,
                    'fintel': FintelMetrics(
                        insider_ownership=metrics.get('insider'),
                        institutional_ownership=metrics.get('institutional'),
                        float_shares=metrics.get('float'),
                        short_interest=metrics.get('short_interest')
                    ),
                    'structure_score': self._calc_structure_score(metrics),
                    'squeeze_score': self._calc_squeeze_score(metrics)
                })
            except Exception as e:
                self.logger.error(f"补充{t.ticker}数据失败: {str(e)}")
                continue
        return enriched

    def _select_top_stocks(self, data: List[Dict]) -> List[Dict]:
        """筛选Top N股票"""
        return sorted(
            [d for d in data if d['transaction_type'] == 'Purchase'],
            key=lambda x: x['shares'],
            reverse=True
        )[:self.top_n]

    @staticmethod
    def _calc_structure_score(metrics: Dict) -> int:
        """计算结构评分"""
        score = 0
        if metrics.get('insider', 0) > 60:
            score += 1
        if metrics.get('institutional', 100) < 20:
            score += 1
        if metrics.get('float', float('inf')) < 20:
            score += 1
        return score

    @staticmethod
    def _calc_squeeze_score(metrics: Dict) -> int:
        """计算轧空评分"""
        score = 0
        short_interest = metrics.get('short_interest', 0)
        if short_interest > 10:
            score += 1
        if short_interest > 20:
            score += 1
        if metrics.get('float', float('inf')) < 20:
            score += 1
        if metrics.get('insider', 0) > 60:
            score += 1
        return score

    def _send_telegram_report(self, stocks: List[Dict]):
        """生成并发送Telegram报告"""
        if not stocks:
            self._notify_no_data("无符合条件的CEO买入记录")
            return

        messages = [f"🔥 *CEO买入警报(前{self.top_n})*"]
        for stock in stocks:
            f = stock['fintel']
            msg = f"""
📈 *Ticker:* `{stock['ticker']}`
👤 *CEO:* {stock['insider_name']}
🧮 *Shares:* +{stock['shares']:,}
💰 *Price:* ${stock['price']:.2f}
🏦 Insider: {f.insider_ownership or 'N/A'}%
🏛 Institutional: {f.institutional_ownership or 'N/A'}%
📊 Float: {f.float_shares or 'N/A'}M
🔻 Short Interest: {f.short_interest or 'N/A'}%
⭐ Structure: {stock['structure_score']}/3
🔥 Squeeze: {stock['squeeze_score']}/4
📅 Date: {stock['trade_date']}
🔗 [EDGAR]({stock['filing_url']}) | [Fintel](https://fintel.io/s/us/{stock['ticker'].lower()})"""
            messages.append(msg)

        send_telegram_message("\n\n".join(messages))

    def _notify_no_data(self, reason: str):
        """发送无数据通知"""
        msg = f"🕵️ 今日无CEO交易数据: {reason}"
        self.logger.warning(msg)
        send_telegram_message(msg)

    def _handle_error(self, error: Exception):
        """统一错误处理"""
        self.logger.error(f"策略执行失败: {str(error)}")
        self.logger.error(traceback.format_exc())
        send_telegram_message(f"💥 CEO策略异常: {str(error)}")

# 使用示例
if __name__ == "__main__":
    logger = setup_logger("ceo_strategy")
    strategy = CEOTradeStrategy(logger, days_back=3, top_n=20)
    strategy.run()

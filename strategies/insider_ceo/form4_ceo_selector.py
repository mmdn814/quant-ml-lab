#该文件是 策略主逻辑模块，主要职责是：
#下载最近几天的 Form 4 文件；
#提取 CEO 买入交易；
#使用 Fintel 获取结构数据；
#计算结构评分 / 轧空评分；
#发送简明推送到 Telegram。
# 功能：运行 CEO 买入策略，包含下载、解析、结构评分、Fintel 数据、Telegram 推送等
# 最后更新时间6/27/25 15:4

from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
from shared.form4_parser import Form4Parser
import traceback

# ============ 结构评分计算 ============
def compute_structure_score(data: dict) -> int:
    """根据 Fintel 数据计算结构评分（0-3）"""
    score = 0
    if data.get('insider') and data['insider'] > 60:
        score += 1
    if data.get('institutional') is not None and data['institutional'] < 20:
        score += 1
    if data.get('float') and data['float'] < 20:
        score += 1
    return score

# ============ 轧空评分计算 ============
def compute_squeeze_score(data: dict) -> int:
    """根据 Fintel 数据计算轧空评分（0-4）"""
    score = 0
    si = data.get('short_interest', 0)
    if si > 10:
        score += 1
    if si > 20:
        score += 1
    if data.get('float') and data['float'] < 20:
        score += 1
    if data.get('insider') and data['insider'] > 60:
        score += 1
    return score

# ============ 策略主函数 ============
def run_ceo_strategy(logger, days_back: int = 7, top_n: int = 20):
    logger.info("🚀 启动 insider_ceo 策略")

    try:
        # 1. 加载 CIK 映射（目前不直接用，但为后续扩展预留）
        cik_mapping = load_latest_cik_mapping()
        logger.info(f"✅ 加载 CIK 映射: {len(cik_mapping)} 条")

        # 2. 下载 Form 4 数据
        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=days_back)
        logger.info(f"📥 下载 Form 4 文件数: {len(downloaded_files)}")

        if not downloaded_files:
            msg = "📭 未发现新的 Form 4 文件"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 3. 解析 CEO 买入交易
        parser = Form4Parser(logger)
        ceo_trades = parser.extract_ceo_purchases(downloaded_files)
        logger.info(f"✅ 识别 CEO 买入记录数: {len(ceo_trades)}")

        if not ceo_trades:
            msg = "📭 未发现 CEO 的公开市场买入记录"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 4. 保存 CSV
        save_ceo_trades_to_csv(ceo_trades, logger)

        # 5. 选取成交股数最多的 top N
        top_stocks = sorted(ceo_trades, key=lambda x: x['shares'], reverse=True)[:top_n]

        # 6. Fintel 数据补全并打分
        fintel = FintelScraper(logger)
        messages = [f"🔥 *今日 CEO 买入前 {top_n} 名*"]

        for stock in top_stocks:
            ticker = stock['ticker']
            try:
                fintel_data = fintel.get_fintel_data(ticker)
                if fintel_data:
                    structure_score = compute_structure_score(fintel_data)
                    squeeze_score = compute_squeeze_score(fintel_data)

                    msg = f"""
📈 *Ticker:* `{ticker}`
👤 *CEO:* {stock['insider_name']}
🧮 *Shares:* {stock['shares']:,}
💰 *Price:* ${stock['price']}
🏦 Insider: {fintel_data['insider']}%
🏛 Institutional: {fintel_data['institutional']}%
📊 Float: {fintel_data['float']}M
🔻 Short Interest: {fintel_data['short_interest']}%
⭐ Structure Score: {structure_score}/3
🔥 Squeeze Score: {squeeze_score}/4
📅 Date: {stock['trade_date']}
🔗 [EDGAR Filing]({stock['filing_url']})
🔗 [Fintel Link](https://fintel.io/s/us/{ticker.lower()})"""
                else:
                    msg = f"⚠ 无法获取 `{ticker}` 的结构数据"

                messages.append(msg)

            except Exception as e:
                logger.error(f"❌ {ticker} 的 Fintel 数据拉取失败: {e}")
                continue

        # 7. 发送 Telegram 通知
        send_telegram_message("\n\n".join(messages))

    except Exception as e:
        logger.error("策略运行异常: " + str(e))
        logger.error(traceback.format_exc())
        send_telegram_message(f"🚨 insider_ceo 策略执行失败: {e}")

# ============ 可直接运行 ============
if __name__ == "__main__":
    logger = setup_logger("insider_ceo")
    run_ceo_strategy(logger, days_back=7, top_n=20)

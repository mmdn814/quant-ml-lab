

from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.form4_parser import Form4Parser
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
import traceback


def compute_structure_score(data):
    score = 0
    if data['insider'] and data['insider'] > 60:
        score += 1
    if data['institutional'] is not None and data['institutional'] < 20:
        score += 1
    if data['float'] and data['float'] < 20:
        score += 1
    return score


def compute_squeeze_score(data):
    score = 0
    if data['short_interest'] and data['short_interest'] > 10:
        score += 1
    if data['short_interest'] and data['short_interest'] > 20:
        score += 1
    if data['float'] and data['float'] < 20:
        score += 1
    if data['insider'] and data['insider'] > 60:
        score += 1
    return score


def run_ceo_strategy(logger):
    logger.info("[启动] insider_ceo 策略开始运行")

    try:
        cik_mapping = load_latest_cik_mapping()
        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=2)

        if not downloaded_files:
            send_telegram_message("😕 未发现新的 Form 4 报告")
            return

        parser = Form4Parser(logger)
        ceo_buys = parser.extract_ceo_purchases(downloaded_files)

        if not ceo_buys:
            send_telegram_message("😕 未发现 CEO 公开市场买入记录")
            return

        save_ceo_trades_to_csv(ceo_buys)

        # 选出买入最多前 20 的 CEO 买入
        top_stocks = sorted(ceo_buys, key=lambda x: x['shares'], reverse=True)[:20]

        fintel = FintelScraper(logger)

        messages = ["🚨 *今日 CEO 买入数量前 20 名 (EDGAR)*"]
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
🧮 *Shares:* +{stock['shares']:,}
💰 *Buy Price:* ${stock['price']}
🏦 Insider: {fintel_data['insider']}%
🏦 Institutional: {fintel_data['institutional']}%
🧮 Float: {fintel_data['float']}M
🔻 Short Interest: {fintel_data['short_interest']}%
⭐ Structure Score: {structure_score}/3
🔥 Squeeze Score: {squeeze_score}/4
📅 Date: {stock['trade_date']}
🔗 [EDGAR Filing]({stock['filing_url']})
🔗 [Fintel Link](https://fintel.io/s/us/{ticker.lower()})"""
                else:
                    msg = f"""
📈 *Ticker:* `{ticker}`
⚠ 无法获取结构评分数据"""

                messages.append(msg)

            except Exception as e:
                logger.error(f"❌ {ticker} Fintel 解析异常: {e}")
                continue

        send_telegram_message("\n\n".join(messages))

    except Exception as e:
        logger.error("运行异常: " + str(e))
        logger.error(traceback.format_exc())
        send_telegram_message(f"🚨 insider_ceo 策略执行异常: {e}")

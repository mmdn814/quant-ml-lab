# form4_ceo_selector.py
# 最后修改时间：2025-06-25
# 功能：运行 CEO 买入策略，包含下载、解析、结构评分、Fintel 数据、Telegram 推送等

from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
from shared.form4_parser import Form4Parser  # ✅ 修复导入错误
import traceback

# ============ 结构评分计算 ============
def compute_structure_score(data):
    score = 0
    if data['insider'] and data['insider'] > 60:
        score += 1
    if data['institutional'] is not None and data['institutional'] < 20:
        score += 1
    if data['float'] and data['float'] < 20:
        score += 1
    return score

# ============ squeeze 评分计算 ============
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

# ============ 策略主逻辑 ============
def run_ceo_strategy(logger):
    logger.info("[启动] insider_ceo 策略开始运行")

    try:
        # 1. 加载最新 CIK 映射（用于后续 Ticker 与 CIK 映射）
        cik_mapping = load_latest_cik_mapping()
        logger.info(f"[DEBUG] 成功加载 CIK 映射: 共 {len(cik_mapping)} 条")

        # 2. 下载近 N 天 Form 4 文件（使用 SEC API 提升稳定性）
        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=7, use_sec_api=True)
        logger.info(f"[DEBUG] 下载到 Form4 文件数量: {len(downloaded_files)}")

        if not downloaded_files:
            msg = "😕 未发现新的 Form 4 报告"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 3. 解析出 CEO 买入交易（非期权、非赠与）
        parser = Form4Parser(logger)
        ceo_buys = parser.extract_ceo_purchases(downloaded_files)
        logger.info(f"[DEBUG] CEO 买入记录数: {len(ceo_buys)}")

        if not ceo_buys:
            msg = "😕 未发现 CEO 公开市场买入记录"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 4. 保存结构化结果（完整记录）
        save_ceo_trades_to_csv(ceo_buys, logger=logger)

        # 5. 对买入记录按成交股数排序，选前 top N
        top_stocks = sorted(ceo_buys, key=lambda x: x['shares'], reverse=True)[:20]

        # 6. 获取结构评分、Fintel 数据
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

        # 7. 最终推送到 Telegram
        send_telegram_message("\n\n".join(messages))

    except Exception as e:
        logger.error("运行异常: " + str(e))
        logger.error(traceback.format_exc())
        send_telegram_message(f"🚨 insider_ceo 策略执行异常: {e}")

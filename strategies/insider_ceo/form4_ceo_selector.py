# ✅ 文件：strategies/insider_ceo/form4_ceo_selector.py
# 功能：运行 CEO 买入策略，包含下载、解析、结构评分、Fintel 数据、Telegram 推送等

from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
from shared.form4_parser import Form4Parser

# ============ 结构评分计算 ============
def compute_structure_score(data: dict) -> int:
    score = 0
    if data.get('insider') is not None and data['insider'] > 60:
        score += 1
    if data.get('institutional') is not None and data['institutional'] < 20:
        score += 1
    if data.get('float') is not None and data['float'] > 0 and data['float'] < 20:
        score += 1
    return score

# ============ 轧空评分计算 ============
def compute_squeeze_score(data: dict) -> int:
    score = 0
    si = data.get('short_interest', 0)
    if si > 10:
        score += 1
    if si > 20:
        score += 1
    if data.get('float') is not None and data['float'] > 0 and data['float'] < 20:
        score += 1
    if data.get('insider') is not None and data['insider'] > 60:
        score += 1
    return score

# ============ 策略主函数 ============
def run_ceo_strategy(logger, days_back: int = 14, top_n: int = 20, mode: str = "index"):
    logger.info("🚀 启动 insider_ceo 策略")

    try:
        cik_mapping = load_latest_cik_mapping() or {}
        logger.info(f"✅ 加载 CIK 映射: {len(cik_mapping)} 条")

        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=days_back, mode=mode)
        logger.info(f"📥 下载 Form 4 文件数: {len(downloaded_files)}")

        if not downloaded_files:
            logger.warning("📭 未发现新的 Form 4 文件")
            return

        parser = Form4Parser(logger)
        ceo_trades = parser.extract_ceo_purchases(downloaded_files)
        logger.info(f"✅ 识别 CEO 买入记录数: {len(ceo_trades)}")

        if not ceo_trades:
            logger.warning("📭 未发现 CEO 的公开市场买入记录")
            return

        save_ceo_trades_to_csv(ceo_trades, logger)

        valid_ceo_trades = [t for t in ceo_trades if t.get('shares', 0) > 0]
        top_stocks = sorted(valid_ceo_trades, key=lambda x: x.get('shares', 0), reverse=True)[:top_n]

        if not top_stocks:
            logger.warning("📭 没有有效的 CEO 买入股票用于Fintel数据拉取")
            return

        fintel = FintelScraper(logger)
        messages = [f"🔥 *今日 CEO 买入前 {len(top_stocks)} 名*"]

        for stock in top_stocks:
            ticker = stock.get('ticker')
            if not ticker:
                continue
            try:
                fintel_data = fintel.get_fintel_data(ticker)
                if fintel_data:
                    structure_score = compute_structure_score(fintel_data)
                    squeeze_score = compute_squeeze_score(fintel_data)
                    msg = f"""
📈 *Ticker:* `{ticker}`
👤 *CEO:* {stock.get('insider_name', 'N/A')}
🧮 *Shares:* {stock.get('shares', 0):,}
💰 *Price:* ${stock.get('price', 0.0):.2f}
🏦 Insider: {fintel_data.get('insider', 'N/A')}%
🏛 Institutional: {fintel_data.get('institutional', 'N/A')}%
📊 Float: {fintel_data.get('float', 'N/A')}M
🔻 Short Interest: {fintel_data.get('short_interest', 'N/A')}%
⭐ Structure Score: {structure_score}/3
🔥 Squeeze Score: {squeeze_score}/4
📅 Date: {stock.get('trade_date', 'N/A')}
🔗 [EDGAR Filing]({stock.get('filing_url', 'N/A')})
🔗 [Fintel Link](https://fintel.io/s/us/{ticker.lower()})"""
                else:
                    msg = f"⚠ 无法获取 `{ticker}` 的结构数据"
                messages.append(msg)
            except Exception as e:
                logger.error(f"❌ 获取 `{ticker}` 的 Fintel 数据或计算分数失败: {e}", exc_info=True)
                messages.append(f"❌ 获取 `{ticker}` Fintel 数据失败，请手动检查。")

        if len(messages) > 1:
            send_telegram_message("\n\n".join(messages))
        else:
            logger.info("没有足够的信息发送Telegram通知。")

    except Exception as e:
        logger.error("策略运行异常: " + str(e), exc_info=True)
        send_telegram_message(f"🚨 insider_ceo 策略执行失败: {e}")

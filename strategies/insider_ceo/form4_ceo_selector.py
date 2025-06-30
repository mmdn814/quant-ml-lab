# 功能：运行 CEO 买入策略，包含下载、解析、结构评分、Fintel 数据、Telegram 推送等
# 最后更新时间6/30/25 17:05

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
    # 确保字典键存在且值有效
    if data.get('insider') is not None and data['insider'] > 60:
        score += 1
    if data.get('institutional') is not None and data['institutional'] < 20:
        score += 1
    # 考虑float可能为None或0，假设大于0的才有效
    if data.get('float') is not None and data['float'] > 0 and data['float'] < 20:
        score += 1
    return score

# ============ 轧空评分计算 ============
def compute_squeeze_score(data: dict) -> int:
    """根据 Fintel 数据计算轧空评分（0-4）"""
    score = 0
    si = data.get('short_interest', 0) # 默认为0以防None
    if si > 10:
        score += 1
    if si > 20:
        score += 1
    # 考虑float可能为None或0
    if data.get('float') is not None and data['float'] > 0 and data['float'] < 20:
        score += 1
    if data.get('insider') is not None and data['insider'] > 60:
        score += 1
    return score

# ============ 策略主函数 ============
def run_ceo_strategy(logger, days_back: int = 14, top_n: int = 20):
    logger.info("🚀 启动 insider_ceo 策略")

    try:
        # 1. 加载 CIK 映射（目前不直接用，但为后续扩展预留）
        # 确保 load_latest_cik_mapping 健壮性，返回字典
        cik_mapping = load_latest_cik_mapping() or {} 
        logger.info(f"✅ 加载 CIK 映射: {len(cik_mapping)} 条")

        # 2. 下载 Form 4 数据
        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=days_back)
        logger.info(f"📥 下载 Form 4 文件数: {len(downloaded_files)}")

        if not downloaded_files:
            msg = "📭 未发现新的 Form 4 文件"
            logger.warning(msg)
            # send_telegram_message(msg) # 频繁发送可能造成打扰，这里可以选择不发送
            return

        # 3. 解析 CEO 买入交易
        parser = Form4Parser(logger)
        ceo_trades = parser.extract_ceo_purchases(downloaded_files)
        logger.info(f"✅ 识别 CEO 买入记录数: {len(ceo_trades)}")

        if not ceo_trades:
            msg = "📭 未发现 CEO 的公开市场买入记录"
            logger.warning(msg)
            # send_telegram_message(msg) # 频繁发送可能造成打扰，这里可以选择不发送
            return

        # 4. 保存 CSV
        save_ceo_trades_to_csv(ceo_trades, logger)

        # 5. 选取成交股数最多的 top N
        # 过滤掉 shares 为 0 的交易，确保排序有意义
        valid_ceo_trades = [trade for trade in ceo_trades if trade.get('shares', 0) > 0]
        top_stocks = sorted(valid_ceo_trades, key=lambda x: x.get('shares', 0), reverse=True)[:top_n]

        if not top_stocks:
            msg = "📭 没有有效的 CEO 买入股票用于Fintel数据拉取"
            logger.warning(msg)
            # send_telegram_message(msg)
            return

        # 6. Fintel 数据补全并打分
        fintel = FintelScraper(logger)
        messages = [f"🔥 *今日 CEO 买入前 {len(top_stocks)} 名*"] # 使用实际的top_n数量

        for stock in top_stocks:
            ticker = stock.get('ticker')
            if not ticker:
                logger.warning(f"跳过无股票代码的交易: {stock}")
                continue

            try:
                fintel_data = fintel.get_fintel_data(ticker)
                if fintel_data:
                    structure_score = compute_structure_score(fintel_data)
                    squeeze_score = compute_squeeze_score(fintel_data)
                    
                    # 格式化输出，确保所有字段都安全访问
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
                messages.append(f"❌ 获取 `{ticker}` Fintel 数据失败，请手动检查。") # 也通知到Telegram
                continue

        # 7. 发送 Telegram 通知
        # 只有在有有效消息时才发送
        if len(messages) > 1: # 排除掉最初的标题
            send_telegram_message("\n\n".join(messages))
        else:
            logger.info("没有足够的信息发送Telegram通知。")

    except Exception as e:
        logger.error("策略运行异常: " + str(e), exc_info=True) # 打印完整堆栈信息
        send_telegram_message(f"🚨 insider_ceo 策略执行失败: {e}")

# ============ 可直接运行 ============
# 这一块在您的主运行文件中，通常不会在这里直接运行
# if __name__ == "__main__":
#     logger = setup_logger("insider_ceo")
#     run_ceo_strategy(logger, days_back=7, top_n=20)


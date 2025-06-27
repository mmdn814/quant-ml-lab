# 最后更新时间6/27/25 15:4


form4_ceo_selector_code = '''
# strategies/insider_ceo/form4_ceo_selector.py
# 功能：运行 CEO 买入策略，下载 Form 4、解析 CEO 买入、结合 Fintel 数据、结构评分、发送 Telegram 通知

import traceback
from shared.logger import setup_logger
from shared.telegram_notifier import send_telegram_message
from shared.edgar_downloader import EdgarDownloader
from shared.form4_parser import Form4Parser
from shared.fintel_scraper import FintelScraper
from shared.data_saver import save_ceo_trades_to_csv
from shared.data_loader import load_latest_cik_mapping


def compute_structure_score(data: dict) -> int:
    """计算结构评分"""
    score = 0
    if data.get("insider") and data["insider"] > 60:
        score += 1
    if data.get("institutional") is not None and data["institutional"] < 20:
        score += 1
    if data.get("float") and data["float"] < 20:
        score += 1
    return score


def compute_squeeze_score(data: dict) -> int:
    """计算 squeeze 评分"""
    score = 0
    if data.get("short_interest") and data["short_interest"] > 10:
        score += 1
    if data.get("short_interest") and data["short_interest"] > 20:
        score += 1
    if data.get("float") and data["float"] < 20:
        score += 1
    if data.get("insider") and data["insider"] > 60:
        score += 1
    return score


def run_ceo_strategy(logger):
    """策略主入口"""
    logger.info("🚀 [启动] insider_ceo 策略运行中...")

    try:
        # 1. 下载 Form 4 XML 文件
        downloader = EdgarDownloader(logger)
        files = downloader.download_latest_form4(days_back=7)
        logger.info(f"📦 下载 Form 4 文件数量: {len(files)}")

        if not files:
            msg = "⚠️ 未发现新的 Form 4 文件"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 2. 提取 CEO 买入记录
        parser = Form4Parser(logger)
        ceo_trades = parser.extract_ceo_purchases(files)
        logger.info(f"✅ 提取 CEO 买入记录数: {len(ceo_trades)}")

        if not ceo_trades:
            msg = "😕 未发现 CEO 公开市场买入记录"
            logger.warning(msg)
            send_telegram_message(msg)
            return

        # 3. 保存原始记录
        save_ceo_trades_to_csv(ceo_trades, logger)

        # 4. 排序，选取买入量最多前 N 名
        top_ceos = sorted(ceo_trades, key=lambda x: x["shares"], reverse=True)[:20]

        # 5. 获取结构评分 + Fintel 数据
        messages = ["📊 *今日 CEO 买入前 20 名 (按股份数排序)*"]
        fintel = FintelScraper(logger)

        for stock in top_ceos:
            ticker = stock["ticker"]
            try:
                metrics = fintel.get_fintel_data(ticker)
                structure_score = compute_structure_score(metrics)
                squeeze_score = compute_squeeze_score(metrics)

                msg = f"""
📈 *Ticker:* `{ticker}`
👤 *CEO:* {stock["insider_name"]}
🧮 *Shares:* +{stock["shares"]:,}
💰 *Price:* ${stock["price"]}
🏦 Insider: {metrics.get("insider", "N/A")}%
🏛 Institutional: {metrics.get("institutional", "N/A")}%
📊 Float: {metrics.get("float", "N/A")}M
🔻 Short Interest: {metrics.get("short_interest", "N/A")}%
⭐ Structure Score: {structure_score}/3
🔥 Squeeze Score: {squeeze_score}/4
📅 Date: {stock["trade_date"]}
🔗 [EDGAR Filing]({stock["filing_url"]})
🔗 [Fintel](https://fintel.io/s/us/{ticker.lower()})"""
                messages.append(msg)

            except Exception as e:
                logger.error(f"❌ 获取 {ticker} Fintel 数据失败: {e}")
                continue

        # 6. 推送到 Telegram
        send_telegram_message("\\n\\n".join(messages))

    except Exception as e:
        logger.error("💥 策略执行异常: " + str(e))
        logger.error(traceback.format_exc())
        send_telegram_message(f"🚨 insider_ceo 策略运行异常: {e}")
'''

# 将代码写入文件（假设使用路径结构）
path = "/mnt/data/form4_ceo_selector.py"
with open(path, "w") as f:
    f.write(form4_ceo_selector_code)

path

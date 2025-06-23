from shared.logger import setup_logger
from shared.edgar_downloader import EdgarDownloader
from shared.form4_parser import Form4Parser
from shared.data_loader import load_latest_cik_mapping
from shared.fintel_scraper import FintelScraper
from shared.telegram_notifier import send_telegram_message
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
    results = []

    try:
        cik_mapping = load_latest_cik_mapping()
        downloader = EdgarDownloader(logger)
        downloaded_files = downloader.download_latest_form4(days_back=2)

        if not downloaded_files:
            logger.info("😕 未发现新的 Form 4 报告")
            return []

        parser = Form4Parser(logger)
        ceo_buys = parser.extract_ceo_purchases(downloaded_files)

        if not ceo_buys:
            logger.info("😕 未发现 CEO 公开市场买入记录")
            return []

        top_stocks = sorted(ceo_buys, key=lambda x: x['shares'], reverse=True)[:20]

        fintel = FintelScraper(logger)

        for stock in top_stocks:
            ticker = stock['ticker']
            try:
                fintel_data = fintel.get_fintel_data(ticker)
                if fintel_data:
                    structure_score = compute_structure_score(fintel_data)
                    squeeze_score = compute_squeeze_score(fintel_data)

                    result = {
                        **stock,
                        "structure_score": structure_score,
                        "squeeze_score": squeeze_score,
                        "insider_pct": fintel_data.get("insider"),
                        "institutional_pct": fintel_data.get("institutional"),
                        "float_m": fintel_data.get("float"),
                        "short_interest": fintel_data.get("short_interest"),
                        "detail_link": f"https://fintel.io/s/us/{ticker.lower()}",
                        "edgar_link": stock.get("filing_url"),
                    }
                else:
                    result = {
                        **stock,
                        "structure_score": None,
                        "squeeze_score": None,
                        "note": "⚠ 无法获取结构评分数据"
                    }

                results.append(result)

            except Exception as e:
                logger.error(f"❌ {ticker} Fintel 解析异常: {e}")
                continue

    except Exception as e:
        logger.error("🚨 insider_ceo 策略执行异常: " + str(e))
        logger.error(traceback.format_exc())
        send_telegram_message(f"🚨 insider_ceo 策略运行失败：{str(e)}")
        return []

    return results

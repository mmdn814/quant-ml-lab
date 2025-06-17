# insider_ceo 策略的 Telegram 推送格式模块
#兼容了 form4_ceo_selector.py 的数据格式 ✅
#每天推送 20 个最靠前的买入记录 ✅
#自动支持空数据提示 ✅

from shared import telegram_notifier

def send_trade_summary(trade_results):
    """
    格式化并发送整份交易结果列表
    """
    if not trade_results:
        telegram_notifier.send_telegram_message("😕 今天没有 CEO 买入记录")
        return

    messages = ["🚨 *今日 CEO 买入数量前 20 名*"]

    for trade in trade_results[:20]:  # 限制最多 20 个
        msg = f"""📈 *Ticker:* `{trade['ticker']}`
👤 *CEO:* {trade['insider_name']}
🏦 *Company:* {trade['company_name']}
🧮 *Shares:* +{trade['qty']}
💰 *Buy Price:* ${trade['price']}
💰 *Buy Amount:* ${trade['value']:,.0f}
📅 *Filing Date:* {trade['filing_date']}
📅 *Trade Date:* {trade['trade_date']}
🔗 [OpenInsider Link]({trade['detail_link']})
"""
        messages.append(msg)

    final_msg = "\n\n".join(messages)
    telegram_notifier.send_telegram_message(final_msg)


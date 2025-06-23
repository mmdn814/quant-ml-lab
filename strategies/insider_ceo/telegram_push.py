from shared import telegram_notifier

def send_trade_summary(trade_results):
    if not trade_results:
        telegram_notifier.send_telegram_message("😕 今天没有 CEO 买入记录")
        return

    messages = ["🚨 *今日 CEO 买入数量前 20 名*\n"]

    for trade in trade_results[:20]:
        msg = f"""📈 *Ticker:* `{trade['ticker']}`
👤 *CEO:* {trade.get('insider_name')}
🏦 *Company:* {trade.get('company_name')}
🧮 *Shares:* +{trade.get('shares'):,}
💰 *Buy Price:* ${trade.get('price')}
🏦 Insider: {trade.get('insider_pct')}%
🏦 Institutional: {trade.get('institutional_pct')}%
🧮 Float: {trade.get('float_m')}M
🔻 Short Interest: {trade.get('short_interest')}%
⭐ Structure Score: {trade.get('structure_score')}/3
🔥 Squeeze Score: {trade.get('squeeze_score')}/4
📅 Date: {trade.get('trade_date')}
🔗 [EDGAR Filing]({trade.get('edgar_link')})
🔗 [Fintel Link]({trade.get('detail_link')})"""

        messages.append(msg)

    final_msg = "\n\n".join(messages)
    telegram_notifier.send_telegram_message(final_msg)

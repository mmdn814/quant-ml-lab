import requests
from shared.logger import logger
from strategies.insider_ceo.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        logger.info(f"Telegram Response: {resp.status_code}")
        return resp.json()
    except Exception as e:
        logger.error(f"Telegram Push Failed: {e}")
        return None


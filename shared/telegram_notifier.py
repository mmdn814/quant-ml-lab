#配置读取  完全从环境变量读取（兼容 GitHub Secrets）
#日志提示  成功失败都打印日志
#Markdown格式  支持美化格式
#关闭预览  禁用长链接预览，防止推送信息过长
#兼容性  完美兼容之前所有策略

import requests
import os

def send_telegram_message(message):
    """
    统一封装的 Telegram 推送逻辑
    """

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 配置缺失，无法发送通知")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        print("Telegram 推送成功")
    except Exception as e:
        print(f"Telegram 推送失败: {e}")



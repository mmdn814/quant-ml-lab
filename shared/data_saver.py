#每天将解析出来的 CEO 买入数据保存一份 CSV；
#方便未来数据积累、复盘、模型训练；
#防止仅仅依赖于 Telegram 推送日志丢失。

import csv
import os
from datetime import datetime

def save_ceo_trades_to_csv(ceo_buys, data_dir='data/insider_ceo'):
    """
    将每日解析出的 CEO 买入记录保存为 CSV 文件，方便后续回测与建模使用
    """
    if not ceo_buys:
        return

    os.makedirs(data_dir, exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    filename = os.path.join(data_dir, f"ceo_buys_{today_str}.csv")

    fieldnames = [
        'ticker',
        'insider_name',
        'trade_date',
        'shares',
        'price',
        'filing_url'
    ]

    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in ceo_buys:
                writer.writerow(row)
    except Exception as e:
        print(f"保存 CSV 失败: {e}")


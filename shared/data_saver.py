import csv
import os
import pandas as pd
from datetime import datetime

def save_dataframe_to_csv(df: pd.DataFrame, path: str, logger=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    if logger:
        logger.info(f"[保存成功] DataFrame 保存至：{path}")
    else:
        print(f"[保存成功] DataFrame 保存至：{path}")

def save_ceo_trades_to_csv(ceo_buys, data_dir='data/insider_ceo', logger=None):
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

        if logger:
            logger.info(f"[原始数据保存成功] CEO 买入记录保存至：{filename}")
        else:
            print(f"[原始数据保存成功] CEO 买入记录保存至：{filename}")

    except Exception as e:
        err_msg = f"保存 CSV 失败: {e}"
        if logger:
            logger.error(err_msg)
        else:
            print(err_msg)



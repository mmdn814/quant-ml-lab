# 安装依赖（仅在 Colab 中首次运行时使用）
# !pip install yfinance pandas matplotlib numpy

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ===== 策略参数 =====
TICKER = "SPY"             # 标的名称
START_DATE = "2020-01-01"  # 回测起始时间
END_DATE = "2024-12-31"    # 回测结束时间
MA_SHORT = 20              # 中期均线
MA_LONG = 60               # 长期均线
BREAKOUT_LOOKBACK = 3      # 近N日高点突破判断
INITIAL_CAPITAL = 100000   # 初始资金（可选）

# ===== 拉取数据 =====
df = yf.download(TICKER, start=START_DATE, end=END_DATE)
df.dropna(inplace=True)

# ===== 计算均线 =====
df["ma_short"] = df["Close"].rolling(MA_SHORT).mean()
df["ma_long"] = df["Close"].rolling(MA_LONG).mean()

# ===== 趋势确认条件：中期均线上穿长期均线 =====
df["trend_confirmed"] = df["ma_short"] > df["ma_long"]

# ===== 计算近N日高点，用于后续突破判断 =====
df["recent_high"] = df["High"].rolling(BREAKOUT_LOOKBACK).max()

# ===== 去除所有涉及NaN的行，确保计算无误 =====
df.dropna(subset=["ma_short", "ma_long", "recent_high"], inplace=True)

# ===== 策略买入逻辑：趋势成立 + 回调中 + 向上突破 =====
df["signal"] = (
    (df["trend_confirmed"]) &
    (df["Close"] > df["ma_short"]) &
    (df["Close"] > df["recent_high"].shift(1))  # 出现突破信号
)

# ===== 模拟持仓：遇到买点后持有，直到下次买入再更新持仓（简化）=====
df["position"] = 0
holding = False
for i in range(1, len(df)):
    if df["signal"].iloc[i] and not holding:
        df.iloc[i, df.columns.get_loc("position")] = 1
        holding = True
    elif holding:
        df.iloc[i, df.columns.get_loc("position")] = 1
        if df["signal"].iloc[i]:  # 如果连续出现突破，也更新
            continue

# ===== 策略回测收益计算 =====
df["strategy_return"] = df["Close"].pct_change() * df["position"].shift(1)
df["cumulative_strategy"] = (1 + df["strategy_return"]).cumprod()
df["cumulative_buy_hold"] = df["Close"] / df["Close"].iloc[0]

# ===== 输出结果统计 =====
total_return = df["cumulative_strategy"].iloc[-1] - 1
buy_hold_return = df["cumulative_buy_hold"].iloc[-1] - 1
num_trades = df["signal"].sum()

print(f"策略总收益: {total_return:.2%}")
print(f"买入并持有收益: {buy_hold_return:.2%}")
print(f"触发买入次数: {int(num_trades)}")

# ===== 绘制净值曲线 =====
plt.figure(figsize=(12, 6))
plt.plot(df["cumulative_strategy"], label="策略净值")
plt.plot(df["cumulative_buy_hold"], label="买入并持有")
plt.title("SPY 趋势确认 + 回调突破策略回测")
plt.xlabel("时间")
plt.ylabel("累计收益")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

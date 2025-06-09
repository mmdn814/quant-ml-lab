import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 策略参数
TICKER = "SPY"             # 标的
START_DATE = "2020-01-01"  # 回测起始时间
END_DATE = "2024-12-31"    # 回测结束时间
MA_SHORT = 20              # 中期均线
MA_LONG = 60               # 长期均线
BREAKOUT_LOOKBACK = 3      # 最近N日高点突破
INITIAL_CAPITAL = 100000   # 初始资金

# 拉取历史数据
df = yf.download(TICKER, start=START_DATE, end=END_DATE)
df.dropna(inplace=True)

# 计算均线
df["ma_short"] = df["Close"].rolling(MA_SHORT).mean()
df["ma_long"] = df["Close"].rolling(MA_LONG).mean()

# 趋势确认条件：短期均线上穿长期均线
df["trend_confirmed"] = (df["ma_short"] > df["ma_long"])

# 计算近N日高点
df["recent_high"] = df["High"].rolling(BREAKOUT_LOOKBACK).max()

# 策略买入信号：趋势确认 + 在中期均线上方 + 突破近几日高点
df["signal"] = (
    (df["trend_confirmed"]) &
    (df["Close"] > df["ma_short"]) &
    (df["Close"] > df["recent_high"].shift(1))  # 必须是“突破”
)

# 模拟买入：每次买入满仓，遇到下一个买点前全仓持有
df["position"] = 0
holding = False
for i in range(1, len(df)):
    if df["signal"].iloc[i] and not holding:
        df.iloc[i, df.columns.get_loc("position")] = 1
        holding = True
    elif holding:
        df.iloc[i, df.columns.get_loc("position")] = 1
        if df["signal"].iloc[i]:  # 可在此加止盈止损逻辑
            continue

# 计算策略净值
df["strategy_return"] = df["Close"].pct_change() * df["position"].shift(1)
df["cumulative_strategy"] = (1 + df["strategy_return"]).cumprod()
df["cumulative_buy_hold"] = (df["Close"] / df["Close"].iloc[0])

# 输出简单结果
total_return = df["cumulative_strategy"].iloc[-1] - 1
buy_hold_return = df["cumulative_buy_hold"].iloc[-1] - 1
num_trades = df["signal"].sum()

print(f"策略总收益: {total_return:.2%}")
print(f"买入并持有收益: {buy_hold_return:.2%}")
print(f"触发买入次数: {int(num_trades)}")

# 画图
plt.figure(figsize=(12, 6))
plt.plot(df["cumulative_strategy"], label="策略净值")
plt.plot(df["cumulative_buy_hold"], label="买入持有")
plt.title("SPY 趋势+回调+突破策略回测")
plt.xlabel("时间")
plt.ylabel("累计收益")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# insider_ceo 策略专用配置文件
#这里先放宽评分过滤逻辑，先保证全量推送后续你可以随时调整。
#MIN_BUY_AMOUNT 是在 form4_ceo_selector.py 中实际使用的金额过滤阈值。

# 筛选规则
MIN_BUY_AMOUNT = 5000  # 过滤掉买入金额太小的记录，单位美元

# Fintel 抓取时的延迟，防止被风控
FINTEL_REQUEST_DELAY = 0.5

# Fintel 评分阈值（如有）
MIN_STRUCTURE_SCORE = 0  # 暂时不过滤结构评分
MIN_SQUEEZE_SCORE = 0    # 暂时不过滤 squeeze 评分


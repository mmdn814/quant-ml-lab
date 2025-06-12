import yaml
import subprocess
from datetime import datetime, timedelta
import pytz
import os

# 读取 config/schedule_config.yaml
with open("config/schedule_config.yaml", "r") as f:
    config = yaml.safe_load(f)

ny = pytz.timezone("US/Eastern")
now = datetime.now(ny)
dow = now.weekday()

for strategy, rule in config['schedules'].items():
    cron_expr = rule['cron']
    parts = cron_expr.split()
    minute, hour = int(parts[0]), int(parts[1])
    scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    delta = abs((now - scheduled_time).total_seconds())
    if delta < 300 and dow < 5:
        print(f"✅ 运行策略: {strategy}")
        subprocess.run(["python", f"strategies/{strategy}/main.py"])
    else:
        print(f"⏳ 当前跳过: {strategy}")

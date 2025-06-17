
# quant-ml-lab v1.0 6/17/25

> 全自动化量化策略工厂，支持多策略模块化扩展，应对各类策略实验 / 制作 / 实时监控

---

## 🏢 总体目标

* 可备备备控的量化策略工厂基础框架
* 支持多策略同步运行，独立模块化扩展
* 主要功能包括：

  * 数据下载 + 解析
  * 数据备份与缓存
  * 定时调度 + GitHub Actions
  * 开发者级日志跟踪
  * 给 Telegram 实时告警与推送

---

## 🔄 文件结构

### 项目根目录

```
.github/workflows/strategy-runner.yml   # GitHub Actions 定时调度
config/schedule_config.yaml              # 每日策略调度配置
shared/                                   # 公用模块
strategies/insider_ceo/                  # 策略模块: CEO 內实拍卖
run_scheduler.py                         # 全局策略启动器
requirements.txt                         # Python 依赖
README.md                                 # 项目文档
.gitignore
```

### shared/

```
data_loader.py       # 数据加载工具
data_saver.py        # 数据保存工具
edgar_downloader.py  # 下载 SEC Form 4 清单
fintel_scraper.py    # Fintel 结构数据爬取器
form4_parser.py      # 解析 SEC Form 4 XML 文件
logger.py            # 日志系统
telegram_notifier.py # 给 Telegram 发送推送
```

### strategies/insider\_ceo/

```
__init__.py
config.py             # 策略单独配置
form4_ceo_selector.py # 策略核心选股逻辑
main.py               # 策略主控执行
telegram_push.py      # 策略内部 Telegram 格式化
```

### data/

> 数据存储根目录，各策略独立分类存放

```
data/insider_ceo/  # insider_ceo 策略数据目录
models/            # 后续预留的模型文件
```

---

## 📅 执行流程

### 本地测试

```bash
# 启动 insider_ceo 策略
python run_scheduler.py insider_ceo
```

### GitHub Actions 自动化

* 按照 schedule\_config.yaml 配置定时执行
* 推送给 Telegram 消息

---

## 🔄 扩展新策略步骤

1. **新增策略模块：**

```
strategies/{strategy_name}/
  |- __init__.py
  |- config.py
  |- main.py
  |- telegram_push.py
  |- ...
```

2. **在 scheduler 配置中添加调度：**

```yaml
insider_ceo:
  schedule: '0 13 * * *'   # 社区贸星期六时区时间
```

3. **全部兼容 GitHub Actions 自动运行模式**

---

## 🔧 核心特性

* 模块化代码组织，容易维护与扩展
* 多数据源完全集成：EDGAR，OpenInsider，Fintel
* 实时 Telegram 告警与推送
* 完整日志系统
* 自动重试、异常应急机制

---

## 🔒 注意事项

* 本项目仅供学术研究与实验使用，数据来源都为公开网站数据
* 请同时遵循数据源各自 ToS (服务条款)，勿高频使用

---

📄 最后：目前项目已可立即扩展入实战策略工厂模式，可随时在 `strategies/` 下增加新策略单元，整合到全局量化调度系统中。


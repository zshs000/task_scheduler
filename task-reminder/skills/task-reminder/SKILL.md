---
name: task-reminder
description: 本地提醒调度技能。用于用户说"提醒我多久之后/在某个时间做什么"等新增提醒需求，也支持"推送新闻"、"订阅新闻"等新闻资讯推送。尤其适合非技术用户。负责检查服务、自动启动、安装依赖并调用提醒/新闻脚本。
---

# 提醒调度技能

## 核心流程

1) 确定可用的 Python 命令。
2) 检查服务是否运行（健康检查）。
3) 将用户请求转换为提醒命令。
4) 执行提醒命令并反馈结果（提醒通过邮件发送）。

## 1) 确定 Python 命令

优先顺序（第一个可用的为准）：
- `<skill_root>/.venv/Scripts/python.exe` (if exists)
- `py`
- `python`
- `python3`

若都不可用，请用户安装 Python。

## 2) 确保服务运行

读取配置文件：
- `<skill_root>/config/app_config.json`

优先使用 `web_api_base`，否则拼接 `http://{host}:{port}`。
说明：先读取配置，以确定健康检查所用的端口与地址。

健康检查：
- `GET {api_base}/health`

若健康检查失败：
- 使用选定的 Python 命令运行 `<skill_root>/scripts/start_server.py`。
- 再次请求 `GET {api_base}/health`。
- 若仍失败，报告错误并停止。

后台运行：
- 可用 `--daemon` 参数启动后台服务（会写入 `<skill_root>/server.pid`）。
- 若用户未明确说明，先询问是否需要后台常驻；用户同意则使用 `--daemon`，否则默认前台。

## 3) 解析用户请求（两类意图）

### A) 相对时间（无需追问）

示例：
- “提醒我 2小时后吃饭”
- “3天后提醒我提交报告”

转换为：
```
python remind.py <offset> <content>
```
其中 `<offset>` 为 `1d2h30m10s` 这类组合，`<content>` 为提醒内容。

内容增强（统一改写语气）：
- 提取原始意图文本（去掉“提醒我/提醒我在/…后”等引导词）
- 改写为更友好的提示语
- 示例：
  - 原始意图：吃饭
  - 改写内容：主人~该吃饭啦！别饿着～

### B) 相对日期 / 指定时间（可能需要追问）

示例：
- “明天早上8点提醒我开会”
- “后天 9点提醒我交作业”
- “2026-02-07 09:00 提醒我开会”

转换为：
```
python remind.py --at "<time>" <content>
```

规则：
- 用户说“明天/后天/下周…”但**没有具体时间**时，必须追问：“几点提醒？”
- 若用户提供了具体时间，原样传给 `--at`。
- 最大允许未来时间：30 天（脚本会校验）。
直接把提醒内容作为唯一内容参数传入。

内容增强（带时间语气）：
- 在内容里加入时间提示
- 示例：
  - 原始意图：开会
  - 用户时间：明天 08:00
  - 改写内容：主人~现在是 08:00，到了开会时间啦！

## 4) 执行提醒命令

在此工作目录运行：
- `<skill_root>/scripts`

示例：
```
python remind.py 2h30m 提交报告
python remind.py --at "明天 08:00" 开会
```

## 输出给用户

- 成功：确认提醒内容与时间（邮件已发送/将按时发送）。
- 失败：展示脚本错误信息，并提示检查服务或配置。

---

# 通知渠道

系统支持多渠道通知（邮件 + 企业微信），提醒和新闻推送均走统一通知。

## 配置文件

- `<skill_root>/config/notify_config.json` — 默认渠道列表
- `<skill_root>/config/wechat_config.json` — 企业微信 Webhook 配置
- `<skill_root>/config/email_config.json` — 邮件 SMTP 配置

## 企业微信配置

编辑 `config/wechat_config.json`，填入真实的 Webhook Key：
```json
{
  "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY",
  "mentioned_list": []
}
```

---

# 新闻推送技能

## 意图识别

当用户说以下内容时，触发新闻推送功能：
- "推送新闻"、"看看今天的新闻"、"新闻早报" → 立即抓取推送
- "订阅新闻"、"每天推送新闻"、"定时新闻" → 注册定时任务
- "抓取新闻看看" → 仅抓取预览（不推送）

## 核心流程

1) 确定可用的 Python 命令（同提醒技能）。
2) 确保服务运行（同提醒技能）。
3) 根据意图执行对应命令。

## 命令

### A) 立即推送

```
python news.py now
python news.py now --channels wechat
python news.py now --sources 36kr zhihu_hot
```

在此工作目录运行：`<skill_root>/scripts`

### B) 仅抓取预览（不推送）

```
python news.py now --no-push
```

### C) 注册定时推送

```
python news.py schedule
python news.py schedule --cron "0 8,20 * * *"
python news.py schedule --channels wechat
```

默认 cron: `0 8 * * *`（每天早8点）

## 支持的新闻源

内置源（通过 `config/news_config.json` 启用/禁用）：
- `36kr` — 36氪热榜
- `zhihu_hot` — 知乎热榜
- `sina_news` — 新浪新闻
- `infoq` — InfoQ 中文站

自定义 RSS 源：在配置文件 `custom_rss` 数组中添加。

## 输出给用户

- 成功：展示抓取条数和推送结果。
- 失败：展示错误信息，提示检查服务或网络。

# task-reminder 通用技能

一个可在多种 AI 客户端中使用的本地提醒技能（例如 Claude、Codex 等）。
支持通过自然语言添加提醒、自动启动服务，并提供 Web 前端管理界面。
当前仅支持邮件提醒，后续会扩展更多提醒方式。

## 获取项目

方式一（推荐）：npx 安装

```
npx skills add https://github.com/zshs000/task_scheduler --skill task-reminder
```

更多安装方式与详细用法见：
- https://skills.sh/
- https://github.com/vercel-labs/skills

方式二：Git 克隆

```
git clone https://github.com/zshs000/task_scheduler.git
```

方式三：直接下载并解压

## Python 版本

建议使用 Python 3.8+（推荐 3.10/3.11）。

## 安装到 AI 客户端

将 `task-reminder/skills/task-reminder/` 复制到你的技能目录，例如：

- Claude：`C:\Users\<你的用户名>\.claude\skills\task-reminder\`
- Codex：`C:\Users\<你的用户名>\.codex\skills\task-reminder\`

说明：最终目录应包含 `SKILL.md`、`scripts/`、`config/`、`assets/`。

## 配置说明

### 1) 应用配置（端口/地址）

编辑 `config/app_config.json`：

```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "web_api_base": "http://127.0.0.1:8000"
}
```

### 2) 邮箱配置

编辑 `config/email_config.json`：

```json
{
  "smtp_host": "smtp.qq.com",
  "smtp_port": 587,
  "smtp_user": "your_email@qq.com",
  "smtp_password": "your_app_password",
  "recipient": "your_email@qq.com",
  "sender_name": "任务提醒系统"
}
```

> 注：不同邮箱服务商的授权码获取方式不同，请按官方说明生成“应用专用密码”。

## 使用方式

### A) 与 AI 对话（推荐）

示例：
- “提醒我 30 分钟后开会”
- “明天 9 点提醒我提交报告”

AI 会：
1. 读取配置
2. 检查服务是否运行（`/health`）
3. 未运行则自动启动服务（自动创建虚拟环境并安装依赖）
4. 生成提醒并执行

提示：默认提醒内容会使用较亲昵的语气（如“主人~”）。如不喜欢，可在 `skills/task-reminder/SKILL.md` 中修改提示语模板，并按个人喜好调整提醒措辞。

### B) 手动启动服务

在技能目录运行：

```
python scripts/start_server.py
```

后台常驻（关闭窗口不停止）：

```
python scripts/start_server.py --daemon
```

启动成功后访问 Web 页面：
- `http://<host>:<port>/web`

### C) 手动添加提醒

在技能目录运行：

```
python scripts/remind.py 30m 开会
python scripts/remind.py --at "2026-02-07 09:00" 开会
python scripts/remind.py --at "明天 08:00" 开会
```

## Web 前端

提供卡片式任务管理界面，可查看任务、执行历史、清空历史等。
访问：`http://<host>:<port>/web`

## 技术栈

- 后端：FastAPI + APScheduler
- 数据库：SQLite
- 前端：原生 HTML + Tailwind CSS

## 项目结构（技能内）

```
skills/task-reminder/
├── SKILL.md                  # 技能说明
├── scripts/                  # 启动与提醒脚本
│   ├── start_server.py
│   └── remind.py
├── config/                   # 配置文件
│   ├── app_config.json
│   └── email_config.json
└── assets/project/           # 内置完整项目源码
    ├── server/               # 服务端
    ├── client/               # 客户端脚本
    ├── web/                  # 前端页面
    ├── scripts/              # 执行脚本（发邮件）
    ├── data/                 # 数据库
    └── requirements.txt      # 依赖
```

## 主要文件说明

- `scripts/start_server.py`：自动创建虚拟环境、安装依赖并启动服务
- `scripts/remind.py`：解析提醒时间并提交任务
- `config/app_config.json`：服务端口与 API 地址
- `config/email_config.json`：邮箱配置
- `assets/project/server/`：FastAPI 服务端与调度器
- `assets/project/web/`：前端管理界面
- `assets/project/scripts/send_email.py`：邮件发送脚本
- `assets/project/data/tasks.db`：任务与历史数据

## 许可

MIT License

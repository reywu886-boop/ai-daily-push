# 🤖 AI Daily Push - 每日 AI 日报自动推送

> 基于 GitHub Actions 的免费云端方案，每天北京时间 8:00 自动抓取论文 + 热点，邮件推送到你的邮箱。
> 
> **电脑关机也能正常运行。**

---

## 🚀 一次性部署指南（约 10 分钟）

### 第 1 步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名填 `ai-daily-push`，选 **Private**（私有仓库）
3. 点击 "Create repository"

### 第 2 步：上传代码

在本地 `ai-daily-push` 文件夹中执行（或直接在 GitHub 网页上传文件）：

```bash
cd ai-daily-push
git init
git add .
git commit -m "init: AI daily push bot"
git branch -M main
git remote add origin https://github.com/你的用户名/ai-daily-push.git
git push -u origin main
```

### 第 3 步：准备一个发件邮箱

推荐使用 **Gmail**（最稳定）或 **163 邮箱**：

#### 方案 A：Gmail（推荐）
1. 开启 Gmail 两步验证：https://myaccount.google.com/security
2. 创建应用专用密码：https://myaccount.google.com/apppasswords
   - 选择"邮件" + "其他"，名称填 `AI Daily Bot`
   - 记下生成的 16 位密码
3. 配置值：
   - SMTP_SERVER: `smtp.gmail.com`
   - SMTP_PORT: `587`
   - SENDER_EMAIL: `你的gmail@gmail.com`
   - SENDER_PASSWORD: `刚生成的16位应用密码`

#### 方案 B：163 邮箱
1. 登录 163 邮箱 → 设置 → POP3/SMTP 服务 → 开启
2. 会让你设置一个授权码，记下来
3. 配置值：
   - SMTP_SERVER: `smtp.163.com`
   - SMTP_PORT: `465`
   - SENDER_EMAIL: `你的邮箱@163.com`
   - SENDER_PASSWORD: `授权码`

### 第 4 步：配置 GitHub Secrets

1. 打开你的仓库页面 → Settings → Secrets and variables → Actions
2. 点 "New repository secret"，逐一添加以下 5 个：

| Secret 名称 | 值 |
|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` 或 `smtp.163.com` |
| `SMTP_PORT` | `587`（Gmail）或 `465`（163） |
| `SENDER_EMAIL` | 你的发件邮箱地址 |
| `SENDER_PASSWORD` | 应用密码或授权码 |
| `RECIPIENT_EMAIL` | `18868497748@163.com` |

可选（增强新闻搜索质量）：

| Secret 名称 | 值 |
|---|---|
| `SERPER_API_KEY` | 在 https://serper.dev 免费注册获取（每月 2500 次免费搜索） |

### 第 5 步：手动测试一次

1. 打开仓库 → Actions 标签页
2. 左侧选 "AI Daily Push"
3. 点右侧 "Run workflow" 按钮
4. 等待 2-3 分钟，查看运行结果
5. 检查邮箱是否收到日报

### ✅ 完成！

之后每天北京时间 8:00 会自动运行并推送。

---

## ⚙️ 自定义配置

### 修改推送时间

编辑 `.github/workflows/daily-push.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 0 * * *'  # UTC 00:00 = 北京 08:00
```

常用时间对照（UTC → 北京时间）：
- `0 23 * * *` → 北京时间 07:00
- `0 0 * * *` → 北京时间 08:00
- `0 1 * * *` → 北京时间 09:00

### 修改论文筛选方向

编辑 `fetch_papers.py` 中的 `classify_paper()` 函数，调整关键词。

### 修改推送数量

在 `main.py` 中调整 `max_papers` 和 `max_items` 参数。

---

## 📁 项目结构

```
ai-daily-push/
├── .github/
│   └── workflows/
│       └── daily-push.yml    # GitHub Actions 定时任务
├── fetch_papers.py           # 论文抓取模块
├── fetch_news.py             # 热点新闻抓取模块
├── send_email.py             # 邮件推送模块
├── main.py                   # 主程序入口
├── requirements.txt          # Python 依赖
├── .gitignore
└── README.md                 # 本文件
```

## 💡 原理说明

- **GitHub Actions** 是 GitHub 的 CI/CD 服务，免费账户每月 2000 分钟
- 每天自动触发 Python 脚本运行
- 脚本从 HuggingFace、PapersWithCode、RSS 等抓取论文和新闻
- 格式化后通过 SMTP 发送邮件
- 整个过程在 GitHub 的云端服务器上运行，**与你的电脑无关**

## ⚠️ 注意事项

- GitHub Actions 的 cron 触发可能有 5-15 分钟延迟，这是正常的
- 免费账户每月 2000 分钟，每次运行约 2-3 分钟，每天跑完全足够
- 如果连续 60 天没有仓库活动，Actions 会自动暂停，只需随便 push 一次即可恢复

# ChatGPT Owner Demote Tool

将 ChatGPT Team/Enterprise 的所有者 (Owner) 批量降级为管理员 (Admin) 或普通成员 (Member)。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ 功能特点

- 🔄 支持批量处理多个账号
- 🔐 自动解析 Session 获取用户信息
- 🛡️ 使用真实浏览器绕过 Cloudflare 防护
- 👥 支持降级为管理员或普通成员
- 📊 实时显示处理进度和结果
- 🎨 现代化深色主题 UI

## 📋 前置要求

- Python 3.10+
- Chrome 或 Edge 浏览器

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/chatgpt-owner-demote.git
cd chatgpt-owner-demote
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python main.py
```

### 4. 访问界面

打开浏览器访问：**http://localhost:8000**

## 📖 使用方法

1. **登录 ChatGPT**：使用你的 Owner 账号登录 [chatgpt.com](https://chatgpt.com)

2. **获取 Session**：在浏览器地址栏访问：
   ```
   https://chatgpt.com/api/auth/session
   ```

3. **复制完整 JSON**：复制整个 JSON 响应（包含 accessToken、user、account）

4. **开始降级**：
   - 将 JSON 粘贴到输入框
   - 选择目标角色（普通成员/管理员）
   - 点击"开始批量处理"

## 🔧 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HEADLESS` | `true` | 是否使用无头模式运行浏览器 |
| `PORT` | `8000` | 服务监听端口 |

## 📡 API 接口

### POST /api/demote/owner

**请求体：**
```json
{
  "access_token": "完整的 Session JSON 或 accessToken",
  "account_id": "可选，自动从 Session 解析",
  "role": "standard-user 或 account-admin"
}
```

**响应：**
```json
{
  "success": true,
  "message": "成功降级为普通成员",
  "email": "user@example.com",
  "new_role": "standard-user"
}
```

## 🐳 Docker 部署

```dockerfile
FROM python:3.11-slim

# 安装 Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg2 \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend
ENV HEADLESS=true
CMD ["python", "main.py"]
```

## 📁 项目结构

```
chatgpt-owner-demote/
├── backend/
│   ├── main.py           # FastAPI 后端服务
│   └── requirements.txt  # Python 依赖
├── frontend/
│   ├── index.html        # 主页面
│   ├── style.css         # 样式文件
│   ├── script.js         # 前端逻辑
│   └── favicon.png       # 网站图标
├── .gitignore
├── LICENSE
└── README.md
```

## 🔐 角色说明

| 角色 | API 值 | 权限说明 |
|------|--------|----------|
| 所有者 | `workspace-owner` | 最高权限，可管理账单和成员 |
| 管理员 | `account-admin` | 可管理成员，无法管理账单 |
| 普通成员 | `standard-user` | 仅可使用 ChatGPT |

## 🛠️ 技术栈

- **后端**: Python FastAPI + DrissionPage
- **前端**: HTML + CSS + JavaScript
- **浏览器自动化**: DrissionPage (Chrome)
- **样式**: 现代深色主题 + 渐变动效

## ⚠️ 注意事项

- 本工具仅供合法用途使用
- 请确保你有权限操作目标账户
- 降级操作不可逆，请谨慎操作

## 📄 License

[MIT](LICENSE)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

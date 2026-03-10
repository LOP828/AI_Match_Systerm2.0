# AI 辅助红娘筛选系统 2.0

一个面向红娘工作台的 MVP 项目。  
核心目标不是“让算法直接替人配对”，而是让系统先完成资料整理、硬规则筛选、候选排序、待核实任务生成、反馈沉淀与 AI 抽取审核，再由红娘做最后判断。

---

## 当前能力

本项目当前包含以下能力：

- 用户画像查看与编辑
- 偏好、禁忌、观察标签管理
- 推荐结果生成与快照查询
- 待核实任务队列与人工确认
- 见面反馈录入与历史查看
- Memo 的 AI 抽取审核
- 登录、Bearer Token 鉴权、角色控制
- SQLite 本地开发 + PostgreSQL 烟雾验证
- 前后端基础测试与 VS Code 任务集成

---

## 技术栈

### 后端
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PyJWT
- SQLite（默认开发）
- PostgreSQL（联调验证）

### 前端
- React 19
- TypeScript
- Vite
- Tailwind CSS
- React Query
- React Router

### 测试
- Pytest
- Vitest
- Testing Library

---

## 项目结构

```text
ai_match_system2.0/
├─ backend/
│  ├─ app/
│  │  ├─ api/               # 路由层
│  │  ├─ models/            # SQLAlchemy 模型
│  │  ├─ schemas/           # Pydantic 请求/响应模型
│  │  ├─ services/          # 业务逻辑
│  │  ├─ auth.py            # 鉴权与 ActorContext
│  │  ├─ config.py          # 环境变量与运行时约束
│  │  ├─ db.py              # 数据库连接与 Session
│  │  └─ main.py            # FastAPI 入口
│  ├─ alembic/              # 数据库迁移
│  ├─ scripts/              # 工具脚本（含 PostgreSQL 烟雾测试）
│  ├─ tests/                # 后端测试
│  ├─ .env.example
│  ├─ alembic.ini
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ api/               # 前端 API 客户端
│  │  ├─ auth/              # 登录态管理
│  │  └─ pages/             # 页面
│  ├─ public/
│  ├─ package.json
│  ├─ vite.config.ts
│  └─ tsconfig*.json
├─ .vscode/                 # VS Code 任务与解释器配置
├─ .gitignore
└─ README.md
```

---

## 运行前准备

建议环境：

- Python 3.13
- Node.js 20+
- npm 10+
- Git
- 可选：Docker Desktop（用于临时 PostgreSQL）

---

## 快速开始

### 1）创建 Python 虚拟环境

在**仓库根目录**执行：

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

---

### 2）安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

---

### 3）配置后端环境变量

复制示例文件：

```bash
copy .env.example .env
```

Linux / macOS：

```bash
cp .env.example .env
```

默认示例：

```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///./ai_match_mvp.db
AUTH_REQUIRED=true
ALLOW_LEGACY_HEADERS=true
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_SECRET_KEY=replace_with_a_long_random_secret_at_least_32_chars
JWT_ISSUER=ai-match-backend
JWT_EXPIRE_MINUTES=120
DEEPSEEK_API_KEY=
AI_EXTRACTION_ENABLED=true
ALLOW_SQLITE_IN_PRODUCTION=false
```

说明：

- 默认数据库是 SQLite，本地开发足够用
- `DATABASE_URL=sqlite:///./ai_match_mvp.db` 在你从 `backend` 目录启动时，会创建在 `backend/ai_match_mvp.db`
- 未配置 `DEEPSEEK_API_KEY` 时，普通页面仍可运行，但 AI 抽取触发接口会返回配置错误
- 生产环境必须提供足够强的 `JWT_SECRET_KEY`

---

### 4）执行数据库迁移

仍在 `backend` 目录下执行：

```bash
alembic upgrade head
```

---

### 5）启动后端

仍在 `backend` 目录下执行：

```bash
uvicorn app.main:app --reload
```

启动后可访问：

- Swagger 文档：http://localhost:8000/docs
- ReDoc 文档：http://localhost:8000/redoc
- 健康检查：http://localhost:8000/health

---

### 6）启动前端

新开一个终端，回到项目根目录后执行：

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：

- http://localhost:5173

Vite 已配置代理，会自动把 `/api` 转发到：

- http://localhost:8000

---

## Python 虚拟环境说明

本项目约定在**仓库根目录**创建并使用 `.venv` 作为本地 Python 虚拟环境，供 VS Code 和命令行统一使用。

注意：

- `.venv` 仅用于**本地开发环境**
- `.venv` **不会提交到 Git 仓库**
- 仓库中保留的是依赖清单（如 `backend/requirements.txt`），其他开发者应在本地自行创建 `.venv`
- 新开的 VS Code 终端通常会自动激活仓库根目录的 `.venv`
- 如果当前终端仍在使用旧环境，请关闭后重新打开终端，再执行相关命令

---

## 登录与鉴权

当前前端默认要求先登录，再访问业务页面。

### 登录接口

```http
POST /api/auth/login
```

请求体：

```json
{
  "userId": 101,
  "password": "password123"
}
```

登录成功后：

- 前端会保存 Bearer Token
- 后续 API 请求会自动带上 `Authorization: Bearer <token>`

### 角色权限

当前特权角色来自后端配置：

- `admin`
- `matchmaker`

这两个角色可以访问：

- `/verify-tasks`
- `/ai-extraction-review`

普通用户不可访问以上特权页面。

---

## 本地开发如何初始化第一个账号

当前仓库**没有内置 seed.py 导数脚本**。  
也就是说，第一次跑起来后，如果数据库是全新的，你需要先手动创建用户资料和登录凭证。

在开发环境下，默认允许 legacy headers，因此可以用下面方式初始化。

### 1）先创建用户画像

```bash
curl -X POST "http://localhost:8000/api/profile/101" ^
  -H "Content-Type: application/json" ^
  -H "X-User-Id: 101" ^
  -H "X-Role: admin" ^
  -d "{\"gender\":\"male\",\"age\":30,\"city_code\":\"310000\",\"active_status\":\"active\",\"open_to_match\":1}"
```

### 2）再为该用户创建登录凭证

```bash
curl -X POST "http://localhost:8000/api/auth/credential" ^
  -H "Content-Type: application/json" ^
  -H "X-User-Id: 101" ^
  -H "X-Role: admin" ^
  -d "{\"userId\":101,\"password\":\"password123\",\"role\":\"admin\"}"
```

然后就可以在前端登录：

- 用户 ID：`101`
- 密码：`password123`

> 注意：  
> `X-User-Id` / `X-Role` 这种 legacy headers 仅建议用于本地开发。生产环境必须关闭。

---

## 页面说明

| 路径 | 说明 |
|---|---|
| `/login` | 登录页 |
| `/` | 工作台首页 |
| `/user/:id` | 用户画像（资料、偏好、禁忌、标签） |
| `/recommendation/:id` | 推荐结果与快照 |
| `/verify-tasks` | 待核实队列（仅 admin / matchmaker） |
| `/feedback` | 反馈录入 |
| `/ai-extraction-review` | AI 抽取审核（仅 admin / matchmaker） |

---

## 业务流程

### 1. 用户画像
查看或编辑用户资料、偏好、禁忌、观察标签。

### 2. 生成推荐
根据用户资料和规则生成候选结果与推荐快照。

### 3. 待核实任务
对高潜力候选中“未知但重要”的信息生成核实任务，由红娘人工确认。

### 4. 反馈录入
记录见面结果、互动事件和 Memo。

### 5. AI 抽取审核
对 Memo 中抽取出的标签进行人工审核确认。

---

## 主要 API

### 鉴权
- `POST /api/auth/login`
- `POST /api/auth/credential`
- `POST /api/auth/token`
- `GET /api/auth/me`

### 用户画像
- `GET /api/profile/{user_id}`
- `POST /api/profile/{user_id}`
- `POST /api/profile/{user_id}/preference`
- `POST /api/profile/{user_id}/constraint`
- `POST /api/profile/{user_id}/observation-tag`

### 推荐
- `POST /api/recommendation/generate`
- `GET /api/recommendation/{requester_id}`

### 待核实
- `GET /api/verify-tasks/`
- `POST /api/verify-tasks/{task_id}/confirm`

### 反馈
- `POST /api/feedback/meeting`
- `GET /api/feedback/history`

### AI 抽取
- `GET /api/ai-extraction/`
- `POST /api/ai-extraction/{extraction_id}/approve`
- `POST /api/ai-extraction/{extraction_id}/reject`
- `POST /api/ai-extraction/trigger/{memo_id}`

最准确的接口定义以 Swagger 为准：

- http://localhost:8000/docs

---

## 测试

### 后端测试

在 `backend` 目录执行：

```bash
pytest
```

### 前端测试

在 `frontend` 目录执行：

```bash
npm run test
```

### 前端构建

```bash
npm run build
```

### 前端 Lint

```bash
npm run lint
```

---

## PostgreSQL 联调验证

如果本机已启动 PostgreSQL，可执行一次真实迁移烟雾验证。

在 `backend` 目录执行：

```bash
python scripts/postgres_smoke_test.py --database-url postgresql+psycopg://postgres:postgres@localhost:5432/ai_match_mvp
```

该脚本会：

- 执行 `alembic upgrade head`
- 校验 PostgreSQL 连接
- 校验关键约束是否仍然生效

如果你本机有 Docker Desktop，也可以先启动一个临时 PostgreSQL：

```bash
docker run --name ai-match-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ai_match_mvp -p 5432:5432 -d postgres:16
```

---

## VS Code 任务

工作区已提供以下任务，并统一使用仓库根目录 `.venv`：

- `Backend: Pytest`
- `Backend: Uvicorn`
- `Backend: PostgreSQL Smoke Test`
- `Frontend: Install`
- `Frontend: Dev`
- `Frontend: Build`
- `Frontend: Test`
- `Frontend: Lint`

如果你使用 VS Code，可以直接在：

- `Terminal` → `Run Task`

里执行。

---

## 生产环境注意事项

### 1）不要在生产环境继续使用 SQLite
生产环境默认禁止 SQLite，除非显式允许。

### 2）必须关闭 legacy headers
生产环境必须关闭：

```env
ALLOW_LEGACY_HEADERS=false
```

否则存在通过 `X-User-Id` / `X-Role` 绕过 Bearer Token 的风险。

### 3）必须使用强 JWT 密钥
`JWT_SECRET_KEY` 必须至少 32 个字符。

### 4）显式配置 CORS
如果前端部署到真实域名，务必设置：

```env
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
```

### 5）AI 抽取功能需要真实密钥
如果启用了 AI 抽取：

```env
AI_EXTRACTION_ENABLED=true
```

则生产环境必须配置：

```env
DEEPSEEK_API_KEY=your_real_key
```

---

## Git 与仓库规范

建议提交到 Git 的内容：

- 源码
- 文档
- 配置模板
- 测试代码
- 依赖清单

不要提交到 Git 的内容：

- `.venv`
- `node_modules`
- `dist`
- `__pycache__`
- `.pytest_cache`
- `.pytest_tmp`
- 本地 `.db`
- 本地 `.env`

---

## 常见问题

### 为什么 `.venv` 没有上传到 GitHub？
因为 `.venv` 是本地开发环境，不是项目源码的一部分。  
仓库应上传的是依赖清单，而不是你本机已经安装好的环境副本。

### 为什么 AI 抽取接口返回配置错误？
因为项目启用了 AI 抽取能力，但当前没有配置 `DEEPSEEK_API_KEY`。

### 为什么前端能打开但业务页报 401？
因为当前前端默认要求登录。请先创建账号并通过 `/login` 登录后再访问业务页面。

### 为什么生产环境启动失败？
请检查：
- 是否还在使用 SQLite
- 是否仍开启 legacy headers
- `JWT_SECRET_KEY` 是否足够强
- `DEEPSEEK_API_KEY` 是否缺失

---

## 当前项目定位

这是一个偏工程验证和流程验证的 MVP，当前重点是：

- 路由和页面打通
- 鉴权与角色控制打通
- 推荐、核实、反馈、审核这条链路打通
- 后端约束、迁移、测试基础打稳

它不是最终产品形态，但已经能作为后续继续迭代的工作底座。

---
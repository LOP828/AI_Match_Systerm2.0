# AI 辅助红娘筛选系统 2.0 - MVP

本项目实现文档中定义的 AI 辅助红娘筛选系统 MVP，包含：

- **Python FastAPI 后端**：两阶段推荐、禁忌管理、反馈与 AI 抽取
- **React + TypeScript + Tailwind 前端**：红娘工作台

## 快速开始

### 1. 后端

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py   # 导入测试数据（如果仓库已包含该脚本）

uvicorn app.main:app --reload
```

说明：

- 工作区统一使用仓库根目录的 [.venv](.venv) 作为 Python 解释器
- 新开的 VS Code 终端会优先激活这个环境；如果已有旧终端，请重新开一个再执行命令

启动后可访问：

- 接口文档（Swagger）：http://localhost:8000/docs
- 接口文档（ReDoc）：http://localhost:8000/redoc
- 健康检查：http://localhost:8000/health

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173，通过 Vite 代理将 `/api` 转发到后端。

### 3. 环境变量

复制 [backend/.env.example](backend/.env.example) 为 `backend/.env` 后按需修改：

```
ENVIRONMENT=development
DATABASE_URL=sqlite:///./ai_match_mvp.db
AUTH_REQUIRED=true
ALLOW_LEGACY_HEADERS=true
JWT_SECRET_KEY=replace_with_a_long_random_secret_at_least_32_chars
DEEPSEEK_API_KEY=your_key   # AI 抽取时使用
```

说明：

- `ENVIRONMENT=development` 时可保留 demo 能力；只有开发/测试环境才允许 `ALLOW_LEGACY_HEADERS=true`
- `ENVIRONMENT=production` 时必须配置强随机 `JWT_SECRET_KEY`，并且默认禁止 SQLite 与 legacy headers
- 未配置 `DEEPSEEK_API_KEY` 时，普通页面仍可使用，但 AI 抽取触发接口会返回明确的配置错误
- 如需切换 PostgreSQL，可将 `DATABASE_URL` 改为 `postgresql+psycopg://user:password@host:5432/dbname`，并执行 `alembic upgrade head`

### 4. 登录与鉴权

- 前端现在要求先登录，再访问业务页面
- 登录接口：`POST /api/auth/login`
- 登录成功后，前端会自动保存 Bearer Token，并在所有 API 请求中注入 `Authorization` 头
- 待核实队列和 AI 审核页面仅对 `admin` / `matchmaker` 角色开放

### 5. 生产环境注意事项

- SQLite 仅建议用于本地开发和演示；生产环境默认会阻止以 SQLite 启动
- 生产环境必须关闭 legacy headers，避免通过 `X-User-Id` / `X-Role` 绕过 Bearer Token
- 如果要部署到真实域名，请通过 `CORS_ALLOWED_ORIGINS` 显式配置前端来源
- 当前迁移脚本已移除 JSON 字段上的 SQLite 方言硬绑定，并将 SQLite 专用自增修复限制为仅在 SQLite 上执行

### 6. PostgreSQL 联调验证

如果本机已启动 PostgreSQL，可直接执行一次真实迁移烟雾验证：

```bash
cd backend
python scripts/postgres_smoke_test.py --database-url postgresql+psycopg://postgres:postgres@localhost:5432/ai_match_mvp
```

建议使用一次性或空库执行这条命令。脚本会：

- 执行 `alembic upgrade head`
- 校验 PostgreSQL 连接可用
- 校验 `recommendation_snapshot` 的唯一约束仍然生效
- 校验 `user_profile.active_status` 的检查约束仍然生效

如果本机使用 Docker Desktop，可先启动 Docker，再用类似下面的命令拉起临时 PostgreSQL：

```bash
docker run --name ai-match-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ai_match_mvp -p 5432:5432 -d postgres:16
```

### 7. VS Code 一键任务

工作区已经提供以下 VS Code 任务，且统一使用仓库根目录的 [.venv](.venv)：

- `Backend: Pytest`
- `Backend: Uvicorn`
- `Backend: PostgreSQL Smoke Test`
- `Frontend: Install`
- `Frontend: Dev`
- `Frontend: Build`
- `Frontend: Test`
- `Frontend: Lint`

其中 PostgreSQL 烟雾验证任务会弹出 `DATABASE_URL` 输入框，默认值为本地 Docker PostgreSQL 示例地址。

## 功能页面

| 路径 | 说明 |
|------|------|
| / | 工作台首页 |
| /user/:id | 用户画像（资料、偏好、禁忌、标签） |
| /recommendation/:id | 推荐结果 |
| /verify-tasks | 待核实队列 |
| /feedback | 反馈录入 |
| /ai-extraction-review | AI 抽取审核 |

## 流程

1. **用户画像** → 查看/编辑用户 101 资料，点击「生成推荐 TopN」
2. **推荐结果** → 查看粗排候选与快照
3. **待核实** → 对高潜力候选的未知禁忌进行确认
4. **反馈录入** → 记录见面结果与 Memo
5. **AI 审核** → 审核 Memo 抽取的观察标签（需配置 DEEPSEEK_API_KEY 并触发抽取）

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、Alembic、SQLite
- 前端：React 19、TypeScript、Vite、Tailwind CSS、React Query、React Router

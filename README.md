# 筑衡 · 建筑方案智能比选智能体

> 面向“好房子”建设的建筑方案智能比选智能体：大模型负责理解需求、规划任务和解释结果；数值由确定性工具计算，合规由规则引擎判定。

详细技术方案见 [Agent.md](./Agent.md)，使用、协议、规则与运维文档见 [文档入口](./docs/README.md)。

本轮线上初筛材料须在 **2026-10-15 24:00（UTC+8）前提交**。内部目标为 2026-10-14 12:00 冻结版本；四项材料、日程和分工见 [交付计划](./docs/submission-plan.md)，接手上下文见 [项目记忆](./memory/README.md)。原 2026-10-30 计划不再适用于本轮交付。

---

## 快速开始

### 方式一：本地开发（推荐用于联调）

需要本机已安装：

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Node.js 20+ 与 npm

```powershell
# 在仓库根目录安装依赖
uv sync --project backend --all-extras --frozen
npm --prefix frontend ci

# 可选：清空开发数据库并导入虚构样例；已有数据时勿执行
uv run --project backend python scripts/seed_mock.py

# 启动后端（默认 LLM_PROVIDER=fake，无需 API Key）
uv run --project backend uvicorn app.main:app --app-dir backend --reload --port 8000

# 另开终端，在仓库根目录启动前端
npm --prefix frontend run dev
# 浏览器打开 http://localhost:5173
```

也可使用 `make dev-backend` / `make dev-frontend`。复制 `.env.example` 为根目录 `.env` 后可修改 LLM / 数据库配置。默认数据库固定在本工作树的 `backend/data/zhuheng.db`，不受命令工作目录影响；显式配置 `DATABASE_URL` 时建议使用绝对路径。

`npm --prefix frontend run dev:mock` 可启动离线演示。真实模式通过后端计算，接口失败会显示错误。FakeLLM 走真实评估、排序与 SSE 链路，文本由确定性桩生成。当前规则、角色权重与方案均含示例或专业待确认项，结果仅用于开发联调，详见 [未决事项](docs/open-items.md)。

### 方式二：Docker Compose（本地演示）

需要本机已安装 Docker 与 Docker Compose v2。

```bash
docker compose up --build
# 浏览器打开 http://localhost:8080 ，即可看到 "后端状态：ok"
```

容器数据库使用 `/app/data/zhuheng.db`，挂载到宿主机 `./data/`；规则挂载到 `/app/rules`。覆盖 `DATABASE_URL` 时必须使用容器内路径。

### 云服务器发布

访问地址：[Steelyard · 筑衡](https://project.jnove.dpdns.org/steelyard/)。

`main` 的 push 通过后端与前端检查后，GitHub Actions 构建对应提交的镜像并发布到 jnove.vm。
生产编排使用 `docker-compose.production.yml`，数据库保存在服务器的 `shared/data/`，发布不执行样例播种。
服务器配置、SSH Secrets、子路径代理、验收和回滚步骤见 [部署指南](./docs/deployment.md)。

当前部署默认使用 FakeLLM；专业规则、角色权重与 T10 检索仍需完成专业验收。

---

## 常用命令

```bash
make test         # 后端 pytest + 前端单元测试
make lint         # 后端与 scripts/ 的 ruff + 前端 tsc --noEmit
make up           # docker compose 一键启动
make down         # docker compose 关闭
```

---

## 目录结构

```
.
├── backend/           FastAPI 后端（uv 管理依赖）
│   ├── app/           main.py、config.py、api/、models/、engine/、agents/、rag/
│   ├── tests/         pytest 测试
│   └── data/          本地默认 SQLite（运行产物，不提交）
├── frontend/          Vite + React + TypeScript 前端
├── rules/             土木 / 建筑同学维护的 YAML 规则
├── data/              Schema、虚构方案、Excel 模板；容器 SQLite 卷
├── docs/              使用、规则、协议、部署指南与历史归档
├── memory/            当前交付约束、团队分工与 Agent 接手入口
├── scripts/           工程脚本（check_rules.py 等）
├── docker-compose.yml 本地演示
├── docker-compose.production.yml 服务器发布编排
└── Makefile           常用命令
```

---

## 当前进度

- [x] **T1**：项目脚手架（前后端骨架 + Docker 部署 + CI）
- [x] **T2**：数据模型与项目 / 方案 CRUD
- [x] **T3**：规则引擎、指标计算与分段评分
- [x] **T4**：AHP / TOPSIS / 敏感性 / 帕累托 / 名次概率
- [x] **T5**：Excel 模板与原子导入
- [x] **T6**：虚构开发数据与数据库初始化
- [x] **T7**：前端页面、ECharts 看板与离线演示
- [x] **T8**：智能体编排、SSE 对话 / 报告、What-if 与引用校验
- [x] **T9**：规则编写指南与校验工具
- [ ] **T10**：规范条文结构化与检索

任务编号按项目任务提示词对齐。T1–T9 的历史集成与联调见 [集成归档](docs/archive/integration-t1-t9.md)。条文搜索当前仍为空结果桩，待 T10 接入。

**还没定下来的事**都记在 [docs/open-items.md](./docs/open-items.md)：
先看初筛 P0，专业组待定的规则阈值与权重在第一部分，开发侧事项在第二部分。
T1–T9 集成完成不表示专业规则、真实模型或比赛材料已验收；界面改造与完整 T10 仍是待办。

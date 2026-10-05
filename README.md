# 筑衡 · 建筑方案智能比选智能体

> 面向“好房子”建设的建筑方案智能比选智能体：大模型负责理解需求、规划任务和解释结果；数值由确定性工具计算，合规由规则引擎判定。

详细技术方案见 [Agent.md](./Agent.md)。

---

## 快速开始

### 方式一：本地开发（推荐用于联调）

需要本机已安装：

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Node.js 20+ 与 npm

```bash
# 1. 启动后端（端口 8000）
make dev-backend

# 2. 另开一个终端，启动前端（端口 5173）
make dev-frontend

# 浏览器打开 http://localhost:5173 ，右上角应能看到 "后端状态：ok"
```

可选：复制 `.env.example` 为 `.env` 后按需修改 LLM / 数据库配置。

### 方式二：Docker Compose（演示或云服务器）

需要本机已安装 Docker 与 Docker Compose v2。

```bash
docker compose up --build
# 浏览器打开 http://localhost:8080 ，即可看到 "后端状态：ok"
```

数据持久化在 `./data/` 与 `./rules/` 目录，关闭容器不会丢失。

---

## 常用命令

```bash
make test         # 后端 pytest
make lint         # 后端 ruff check + 前端 tsc --noEmit
make up           # docker compose 一键启动
make down         # docker compose 关闭
```

---

## 目录结构

```
.
├── backend/           FastAPI 后端（uv 管理依赖）
│   ├── app/           main.py、config.py、api/、models/、engine/、agents/、rag/
│   └── tests/         pytest 测试
├── frontend/          Vite + React + TypeScript 前端
├── rules/             土木 / 建筑同学维护的 YAML 规则
├── data/              SQLite 数据库与测试方案
├── docs/              规则编写指南、字段对照表、未决事项清单
├── scripts/           工程脚本（check_rules.py 等）
├── docker-compose.yml 一键启动
└── Makefile           常用命令
```

---

## 当前进度

- [x] **T1**：项目脚手架（前后端骨架 + Docker 部署 + CI）
- [ ] **T2**：数据模型与项目 / 方案 CRUD
- [ ] **T3**：规则引擎（YAML 加载、安全求值、合规判定）
- [ ] **T4**：指标计算与分段线性评分
- [ ] **T5**：AHP / TOPSIS / 敏感性 / 帕累托
- [ ] **T6**：智能体编排与 SSE 对话 / 报告
- [ ] **T7**：前端页面与 ECharts 看板

详见 `Agent.md` 的章节划分与 PR 描述。

**还没定下来的事**都记在 [docs/open-items.md](./docs/open-items.md)：
专业组待定的规则阈值与权重在第一部分，开发侧待修项在第二部分。
接手前先过一遍这份清单。
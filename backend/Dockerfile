# syntax=docker/dockerfile:1.7

# 依赖层独立缓存
FROM python:3.11-slim AS deps

# uv 是 Astral 推出的 Python 包管理器，比 pip 快一个数量级
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

WORKDIR /app/backend

# 先拷依赖清单与锁文件，以最大化缓存命中
COPY pyproject.toml uv.lock ./

# 仅安装运行时依赖，不装 dev 组的 pytest / ruff
RUN uv sync --frozen --no-dev --no-install-project

# 真正的应用层
FROM python:3.11-slim AS app

WORKDIR /app/backend

# 直接复用 deps 层的虚拟环境
COPY --from=deps /app/backend/.venv /app/backend/.venv
ENV PATH="/app/backend/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

# 保持仓库目录层级，使规则加载器定位到 /app/rules
COPY app ./app

# 持久化数据（SQLite、规则、测试方案）由 compose 挂载
RUN mkdir -p /app/data /app/rules /app/backend/data
VOLUME ["/app/data", "/app/rules"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

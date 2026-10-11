# 自动部署到 jnove.vm

访问地址为 <https://project.jnove.dpdns.org/steelyard>。应用代码由本仓库维护；同一 VM 上博客仓库 `jnoves-blog` 维护 `blog-caddy` 的域名、证书和入口路由。生产环境使用 `docker-compose.production.yml`，开发环境继续使用根目录的 `docker-compose.yml`。

## 发布链路

`.github/workflows/ci.yml` 对 `main`、`feat/**`、`codex/**` 的 push 与发往 `main` 的 PR 执行原有完整后端、前端检查。只有 **main 的 push** 或 **在 main 上手动 workflow_dispatch** 会进入后续发布任务；PR 与其他分支仅测试。

1. 后端 ruff、pytest、规则、字段表、Schema 检查与前端测试、类型生成、类型检查、构建全部通过。
2. `package` checkout 触发提交的完整 SHA，在 GitHub runner 构建两个带该 SHA 标签与 revision label 的镜像。生产前端使用 `/steelyard/` 作为 Vite base；Nginx 使用私有网络的 `steelyard-backend`。
3. runner 以临时数据库启动生产 Compose，检查 base 跳转、SPA 深链接、静态资源、公开 SHA、API 与 POST SSE `done`。成功后上传镜像、`git archive` 源码与 SHA256 校验和，artifact 保留 7 天。
4. `deploy` 使用 `production` environment 与固定 concurrency group，等待中的过时提交在部署前与当前 main SHA 比对后跳过。正在执行的部署不会被新 push 取消。
5. 使用独立 SSH key 和固定 known_hosts 上传 artifact。VM 校验文件完整性与提交 SHA，加载镜像，在服务器锁内替换独立的 `steelyard` Compose 项目。
6. 容器健康、本机与公开路径验收通过后，才将 `current` 指向新 SHA。切换失败时自动启动上次已验收镜像；首次部署失败时仅停止本应用的容器。GitHub job 仍然失败，回滚不会掩盖发布失败。

VM 不安装 npm/uv、不构建镜像，也不保存 GitHub PAT。部署不运行 seed、不覆盖已有数据库、不操作其他 Compose 项目。容器替换期间可能出现短暂不可用；当前方案没有实现无中断切换。

## 首次服务器配置

当前约定：VM `20.46.166.104`，SSH 用户 `jnove`，部署根 `/home/jnove/steelyard`，Docker 外部网络 `jnoves-blog_default`。部署用户需要 Docker 权限、Bash、Python 3 标准库、`flock`、`tar`、`gzip`、`sha256sum` 与支持 `up --wait` 的 Docker Compose。

```text
/home/jnove/steelyard/
├── shared/
│   ├── data/                 SQLite 与部署前在线备份
│   ├── runtime.env           LLM 等运行时配置，chmod 600
│   └── deploy.env            网络、端口与公开 origin，chmod 600
├── releases/<commit SHA>/    经校验的版本源码与规则
├── incoming/                上传暂存；镜像加载后清理
├── current -> releases/SHA   最后一次验收成功的版本
└── deploy.lock
```

创建 `shared/data`，并在 `shared/runtime.env` 写入：

```dotenv
LLM_PROVIDER=fake
```

在 `shared/deploy.env` 写入：

```dotenv
STEELYARD_PROXY_NETWORK=jnoves-blog_default
STEELYARD_HTTP_PORT=18081
STEELYARD_PUBLIC_ORIGIN=https://project.jnove.dpdns.org
```

Compose 固定 `APP_ENV=prod`、数据库 `sqlite:////app/data/zhuheng.db`，并按公开 origin 设置 CORS。`prod` 关闭开发规则热重载入口。数据库目录独立于 release；规则从该 release 的 `rules/` 只读挂载。backend 只在本应用网络内可见，frontend 同时连接本应用与 Caddy 网络，并仅向宿主 `127.0.0.1:18081` 暴露本机验收端口。

`fake` 使用真实后端评估、排序和 SSE 链路，报告文本由确定性桩生成。要启用真实模型，直接修改服务器 `runtime.env`，增加 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，随后重新部署。密钥不写入源码、artifact 或前端构建。部署的公开 SSE 验收会调用当前配置的模型；真实模式下需要可用的模型服务，失败会阻止发布并触发容器回滚。

## GitHub 配置

在本仓库的 `production` environment 设置以下 Actions Secrets；不保留 repository 全局副本：

| Secret | 用途 |
| --- | --- |
| `STEELYARD_SSH_KEY` | 仅用于本应用部署的私钥；对应公钥写入 VM 部署用户 authorized_keys |
| `STEELYARD_SSH_KNOWN_HOSTS` | 从可信现有 SSH 连接核验的服务器 host key 条目 |

`production` environment 的 deployment branch policy 仅允许 `main`，不设置等待计时器或人工审批，使 main push 通过检查后自动发布。Secrets 仅在实际进入该 environment 的部署 job 可用。

设置以下 Actions Variables：

| Variable | 当前值 |
| --- | --- |
| `STEELYARD_SSH_HOST` | `20.46.166.104` |
| `STEELYARD_SSH_USER` | `jnove` |
| `STEELYARD_DEPLOY_ROOT` | `/home/jnove/steelyard` |
| `STEELYARD_PUBLIC_URL` | `https://project.jnove.dpdns.org/steelyard` |

SSH 启用 `StrictHostKeyChecking=yes`、`BatchMode=yes` 与 `IdentitiesOnly=yes`，工作流不实时信任 `ssh-keyscan` 返回的陌生 key。主机 key 变更后，需要先独立核验，再更新 Secret。专用部署 key 和 Docker 权限仍允许管理该用户可访问的容器，应只向受信任的 main 工作流提供。

## Caddy 与子路径

博客仓库在 VM 的 `/home/jnove/jnoves-blog/Caddyfile` 持久维护入口，并挂载到 `blog-caddy:/etc/caddy/Caddyfile`。必须将 Steelyard 路由提交到博客仓库，使博客后续更新不会移除它。在 `project.jnove.dpdns.org` 的其他兜底路由之前加入等效配置：

```caddyfile
redir /steelyard /steelyard/ 308
handle /steelyard/* {
    reverse_proxy steelyard-frontend:8080 {
        flush_interval -1
    }
}
```

Caddy 与 frontend 共享 `jnoves-blog_default`，以独立 alias `steelyard-frontend` 访问本应用。使用 `handle` 保留 `/steelyard` 前缀。frontend Nginx 将 `/steelyard/api/` 转到私有网络 `steelyard-backend:8000/api/`；对 SSE 关闭缓冲、缓存，并保留长连接超时。Caddy 对 `/steelyard` 跳转到 `/steelyard/`；直连本机 Nginx 时也使用相对跳转，并通过 `absolute_redirect off` 保留访问域名与端口。SPA 深链接回退到本应用 `index.html`，不存在的脚本仍返回 404。

开发模式默认 `VITE_BASE_PATH=/`，React Router、REST 和 SSE 继续使用根路径。设置 `VITE_BASE_PATH=/steelyard/` 时，Vite 资源、Router basename、默认 API 地址同步为此子路径；显式设置 `VITE_API_BASE` 可覆盖默认 API 地址。每次修改公开 base 后必须重新构建前端镜像。

## 验收、回滚与维护

`scripts/deploy_smoke.py` 检查 base 跳转、SPA 深链接、每个入口资源、缺失脚本 404、`release.json` 的精确 SHA、health/rules/schema/projects，以及 POST SSE 的首帧与最终 `done`。完整 SSE 验收创建一个 `__deployment_smoke__<SHA>` 临时项目，用仓库的两套虚构 fixture 运行真实后端链路，结束或失败时重试删除该项目及其子数据。此检查确认应用协议与部署可用性，不能作为真实工程规则、规范出处或评价结论的验证。

所有冒烟请求使用明确的 `User-Agent: SteelyardDeployment/1.0`，避免入口将默认 Python 客户端 UA 误拒绝；服务器实际运行的公开验收仍是最终依据。

登录 VM 后可检查：

```bash
root=/home/jnove/steelyard
sha=$(basename "$(readlink -f "$root/current")")
STEELYARD_ROOT="$root" STEELYARD_RELEASE="$sha" docker compose \
  --project-name steelyard --env-file "$root/shared/deploy.env" \
  --project-directory "$root/releases/$sha" \
  -f "$root/releases/$sha/docker-compose.production.yml" ps
python3 "$root/current/scripts/deploy_smoke.py" \
  --url https://project.jnove.dpdns.org/steelyard --sha "$sha"
```

手工回滚到仍保有镜像与源码的已验收 SHA：

```bash
root=/home/jnove/steelyard
sha='替换为已验收的40位commit-SHA'
bash "$root/releases/$sha/scripts/deploy.sh" "$root" "$sha" \
  https://project.jnove.dpdns.org/steelyard
```

每次替换前对当前 SQLite 做在线备份，存于 `shared/data/backups/`。正常部署和回滚均强制重建 frontend 与 backend，使 Nginx 在 backend 地址变更后重新解析 Docker DNS；同 SHA 重新部署也可更新 runtime 配置。自动回滚只恢复容器与规则版本，保留用户数据库及当前 runtime 配置。当前启动仅建表；未来增加不兼容数据库迁移时，须单独设计迁移与数据恢复策略，不能假定旧镜像仍可读取新 Schema。

发布包在加载后删除；中途中断可能留下 `incoming/` 文件。旧 release、旧镜像标签与数据库备份会保留，需要按磁盘空间定期清理，并保留 `current` 与至少一个已验收回滚版本。只清理明确属于 Steelyard 的旧文件和镜像，避免影响本机其他站点。

排障时先检查 GitHub 失败步骤和本应用 Compose 状态；日志可能包含业务输入，分享前检查内容。不要输出展开后的完整 `docker compose config` 或 runtime.env。部署成功应以 GitHub 部署 job 成功、公开 SHA 一致及冒烟检查通过为证据，单独 `health=ok` 不能证明已更新。

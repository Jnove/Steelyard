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

### 初筛版本冻结

冻结节点与材料安排以 [交付计划](submission-plan.md) 为准。冻结后限制 `main` 的合并与 push，只处理阻断演示或影响事实准确性的必要修复；这由团队协作执行，CI 不会自动阻止发布。记录已验收的提交 SHA、公开部署版本和备用源码包，保留可回滚版本。必要修复发布后，重新验收受影响链路并同步视频、报告与技术说明，确保材料对应实际可访问的版本。

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
STEELYARD_UID=1000
STEELYARD_GID=1000
```

Compose 固定 `APP_ENV=prod`、数据库 `sqlite:////app/data/zhuheng.db`，并按公开 origin 设置 CORS。`prod` 关闭开发规则热重载入口。数据库目录独立于 release；规则从该 release 的 `rules/` 只读挂载。`backend` 只在本应用网络内可见，`steelyard-frontend` 同时连接本应用与 Caddy 网络，并仅向宿主 `127.0.0.1:18081` 暴露本机验收端口。Compose 会自动把服务名注册为 Docker DNS alias，因此生产服务名也采用 `steelyard-frontend`，避免与博客的 `frontend` 冲突；runner 在发布前检查实际网络 aliases。

生产 backend 使用宿主部署用户的 UID:GID（默认 `1000:1000`，由 `STEELYARD_UID/GID` 覆盖），并保留 `cap_drop: ALL`。`shared/data` 必须归属此 UID:GID，目录可设为 `0700`；已有 SQLite 文件及备份也需由该用户读写。确认宿主 `id -u`、`id -g` 后填写配置，勿依赖 root 绕过数据目录权限。镜像里的应用、虚拟环境与 release 的规则需要对该用户可读。CI 使用 runner 的实际 UID:GID，并在启动前以同一用户检查模块导入、只读规则加载与数据卷写入；失败时先打印仅含 fake 配置的 CI 容器日志再清理。

`fake` 使用真实后端评估、排序和 SSE 链路，报告文本由确定性桩生成。要启用真实模型，直接修改服务器 `runtime.env`，增加 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，随后重新部署。密钥不写入源码、artifact 或前端构建。部署的公开 SSE 验收会调用当前配置的模型；真实模式下需要可用的模型服务，失败会阻止发布并触发容器回滚。

模型服务支持时可设置 `LLM_REASONING_EFFORT=low`，留空则不发送此参数；不要假定所有兼容服务都支持相同强度。参数用法见 [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 与 [DeepSeek 思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)，最终以所配置服务实测为准。

当前 DeepSeek 兼容服务实测可用 `LLM_REASONING_EFFORT=none` 缩短简短追问与建议的等待；同一服务的其他开关可能被忽略，切换服务后应重新验证。模型返回空响应时最多重试一次；隐藏思考不作为正文，明确被截断的输出不作为成功结果。建议只接收必要的项目摘要，总预算为 45 秒；超时后页面提供重试提示，日志仅记录失败阶段、异常类型与耗时。对话历史仅保留最近的必要片段，已有结果与条文在解释节点一次读取，避免重复调用模型取同一份证据。

模型传输统一使用 `stream=true`；建议问题与只读计划在后端汇总正文或工具调用后，仍按原有 JSON 接口返回。2026-10-23 实测当前网关对非流式请求返回 HTTP 200、`text/event-stream`，但只有空 `choices` 和零输出；同模型的显式流式请求可正常返回正文及工具调用。遇到类似故障应分别检查实际响应协议和内容，不能仅凭 HTTP 200 或容器健康判定可用；发布后需验证建议生成、`/plan` 意图解析及 `/chat` 最终 `done`。

自然语言计划格式未通过校验时，按原始请求纠正并重试一次，仍受 `/plan` 的 45 秒总预算限制。例如“从 0.72 调整为 0.85”的修改计划必须使用 `scheme_id`、`field`、`value`，不能用 `from/to` 代替接口字段。重试只解析，不修改数据；持续格式错误、非法字段、方案归属不符或目标不明确时仍拒绝执行。预览原值由后端读取，用户确认后才创建推演副本。

建议与默认问答使用中文资料名称、定性的指标比较，不向模型重复传入字段字典、长篇规范和计算表。普通追问直接生成短答，具体分数、公式和编号按明确追问提供，原始工具证据仍用于数字核验和溯源。建议按项目输入、评估与权重状态、所选方案及模型配置缓存五分钟；手动“刷新建议”通过 `refresh=true` 重新生成。缓存复用派生结果表，项目或方案删除时一并清理，缓存故障不会阻断已生成的有效建议。

普通回答先解释当前方案的优势、代价与调整结果，只在影响本问时简短说明限制，不机械以“先补资料再看排名”收尾。案例说明仍随证据保留，教学参数不作为实测成效，明确未通过或排除不省略；用户主动询问合规、缺项和依据时说明相应边界。已有评估的建议问题优先讨论方案差异和选择取舍，避免连续生成资料审查问题。
提示级规则单独作为“专项与施工提示”传递，例如触发专家论证程序不代表论证未通过或尚未办理；硬约束错误仍列入需处理问题和排除信息。此区分只影响解释，不更改规则状态、严重级别、评分或排名。
定性比较分别传递原始指标值和指标得分的高低关系，避免把“越少越好”的风险指标得分较高误说成风险指数较高；摘要不新增计算值或工程结论。

默认精简报告直接使用确定性评分、关键问题与排名摘要，仅由模型组织最终文字，不重复调用意图解析及四份维度评语；完整结果保留用于溯源。普通页面追问走只读解释，参数修改仍使用明确的假设推演入口。模型请求超过整条链路的 110 秒预算会发出中文 `error` 并关闭连接，不会持续只发心跳。思考模式的内部内容仅用于模型工具回合续接，不写进报告或 SSE。

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

Caddy 与 `steelyard-frontend` 服务共享 `jnoves-blog_default`，以同名的唯一 DNS alias 访问本应用。使用 `handle` 保留 `/steelyard` 前缀。前端 Nginx 将 `/steelyard/api/` 转到私有网络 `steelyard-backend:8000/api/`；对 SSE 关闭缓冲、缓存，并保留长连接超时。Caddy 对 `/steelyard` 跳转到 `/steelyard/`；直连本机 Nginx 时也使用相对跳转，并通过 `absolute_redirect off` 保留访问域名与端口。SPA 深链接回退到本应用 `index.html`，不存在的脚本仍返回 404。

Git 更新可能替换宿主 Caddyfile 的 inode，而运行中容器的单文件 bind mount 仍指向旧文件。博客部署工作流与手工操作应从宿主最新文件读取配置；在 `/home/jnove/jnoves-blog` 执行：

```bash
docker exec -i blog-caddy caddy validate --config - --adapter caddyfile < Caddyfile
docker exec -i blog-caddy caddy reload --config - --adapter caddyfile < Caddyfile
```

以公开路径的跳转和实际响应验证生效。仅查看容器内文件或从挂载文件重载，可能仍读到旧配置。

开发模式默认 `VITE_BASE_PATH=/`，React Router、REST 和 SSE 继续使用根路径。设置 `VITE_BASE_PATH=/steelyard/` 时，Vite 资源、Router basename、默认 API 地址同步为此子路径；显式设置 `VITE_API_BASE` 可覆盖默认 API 地址。每次修改公开 base 后必须重新构建前端镜像。

## 验收、回滚与维护

`scripts/deploy_smoke.py` 检查 base 跳转、SPA 深链接、每个入口资源、缺失脚本 404、`release.json` 的精确 SHA、health/rules/schema/projects，以及 POST SSE 的首帧与最终 `done`。完整 SSE 验收创建一个 `__deployment_smoke__<SHA>` 临时项目，用仓库的两套虚构 fixture 运行真实后端链路，结束或失败时重试删除该项目及其子数据。此检查确认应用协议与部署可用性，不能作为真实工程规则、规范出处或评价结论的验证。

公网入口会被 Cloudflare 注入动态脚本，首页与深链接的 HTML 不保证字节相同。公开验收比较 HTML 类型、应用标题、React 挂载点及相同的入口脚本和样式资源，并继续严格检查资源可访问性与发布 SHA。CI 和 VM 本机直连使用 `--strict-html`，另外要求深链接与首页的 HTML 完全相同。

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

每次替换前对当前 SQLite 做在线备份，存于 `shared/data/backups/`。正常部署和回滚均强制重建 `steelyard-frontend` 与 `backend`，使 Nginx 在 backend 地址变更后重新解析 Docker DNS；同 SHA 重新部署也可更新 runtime 配置。`--remove-orphans` 仅清理 `steelyard` 项目内被改名或移除的服务，不会清理博客容器。自动回滚只恢复容器与规则版本，保留用户数据库及当前 runtime 配置。当前启动仅建表；未来增加不兼容数据库迁移时，须单独设计迁移与数据恢复策略，不能假定旧镜像仍可读取新 Schema。

发布包在加载后删除；中途中断可能留下 `incoming/` 文件。旧 release、旧镜像标签与数据库备份会保留，需要按磁盘空间定期清理，并保留 `current` 与至少一个已验收回滚版本。只清理明确属于 Steelyard 的旧文件和镜像，避免影响本机其他站点。

排障时先检查 GitHub 失败步骤和本应用 Compose 状态；日志可能包含业务输入，分享前检查内容。不要输出展开后的完整 `docker compose config` 或 runtime.env。部署成功应以 GitHub 部署 job 成功、公开 SHA 一致及冒烟检查通过为证据，单独 `health=ok` 不能证明已更新。

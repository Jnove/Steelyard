#!/usr/bin/env bash
# 只负责 steelyard Compose 项目；调用前已校验归档并加载对应 SHA 的镜像。
set -Eeuo pipefail

root=${1:?deployment root is required}
sha=${2:?commit SHA is required}
public_url=${3:?public URL is required}
[[ "$root" =~ ^/[a-zA-Z0-9_./-]+$ && "$root" != / ]] || exit 2
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$public_url" =~ ^https://[a-zA-Z0-9./:_-]+$ ]] || exit 2
root=$(realpath "$root")
release="$root/releases/$sha"
[[ -f "$release/docker-compose.production.yml" ]] || exit 2
[[ -f "$root/shared/runtime.env" && -f "$root/shared/deploy.env" ]] || {
  echo "Missing shared/runtime.env or shared/deploy.env; complete server setup first." >&2
  exit 2
}

# GitHub concurrency 不保证 FIFO；服务器锁也覆盖手工部署。
exec 9>"$root/deploy.lock"
flock -w 600 9
previous=""
if [[ -L "$root/current" ]]; then
  previous=$(basename "$(readlink -f "$root/current")")
  [[ "$previous" =~ ^[0-9a-f]{40}$ ]] || exit 2
fi

compose_for() {
  local revision=$1
  shift
  STEELYARD_ROOT="$root" STEELYARD_RELEASE="$revision" docker compose \
    --project-name steelyard --env-file "$root/shared/deploy.env" \
    --project-directory "$root/releases/$revision" \
    -f "$root/releases/$revision/docker-compose.production.yml" "$@"
}

armed=false
rollback() {
  local status=$?
  [[ "$status" != 0 ]] || status=1
  trap - ERR INT TERM
  if [[ "$armed" == true ]]; then
    if [[ -n "$previous" ]]; then
      echo "Deployment failed; restoring containers for $previous." >&2
      if compose_for "$previous" up -d --remove-orphans --force-recreate --no-build --pull never --wait --wait-timeout 180; then
        if ! python3 "$root/releases/$previous/scripts/deploy_smoke.py" \
          --url "$public_url" --sha "$previous" --skip-sse; then
          echo "Previous containers restarted, but public rollback verification failed." >&2
        fi
      else
        echo "Rollback failed; inspect the steelyard Compose project on the VM." >&2
      fi
    else
      echo "First deployment failed; stopping only the steelyard containers." >&2
      compose_for "$sha" stop || true
    fi
  fi
  exit "${status:-1}"
}
trap rollback ERR INT TERM

docker image inspect "steelyard-backend:$sha" "steelyard-frontend:$sha" >/dev/null
for image in steelyard-backend steelyard-frontend; do
  revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image:$sha")
  [[ "$revision" == "$sha" ]]
done
# 仅校验，不输出展开后的 Compose（其中包含运行时 Secrets）。
compose_for "$sha" config --quiet

if [[ -n "$previous" ]]; then
  # SQLite 在线备份保留一致性；代码回滚不会自动覆盖用户数据库。
  compose_for "$previous" exec -T backend python - <<'PY'
import datetime
import pathlib
import sqlite3

directory = pathlib.Path('/app/data/backups')
directory.mkdir(exist_ok=True)
target = directory / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
with sqlite3.connect('/app/data/zhuheng.db') as source, sqlite3.connect(target) as backup:
    source.backup(backup)
PY
fi

armed=true
compose_for "$sha" up -d --remove-orphans --force-recreate --no-build --pull never --wait --wait-timeout 180
port=$(compose_for "$sha" port steelyard-frontend 8080)
python3 "$release/scripts/deploy_smoke.py" --url "http://$port/steelyard" --sha "$sha" --skip-sse --strict-html
python3 "$release/scripts/deploy_smoke.py" --url "$public_url" --sha "$sha"

# 只有容器健康、子路径、公开 SHA、API 与完整 SSE 均通过，才推进 current。
next_link="$root/.current-$sha-$$"
ln -s "$release" "$next_link"
mv -Tf "$next_link" "$root/current"
armed=false
echo "Deployed $sha to $public_url"

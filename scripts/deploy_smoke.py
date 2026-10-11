"""验收部署路径与 POST SSE；临时虚构项目仅用于应用协议测试，最终删除。"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def request(url: str, method: str = "GET", body: dict | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": "SteelyardDeployment/1.0"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.urlopen(  # noqa: S310 - URL comes from the deployment CLI
        urllib.request.Request(url, payload, headers, method=method), timeout=45
    )


def read_json(url: str, method: str = "GET", body: dict | None = None):
    with request(url, method, body) as response:
        return json.load(response)


def check_site(url: str, sha: str) -> None:
    with request(url) as response:
        assert response.url == f"{url}/", "App base redirect changed origin or lost prefix"
    with request(f"{url}/") as response:
        html = response.read().decode()
        assert "text/html" in response.headers.get("Content-Type", ""), "SPA MIME type"
    with request(f"{url}/projects/999999/schemes") as response:
        assert response.read().decode() == html, "SPA deep link does not return index.html"
    assets = re.findall(r'(?:src|href)="([^\"]+/assets/[^\"]+)"', html)
    assert assets, "No prefixed Vite assets in index.html"
    origin = urllib.parse.urlsplit(url)
    prefix = origin.path.rstrip("/") + "/assets/"
    for asset in assets:
        assert asset.startswith(prefix), f"Asset escaped app base: {asset}"
        with request(f"{origin.scheme}://{origin.netloc}{asset}") as response:
            assert response.status == 200, f"Missing asset: {asset}"
    try:
        with request(f"{url}/assets/__missing_deployment_probe__.js"):
            raise AssertionError("Missing script returned success instead of 404")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, f"Missing script returned {exc.code}"
    assert read_json(f"{url}/release.json")["commit"] == sha, "Public commit SHA mismatch"
    assert read_json(f"{url}/api/health")["status"] == "ok", "Backend health"
    assert read_json(f"{url}/api/rules")["rule_count"] > 0, "Rules did not load"
    assert "project_params" in read_json(f"{url}/api/schema"), "Schema did not load"
    assert isinstance(read_json(f"{url}/api/projects"), list), "Project API"


def check_sse(url: str, sha: str) -> None:
    fixtures = Path(__file__).resolve().parents[1] / "data" / "schemes" / "mock"
    project = json.loads((fixtures / "project.json").read_text(encoding="utf-8"))
    created = read_json(
        f"{url}/api/projects",
        "POST",
        {"name": f"__deployment_smoke__{sha}", "params": project["params"]},
    )
    project_url = f"{url}/api/projects/{created['id']}"
    try:
        for prefix in ("A_", "D_"):
            fixture = next(fixtures.glob(f"{prefix}*.json"))
            scheme = json.loads(fixture.read_text(encoding="utf-8"))
            read_json(
                f"{project_url}/schemes", "POST", {"name": scheme["name"], "params": scheme["params"]}
            )
        deadline = time.monotonic() + 120
        event = ""
        saw_start = False
        with request(
            f"{project_url}/chat", "POST", {"intent": "new_eval", "message": "生成方案比选报告"}
        ) as response:
            assert "text/event-stream" in response.headers.get("Content-Type", ""), "SSE MIME type"
            for raw in response:
                assert time.monotonic() < deadline, "SSE did not terminate within 120 seconds"
                line = raw.decode().strip()
                if line.startswith("event:"):
                    event = line[6:].strip()
                    if not saw_start:
                        assert time.monotonic() < deadline - 100, "SSE first event was buffered for over 20 seconds"
                    saw_start |= event == "node_start"
                elif line.startswith("data:") and event == "error":
                    raise AssertionError(f"SSE failed: {json.loads(line[5:])}")
                elif line.startswith("data:") and event == "done":
                    result = json.loads(line[5:])
                    assert saw_start and result["report"].strip(), "SSE missing nodes or final report"
                    return
        raise AssertionError("SSE closed without done")
    finally:
        for attempt in range(3):
            try:
                with request(project_url, "DELETE") as response:
                    assert response.status == 204, "Temporary project cleanup"
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    break
                if attempt == 2:
                    raise
                time.sleep(1)
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--skip-sse", action="store_true")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    check_site(url, args.sha)
    if not args.skip_sse:
        check_sse(url, args.sha)
    print(f"Verified {args.sha}: SPA/assets/API" + ("/POST SSE done" if not args.skip_sse else ""))


if __name__ == "__main__":
    main()

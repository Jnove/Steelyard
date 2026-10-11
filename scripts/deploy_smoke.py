"""验收部署路径与 POST SSE；临时虚构项目仅用于应用协议测试，最终删除。"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
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


@dataclass(frozen=True)
class SPAShell:
    title: str
    scripts: tuple[str, ...]
    stylesheets: tuple[str, ...]


class SPAShellParser(HTMLParser):
    """只取应用入口；CDN 的动态 script type、注入脚本与统计标记不参与比较。"""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title = False
        self.root_count = 0
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "div" and values.get("id") == "root":
            self.root_count += 1
        if tag == "script":
            source = values.get("src")
            if source and "/assets/" in urllib.parse.urlsplit(source).path:
                self.scripts.append(source)
        if tag == "link" and "stylesheet" in (values.get("rel") or "").lower().split():
            source = values.get("href")
            if source and "/assets/" in urllib.parse.urlsplit(source).path:
                self.stylesheets.append(source)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def parse_spa_shell(html: str, prefix: str) -> SPAShell:
    parser = SPAShellParser()
    parser.feed(html)
    parser.close()
    title = "".join(parser.title_parts).strip()
    assert title, "SPA title is missing"
    assert parser.root_count == 1, "SPA root mount is missing or duplicated"
    assert parser.scripts, "No Vite entry scripts in index.html"
    assert parser.stylesheets, "No Vite entry stylesheets in index.html"
    for asset in (*parser.scripts, *parser.stylesheets):
        assert asset.startswith(prefix), f"Asset escaped app base: {asset}"
    return SPAShell(title, tuple(parser.scripts), tuple(parser.stylesheets))


def check_site(url: str, sha: str, *, strict_html: bool = False) -> None:
    origin = urllib.parse.urlsplit(url)
    prefix = origin.path.rstrip("/") + "/assets/"
    index_url = f"{url}/"
    deep_url = f"{url}/projects/999999/schemes"
    with request(url) as response:
        assert response.url == index_url, "App base redirect changed origin or lost prefix"
    with request(index_url) as response:
        assert response.url == index_url, "SPA index redirected away from its canonical URL"
        html = response.read().decode()
        assert response.headers.get("Content-Type", "").split(";")[0] == "text/html", "SPA MIME type"
    with request(deep_url) as response:
        assert response.url == deep_url, "SPA deep link redirected away from its requested route"
        deep_html = response.read().decode()
        assert response.headers.get("Content-Type", "").split(";")[0] == "text/html", "SPA deep link MIME type"
    shell = parse_spa_shell(html, prefix)
    assert parse_spa_shell(deep_html, prefix) == shell, "SPA deep link returned a different app shell"
    if strict_html:
        assert deep_html == html, "SPA deep link does not return identical origin index.html"
    for asset in (*shell.scripts, *shell.stylesheets):
        asset_url = f"{origin.scheme}://{origin.netloc}{asset}"
        with request(asset_url) as response:
            assert response.status == 200, f"Missing asset: {asset}"
            assert response.url == asset_url, f"Asset redirected away from its real URL: {asset}"
            media_type = response.headers.get("Content-Type", "").split(";")[0]
            expected_types = ("text/css",) if asset in shell.stylesheets else (
                "text/javascript", "application/javascript", "application/x-javascript"
            )
            assert media_type in expected_types, f"Wrong asset MIME type: {asset}: {media_type}"
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
    parser.add_argument("--strict-html", action="store_true", help="Require identical origin HTML; omit behind a CDN")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    check_site(url, args.sha, strict_html=args.strict_html)
    if not args.skip_sse:
        check_sse(url, args.sha)
    print(f"Verified {args.sha}: SPA/assets/API" + ("/POST SSE done" if not args.skip_sse else ""))


if __name__ == "__main__":
    main()

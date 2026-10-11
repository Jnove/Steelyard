"""部署验收在 CDN 改写 HTML 后仍识别正确 SPA，并拒绝错误入口或资源。"""

from __future__ import annotations

import importlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

BASE = "https://project.example/steelyard"
SHA = "a" * 40
HTML = """<!doctype html><html><head><title>筑衡 · 建筑方案智能比选</title>
<script type="module" src="/steelyard/assets/main-a.js"></script>
<link rel="stylesheet" href="/steelyard/assets/main-a.css"></head>
<body><div id="root"></div></body></html>"""


def cloudflare_html(marker: str) -> str:
    # Rocket Loader 重写 module type；JS detection 与 beacon 每次请求可变。
    return HTML.replace('type="module"', f'type="{marker}-module"').replace(
        "</body>",
        f'<script src="/cdn-cgi/scripts/rocket-loader.min.js" data-cf-settings="{marker}"></script>'
        f'<script>window.__CF$cv$params={{r:"{marker}"}};</script>'
        '<script src="https://static.cloudflareinsights.com/beacon.min.js"></script></body>',
    )


@pytest.fixture
def smoke(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    return importlib.import_module("scripts.deploy_smoke")


class Response(io.BytesIO):
    def __init__(self, body: str, url: str, content_type: str = "text/html") -> None:
        super().__init__(body.encode())
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": content_type}


def fake_site(monkeypatch, smoke, root_html: str, deep_html: str, *, deep_type="text/html",
              asset_type="application/javascript", asset_redirect=False, index_redirect=False,
              deep_redirect=False):
    calls = []
    json_routes = {
        "/release.json": {"commit": SHA},
        "/api/health": {"status": "ok"},
        "/api/rules": {"rule_count": 1},
        "/api/schema": {"project_params": {}},
        "/api/projects": [],
    }

    def request(url, method="GET", body=None):
        calls.append(url)
        assert method == "GET" and body is None
        if url == BASE:
            return Response(root_html, BASE + "/")
        if url == BASE + "/":
            return Response(root_html, "https://project.example/" if index_redirect else url)
        if url == BASE + "/projects/999999/schemes":
            return Response(deep_html, BASE + "/" if deep_redirect else url, deep_type)
        if url == BASE + "/assets/main-a.js":
            return Response("console.log('ok')", BASE + "/" if asset_redirect else url, asset_type)
        if url == BASE + "/assets/main-a.css":
            return Response("body{}", url, "text/css")
        if url == BASE + "/assets/__missing_deployment_probe__.js":
            raise urllib.error.HTTPError(url, 404, "Not found", {}, None)
        for path, result in json_routes.items():
            if url == BASE + path:
                return Response(json.dumps(result), url, "application/json")
        raise AssertionError(f"Unexpected request: {url}")

    monkeypatch.setattr(smoke, "request", request)
    return calls


def test_public_spa_accepts_dynamic_cdn_scripts_and_checks_real_resources(smoke, monkeypatch):
    calls = fake_site(monkeypatch, smoke, cloudflare_html("request-1"), cloudflare_html("request-2"))
    smoke.check_site(BASE, SHA)
    assert BASE + "/assets/main-a.js" in calls
    assert BASE + "/assets/main-a.css" in calls
    assert BASE + "/assets/__missing_deployment_probe__.js" in calls
    assert BASE + "/release.json" in calls
    assert all("cdn-cgi" not in url and "cloudflareinsights" not in url for url in calls)


@pytest.mark.parametrize(
    ("deep_html", "message"),
    [
        (HTML.replace("筑衡 · 建筑方案智能比选", "其他站点"), "different app shell"),
        (HTML.replace('id="root"', 'id="other"'), "root mount"),
        (HTML.replace("main-a.js", "main-b.js"), "different app shell"),
        (HTML.replace("main-a.css", "main-b.css"), "different app shell"),
        (HTML.replace("/steelyard/assets/", "/other/assets/"), "escaped app base"),
        (HTML.replace('<div id="root"></div>', '<div id="root"></div><div id="root"></div>'), "root mount"),
    ],
)
def test_public_spa_rejects_wrong_shell(smoke, monkeypatch, deep_html, message):
    fake_site(monkeypatch, smoke, HTML, deep_html)
    with pytest.raises(AssertionError, match=message):
        smoke.check_site(BASE, SHA)


def test_deep_link_must_have_html_mime(smoke, monkeypatch):
    fake_site(monkeypatch, smoke, HTML, HTML, deep_type="application/json")
    with pytest.raises(AssertionError, match="deep link MIME"):
        smoke.check_site(BASE, SHA)


@pytest.mark.parametrize("strict_html", [False, True])
@pytest.mark.parametrize(
    ("redirect", "message"),
    [("index_redirect", "SPA index redirected"), ("deep_redirect", "SPA deep link redirected")],
)
def test_spa_routes_must_keep_the_requested_url(smoke, monkeypatch, strict_html, redirect, message):
    fake_site(monkeypatch, smoke, HTML, HTML, **{redirect: True})
    with pytest.raises(AssertionError, match=message):
        smoke.check_site(BASE, SHA, strict_html=strict_html)


def test_origin_mode_keeps_exact_html_check(smoke, monkeypatch):
    fake_site(monkeypatch, smoke, HTML, HTML)
    smoke.check_site(BASE, SHA, strict_html=True)
    fake_site(monkeypatch, smoke, cloudflare_html("request-1"), cloudflare_html("request-2"))
    with pytest.raises(AssertionError, match="identical origin index.html"):
        smoke.check_site(BASE, SHA, strict_html=True)


@pytest.mark.parametrize(
    ("asset_type", "asset_redirect", "message"),
    [("text/html", False, "asset MIME"), ("application/javascript", True, "redirected away")],
)
def test_entry_resource_must_resolve_to_real_script(smoke, monkeypatch, asset_type, asset_redirect, message):
    fake_site(monkeypatch, smoke, HTML, HTML, asset_type=asset_type, asset_redirect=asset_redirect)
    with pytest.raises(AssertionError, match=message):
        smoke.check_site(BASE, SHA)

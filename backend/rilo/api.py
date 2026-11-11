"""Authenticated local API with durable experiment admission."""

from __future__ import annotations

import asyncio
import csv
import hmac
import io
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .catalog import public_source, public_task
from .config import Config, allowed_origins, redact
from .engine import InfrastructureError, bounded_json
from .evaluation import compare
from .schemas import (
    AgentCreate,
    AgentVersionCreate,
    BaselineCreate,
    ComparisonCreate,
    ExperimentCreate,
    SettingsUpdate,
    TaskCreate,
)
from .storage import Store, identifier

DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta name="color-scheme" content="dark light">
  <title>Rilo API reference</title>
  <link rel="icon" href="/docs-assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/docs-assets/reference.css">
  <script src="/docs-assets/reference.js" defer></script>
</head>
<body>
  <a class="skip" href="#operations">Skip to API operations</a>
  <header>
    <a class="brand" href="/" aria-label="Rilo workspace">rilo<span>API reference</span></a>
    <nav aria-label="Documentation links"><a href="/">Workspace</a><a href="/openapi.json">OpenAPI JSON</a></nav>
  </header>
  <main>
    <section class="intro" aria-labelledby="title">
      <p class="eyebrow">Local developer API</p>
      <h1 id="title">Build with Rilo.</h1>
      <p>Inspect the routes, request contracts, and schemas served by your installed version.</p>
      <p id="version" class="version"></p>
    </section>
    <details class="authentication" open>
      <summary>Local authentication</summary>
      <p>Browser clients call <code>GET /api/v1/session</code> to establish an HttpOnly session cookie. Send its returned <code>csrf_token</code> as <code>X-CSRF-Token</code> for mutations.</p>
      <p>CLI and SDK clients send <code>Authorization: Bearer &lt;local session key&gt;</code>, using the private <code>.rilo/session.key</code> file. Keep credential values private.</p>
      <p>This reference describes the API without executing mutations. JSON objects without a declared response schema are marked explicitly; inspect evidence reports for their documented fields.</p>
    </details>
    <form class="filters" role="search" autocomplete="off">
      <label for="search">Find an operation<input id="search" type="search" placeholder="Search a path or operation name"></label>
      <label for="method">HTTP method<select id="method"><option value="">All methods</option><option>GET</option><option>POST</option><option>PATCH</option><option>PUT</option><option>DELETE</option></select></label>
    </form>
    <p id="status" role="status" aria-live="polite">Loading the installed API schema…</p>
    <section id="operations" aria-label="API operations" tabindex="-1"></section>
    <section class="schemas" aria-labelledby="schema-title"><h2 id="schema-title">Data schemas</h2><div id="schemas"></div></section>
    <noscript><p>Enable JavaScript to browse operations, or open <a href="/openapi.json">the OpenAPI JSON schema</a> after establishing a local session.</p></noscript>
  </main>
  <footer>Rilo · Local API reference · Schema generated from the installed FastAPI routes</footer>
</body>
</html>"""

DOCS_CSS = """
:root{color-scheme:light dark;--bg:#f7f8fa;--panel:#fff;--ink:#172a36;--muted:#526571;--line:#d7e0e6;--accent:#187254;--code:#edf2f5;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);line-height:1.65}a{color:var(--accent);text-underline-offset:3px}header,main,footer{max-width:1100px;margin:auto;padding:24px}header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:24px}.brand{font-size:30px;font-weight:750;text-decoration:none;color:var(--ink);letter-spacing:-1px;display:flex;align-items:center;gap:14px}.brand span{font-size:13px;letter-spacing:0;font-weight:500;color:var(--muted);border-left:1px solid var(--line);padding-left:14px}nav{display:flex;gap:20px;font-size:14px}.intro{padding:30px 0 18px;max-width:720px}.eyebrow{text-transform:uppercase;font-size:11px;letter-spacing:2px;color:var(--accent);font-weight:700}h1{font-size:clamp(30px,5vw,46px);line-height:1.2;letter-spacing:-1.4px;margin:10px 0 18px}p{margin:10px 0}.intro>p:not(.eyebrow){color:var(--muted)}h2{font-size:22px;letter-spacing:-.5px}h3{font-size:15px;margin:22px 0 10px}.version{font-size:12px;font-family:ui-monospace,monospace}.authentication{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:18px 22px;font-size:14px}.authentication summary{font-weight:650}.authentication p{max-width:900px}.filters{display:grid;grid-template-columns:1fr 180px;gap:18px;align-items:end;margin:28px 0 14px}label{font-size:12px;font-weight:650;display:flex;flex-direction:column;gap:7px}input,select{width:100%;border:1px solid var(--line);border-radius:7px;color:var(--ink);background:var(--panel);padding:12px;font:inherit;font-size:14px}input:focus,select:focus,a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}#status{font-size:13px;color:var(--muted);min-height:24px}.operation,.schema{border:1px solid var(--line);border-radius:9px;margin:12px 0;background:var(--panel)}summary{cursor:pointer;list-style-position:outside;margin-left:16px}.operation>summary{padding:17px 18px 17px 4px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}.method{font:700 11px/1 ui-monospace,monospace;min-width:56px;text-align:center;border-radius:5px;padding:8px;background:#e6eff4;color:#20516b}.method-post{background:#e1f2e9;color:#176343}.method-patch{background:#fff0d6;color:#785016}.route{font-size:14px;overflow-wrap:anywhere}.operation-name{font-size:13px;color:var(--muted);margin-left:auto}.operation-body{padding:0 22px 24px}.description{font-size:14px;color:var(--muted)}.schema>summary{padding:14px 18px 14px 4px;font:600 13px ui-monospace,monospace}.schema>div{padding:0 18px 18px}.schema h3{margin-top:12px}code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}code{font-size:.91em;background:var(--code);padding:2px 5px;border-radius:4px}pre{font-size:12px;line-height:1.6;overflow:auto;background:var(--code);padding:16px;border-radius:7px;max-height:440px;white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top;overflow-wrap:anywhere}th{font-weight:650;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}.table-wrap{overflow-x:auto}.table-wrap table{min-width:500px}.response{font-size:13px}.response>strong{font-family:ui-monospace,monospace;margin-right:12px}.hint{font-size:12px;color:var(--muted)}.schema-links{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;margin:8px 0}.schemas{margin-top:35px}footer{border-top:1px solid var(--line);font-size:12px;color:var(--muted);padding-top:26px;padding-bottom:40px}.skip{position:absolute;left:18px;top:-80px;z-index:2;background:var(--panel);padding:8px}.skip:focus{top:10px}[hidden]{display:none!important}
@media(prefers-color-scheme:dark){:root{--bg:#121a20;--panel:#18242c;--ink:#edf3f7;--muted:#a4b6c0;--line:#35444e;--accent:#76d6b1;--code:#101a21}.method{background:#264450;color:#c0e5f5}.method-post{background:#234c3b;color:#b3edd2}.method-patch{background:#4e4228;color:#ffe0a3}}
@media(max-width:640px){header,main,footer{padding:18px}header{align-items:flex-start;flex-direction:column;gap:12px}nav{gap:18px}.filters{grid-template-columns:1fr}.operation-name{width:100%;margin-left:70px}.operation>summary{gap:10px;padding-right:12px}.operation-body{padding:0 14px 18px}.authentication{padding:15px}.brand{font-size:27px}}
"""

DOCS_JS = """
"use strict";
(() => {
  const element = (tag, text, className) => {
    const value = document.createElement(tag);
    if (text !== undefined) value.textContent = String(text);
    if (className) value.className = className;
    return value;
  };
  const operations = document.getElementById("operations");
  const schemas = document.getElementById("schemas");
  const status = document.getElementById("status");
  const search = document.getElementById("search");
  const method = document.getElementById("method");
  const cards = [];
  const schemaId = name => "schema-" + encodeURIComponent(name);
  const references = (value, output = new Set()) => {
    if (Array.isArray(value)) value.forEach(item => references(item, output));
    else if (value && typeof value === "object") {
      if (typeof value.$ref === "string" && value.$ref.startsWith("#/components/schemas/")) output.add(value.$ref.split("/").pop());
      Object.values(value).forEach(item => references(item, output));
    }
    return output;
  };
  const showSchema = (parent, schema) => {
    parent.append(element("pre", JSON.stringify(schema, null, 2)));
    const links = element("div", undefined, "schema-links");
    references(schema).forEach(name => {
      const link = element("a", name);
      link.href = "#" + schemaId(name);
      link.addEventListener("click", () => {
        const target = document.getElementById(schemaId(name));
        if (target) target.open = true;
      });
      links.append(link);
    });
    parent.append(links);
  };
  const contentSchemas = (parent, content) => {
    Object.entries(content || {}).forEach(([type, media]) => {
      parent.append(element("p", type, "hint"));
      const schema = media && typeof media === "object" ? media.schema : null;
      if (schema && Object.keys(schema).length) showSchema(parent, schema);
      else parent.append(element("p", "No structured response schema is declared for this media type.", "hint"));
    });
  };
  const typeName = schema => {
    if (!schema || typeof schema !== "object") return "unspecified";
    if (schema.$ref) return schema.$ref.split("/").pop();
    if (schema.anyOf) return schema.anyOf.map(typeName).join(" | ");
    if (schema.type === "array") return "array of " + typeName(schema.items);
    return schema.type || "object";
  };
  const applyFilter = () => {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    cards.forEach(card => {
      card.element.hidden = !card.text.includes(query) || Boolean(method.value && card.method !== method.value);
      if (!card.element.hidden) visible++;
    });
    status.textContent = visible ? visible + " of " + cards.length + " operations" : "No operations match this search.";
  };
  const render = schema => {
    document.getElementById("version").textContent = "Rilo " + (schema.info.version || "") + " · OpenAPI " + schema.openapi;
    const methods = new Set(["get", "post", "put", "patch", "delete", "head", "options"]);
    Object.entries(schema.paths).forEach(([path, entries]) => {
      Object.entries(entries).forEach(([verb, operation]) => {
        if (!methods.has(verb) || !operation || typeof operation !== "object") return;
        const card = element("details", undefined, "operation");
        const summary = element("summary");
        summary.append(element("span", verb.toUpperCase(), "method method-" + verb), element("code", path, "route"), element("span", operation.summary || operation.operationId || "", "operation-name"));
        const body = element("div", undefined, "operation-body");
        if (operation.description) body.append(element("p", operation.description, "description"));
        const parameters = [...(entries.parameters || []), ...(operation.parameters || [])];
        if (parameters.length) {
          body.append(element("h3", "Parameters"));
          const table = element("table");
          const head = element("tr");
          ["Name", "Location", "Type", "Required", "Description"].forEach(name => head.append(element("th", name)));
          const header = element("thead"); header.append(head); table.append(header);
          const rows = element("tbody");
          parameters.forEach(parameter => {
            const row = element("tr");
            [parameter.name || parameter.$ref, parameter.in || "", typeName(parameter.schema), parameter.required ? "yes" : "no", parameter.description || ""].forEach(value => row.append(element("td", value)));
            rows.append(row);
          });
          table.append(rows);
          const wrap = element("div", undefined, "table-wrap"); wrap.append(table); body.append(wrap);
        }
        if (operation.requestBody) {
          body.append(element("h3", "Request body" + (operation.requestBody.required ? " · required" : "")));
          contentSchemas(body, operation.requestBody.content);
        }
        body.append(element("h3", "Responses"));
        Object.entries(operation.responses || {}).forEach(([code, response]) => {
          const row = element("p", undefined, "response");
          row.append(element("strong", code), element("span", response.description || ""));
          body.append(row);
          contentSchemas(body, response.content);
        });
        card.append(summary, body);
        operations.append(card);
        cards.push({element: card, text: [path, verb, operation.summary, operation.description, operation.operationId].join(" ").toLowerCase(), method: verb.toUpperCase()});
      });
    });
    Object.entries((schema.components || {}).schemas || {}).sort(([a], [b]) => a.localeCompare(b)).forEach(([name, contract]) => {
      const card = element("details", undefined, "schema");
      card.id = schemaId(name);
      card.append(element("summary", name));
      const body = element("div"); showSchema(body, contract); card.append(body); schemas.append(card);
    });
    applyFilter();
  };
  document.querySelector("form").addEventListener("submit", event => event.preventDefault());
  search.addEventListener("input", applyFilter);
  method.addEventListener("change", applyFilter);
  const load = async () => {
    try {
      const session = await fetch("/api/v1/session", {credentials: "same-origin", cache: "no-store"});
      if (!session.ok) throw new Error("Local session could not be established.");
      await session.json();
      const response = await fetch("/openapi.json", {credentials: "same-origin", cache: "no-store"});
      if (!response.ok) throw new Error("OpenAPI schema could not be loaded (HTTP " + response.status + ").");
      const schema = await response.json();
      if (!schema || typeof schema.paths !== "object" || !schema.info) throw new Error("OpenAPI schema has an unexpected shape.");
      render(schema);
    } catch (error) {
      status.textContent = error instanceof Error ? error.message + " Refresh this local page to retry." : "The API reference could not be loaded. Refresh to retry.";
    }
  };
  load();
})();
"""

DOCS_ASSETS = {
    "reference.css": (DOCS_CSS, "text/css"),
    "reference.js": (DOCS_JS, "text/javascript"),
    "favicon.svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#187254"/><path d="M10 23V10h5v3c2-3 5-3 7-3v5c-5-1-7 1-7 4v4z" fill="white"/></svg>',
        "image/svg+xml",
    ),
}


def create_app(config: Config | None = None) -> FastAPI:
    settings = config or Config.load()
    store = Store(settings)
    origins = allowed_origins(settings.port)
    sessions: dict[str, tuple[str, float]] = {}
    requests: dict[str, deque] = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _ = settings.session_key
        store.recover()
        yield

    app = FastAPI(
        title="Rilo", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.state.store = store
    app.state.config = settings
    from .workspace_api import workspace_router

    app.include_router(workspace_router(store))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "Authorization",
            "Idempotency-Key",
            "Last-Event-ID",
            "X-Filename",
        ],
    )

    def secure_response(response: Response, request_id: str, api: bool = True) -> Response:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if api:
            response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    def failure(code: str, message: str, status: int, request_id: str = "") -> Response:
        return secure_response(
            JSONResponse(
                {
                    "error": {
                        "code": code,
                        "message": message,
                        "request_id": request_id,
                        "details": {},
                    }
                },
                status_code=status,
            ),
            request_id,
        )

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        try:
            host = urlsplit("http://" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            return failure("untrusted_host", "Rilo accepts local hosts only.", 403, request_id)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return failure(
                "untrusted_origin", "This browser origin is not allowed.", 403, request_id
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return failure("cross_site", "Cross-site requests are not allowed.", 403, request_id)
        protected = request.url.path.startswith("/api/") or request.url.path == "/openapi.json"
        body_limit = 8_000_000 if request.url.path == "/api/v1/workspace/uploads" else 64000
        if protected and request.method != "OPTIONS":
            queue = requests[request.client.host if request.client else "local"]
            while queue and queue[0] < time.monotonic() - 60:
                queue.popleft()
            if len(queue) > 600:
                return failure(
                    "rate_limit", "Local API request limit reached; retry shortly.", 429, request_id
                )
            queue.append(time.monotonic())
            if request.headers.get("content-length"):
                try:
                    if int(request.headers["content-length"]) > body_limit:
                        return failure(
                            "body_limit", "Request body exceeds the size limit.", 413, request_id
                        )
                except ValueError:
                    return failure(
                        "invalid_length", "Invalid request content length.", 400, request_id
                    )
            if request.method in {"POST", "PATCH", "PUT"}:
                body = bytearray()
                async for part in request.stream():
                    body.extend(part)
                    if len(body) > body_limit:
                        return failure(
                            "body_limit", "Request body exceeds the size limit.", 413, request_id
                        )
                request._body = bytes(body)
            if request.url.path != "/api/v1/session":
                auth = request.headers.get("authorization", "")
                bearer = auth.startswith("Bearer ") and hmac.compare_digest(
                    auth[7:], settings.session_key
                )
                cookie = request.cookies.get("rilo_session", "")
                cookie_session = sessions.get(cookie)
                if not bearer and (not cookie_session or cookie_session[1] < time.time()):
                    return failure(
                        "authentication_required",
                        "Open Rilo locally to establish a session.",
                        401,
                        request_id,
                    )
                if not bearer and request.method not in {"GET", "HEAD", "OPTIONS"}:
                    csrf = request.headers.get("x-csrf-token", "")
                    if not cookie_session or not hmac.compare_digest(csrf, cookie_session[0]):
                        return failure(
                            "csrf_required",
                            "Refresh the local session before changing data.",
                            403,
                            request_id,
                        )
        try:
            response = await call_next(request)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "Unexpected API failure (%s); request %s", type(exc).__name__, request_id
            )
            return failure(
                "internal_error",
                "The local service could not complete this request.",
                500,
                request_id,
            )
        return secure_response(response, request_id, protected)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return failure("request_error", str(exc.detail), exc.status_code, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"location": list(item["loc"]), "message": item["msg"]} for item in exc.errors()]
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Request fields are invalid.",
                    "request_id": request.state.request_id,
                    "details": details,
                }
            },
            status_code=422,
        )

    @app.exception_handler(KeyError)
    async def missing_item(request: Request, exc: KeyError):
        return failure(
            "not_found", "The requested item was not found.", 404, request.state.request_id
        )

    @app.exception_handler(ValueError)
    async def invalid_operation(request: Request, exc: ValueError):
        return failure(
            "invalid_operation",
            str(redact(str(exc), settings.secrets)),
            409,
            request.state.request_id,
        )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/docs", include_in_schema=False)
    @app.get("/redoc", include_in_schema=False)
    def api_reference() -> Response:
        return Response(DOCS_HTML, media_type="text/html")

    @app.get("/docs-assets/{name:path}", include_in_schema=False)
    def docs_asset(name: str) -> Response:
        if name not in DOCS_ASSETS:
            raise HTTPException(404, "Documentation asset not found.")
        content, media_type = DOCS_ASSETS[name]
        return Response(content, media_type=media_type, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/session")
    def session(request: Request) -> JSONResponse:
        cookie = request.cookies.get("rilo_session", "")
        current = sessions.get(cookie)
        if not current or current[1] < time.time():
            cookie, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
            sessions[cookie] = (csrf, time.time() + 86400)
        else:
            csrf = current[0]
        if len(sessions) > 200:
            for expired in [key for key, value in sessions.items() if value[1] < time.time()]:
                sessions.pop(expired, None)
            while len(sessions) > 200:
                sessions.pop(next(iter(sessions)))
        response = JSONResponse(
            {"csrf_token": csrf, "app_version": __version__, "workspace_name": "Local workspace"}
        )
        response.set_cookie(
            "rilo_session",
            cookie,
            httponly=True,
            samesite="strict",
            max_age=86400,
            secure=request.url.scheme == "https",
        )
        return response

    @app.get("/api/v1/agents")
    def agents() -> list[dict]:
        return store.catalog("agent")

    @app.post("/api/v1/agents", status_code=201)
    def create_agent(payload: AgentCreate) -> dict:
        return store.add_item(
            "agent",
            {
                "id": identifier("agent"),
                "name": payload.name,
                "description": payload.description,
                "framework": "HTTP endpoint",
                "kind": "http",
                "version": payload.version,
                "capabilities": ["final_output"],
                "config": {"endpoint": payload.endpoint},
            },
        )

    @app.get("/api/v1/agents/{agent_id}/versions")
    def agent_versions(agent_id: str) -> list[dict]:
        return store.agent_versions(agent_id)

    @app.post("/api/v1/agents/{agent_id}/versions", status_code=201)
    def create_agent_version(agent_id: str, payload: AgentVersionCreate) -> dict:
        return store.revise_agent(agent_id, payload.model_dump())

    @app.post("/api/v1/agents/{agent_id}/check")
    async def check_agent(agent_id: str) -> dict:
        agent = store.item("agent", agent_id)
        if agent["kind"] != "http":
            return {
                "status": "ready",
                "capabilities": agent["capabilities"],
                "detail": "Built-in workflow is available; model and live-search readiness are checked separately.",
            }
        async with httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False) as client:
            try:
                response = await client.get(agent["config"]["endpoint"])
                return {
                    "status": "reachable"
                    if response.status_code < 500 and not response.is_redirect
                    else "unavailable",
                    "capabilities": agent["capabilities"],
                    "detail": f"Local endpoint returned HTTP {response.status_code}; full run contract is checked during execution.",
                }
            except httpx.HTTPError:
                return {
                    "status": "unavailable",
                    "capabilities": agent["capabilities"],
                    "detail": "Local HTTP endpoint could not be reached.",
                }

    @app.get("/api/v1/tasks")
    def tasks() -> list[dict]:
        return [public_task(item) for item in store.catalog("task")]

    @app.get("/api/v1/suites")
    def suites() -> list[dict]:
        return [
            {
                "id": "research-v1",
                "name": "Research reliability",
                "version": "1.0",
                "task_ids": [item["id"] for item in store.catalog("task")],
                "description": "Versioned synthetic research tasks with deterministic evidence checks.",
            }
        ]

    @app.post("/api/v1/tasks", status_code=201)
    def create_task(payload: TaskCreate) -> dict:
        sources = [store.item("source", source_id) for source_id in payload.source_ids]
        for expected in payload.required_facts:
            if not any(expected in item["content"] for item in sources):
                raise ValueError("Every required fact must be a passage in the selected evidence.")
        item = {
            **payload.model_dump(mode="json"),
            "id": identifier("task"),
            "entity_id": sources[0]["entity_id"],
            "rubric": "custom",
        }
        return public_task(store.add_item("task", item))

    @app.get("/api/v1/scenarios")
    def scenarios() -> list[dict]:
        return store.catalog("scenario")

    @app.get("/api/v1/sources")
    def sources() -> list[dict]:
        return [public_source(item) for item in store.catalog("source")]

    async def integrations() -> dict:
        async def status(url: str, label: str, health_only: bool = False) -> dict:
            async with httpx.AsyncClient(
                timeout=2, trust_env=False, follow_redirects=False
            ) as client:
                try:
                    result = await bounded_json(client, "GET", url)
                    entries = result.get("models", result.get("data", []))
                    if not isinstance(entries, list):
                        raise InfrastructureError("The model-list response is malformed.")
                    models = [
                        item.get("name", item.get("id", ""))
                        for item in entries
                        if isinstance(item, dict)
                        and isinstance(item.get("name", item.get("id", "")), str)
                    ]
                    return {
                        "status": "reachable" if health_only else "ready",
                        "configured": True,
                        "detail": "Health endpoint is reachable; authentication and model responses are checked during real runs."
                        if health_only
                        else f"{label} returned its available model list; inference is checked during real runs.",
                        "models": models,
                    }
                except InfrastructureError:
                    return {
                        "status": "unavailable",
                        "configured": True,
                        "detail": f"{label} is not reachable at its configured local endpoint.",
                        "models": [],
                    }

        bifrost, ollama = await asyncio.gather(
            status(settings.bifrost_url + "/health", "Bifrost", health_only=True),
            status("http://127.0.0.1:11434/api/tags", "Ollama"),
        )
        return {
            "bifrost": {**bifrost, "credential_configured": bool(settings.bifrost_key)},
            "ollama": ollama,
            "tavily": {
                "status": "configured" if settings.tavily_key else "not_configured",
                "configured": bool(settings.tavily_key),
                "detail": "A private Tavily key is configured; actual retrieval is verified during live runs."
                if settings.tavily_key
                else "Set TAVILY_API_KEY in the private .env file and restart the services for live research.",
            },
        }

    @app.get("/api/v1/settings")
    async def get_settings() -> dict:
        return {
            "config": {
                "bifrost_url": settings.bifrost_url,
                "model": settings.model,
                "tavily_credit_limit": settings.tavily_credit_limit,
            },
            "integrations": await integrations(),
        }

    @app.patch("/api/v1/settings")
    async def save_settings(payload: SettingsUpdate) -> dict:
        settings.save(payload.bifrost_url or settings.bifrost_url, payload.model or settings.model)
        return await get_settings()

    @app.get("/api/v1/experiments")
    def experiments() -> list[dict]:
        return store.experiments()

    @app.post("/api/v1/experiments", status_code=202)
    async def create_experiment(payload: ExperimentCreate, request: Request) -> dict:
        if payload.mode == "live" and any(
            store.item("agent", agent_id)["kind"] == "http" for agent_id in payload.agent_ids
        ):
            raise ValueError(
                "HTTP adapters receive controlled evidence only; live search coverage is unsupported."
            )
        if payload.mode == "live" and not settings.tavily_key:
            raise HTTPException(503, "Tavily is not configured for live research.")
        if payload.engine == "bifrost":
            async with httpx.AsyncClient(
                timeout=3, trust_env=False, follow_redirects=False
            ) as client:
                try:
                    await bounded_json(client, "GET", settings.bifrost_url + "/health")
                except InfrastructureError as exc:
                    raise HTTPException(
                        503,
                        "Bifrost is unavailable. Start the local gateway before a real-model experiment.",
                    ) from exc
        key = request.headers.get("idempotency-key")
        if key and (len(key) > 100 or not key.isascii()):
            raise HTTPException(422, "Idempotency-Key must be ASCII and at most 100 characters.")
        return store.create_experiment(payload, key)

    @app.get("/api/v1/experiments/{experiment_id}")
    def experiment(experiment_id: str) -> dict:
        return store.experiment(experiment_id)

    @app.post("/api/v1/experiments/{experiment_id}/cancel")
    def cancel(experiment_id: str) -> dict:
        return store.cancel(experiment_id)

    @app.get("/api/v1/experiments/{experiment_id}/events")
    async def events(experiment_id: str, request: Request, cursor: int = 0):
        store.experiment(experiment_id)
        if cursor < 0:
            raise HTTPException(422, "Cursor must be nonnegative.")
        try:
            after = max(cursor, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "Last-Event-ID must be an integer.") from None

        async def stream():
            nonlocal after
            while not await request.is_disconnected():
                values = store.experiment_events(experiment_id, after)
                for event in values:
                    after = event["cursor"]
                    yield f"id: {after}\nevent: trace\ndata: {json.dumps(event)}\n\n"
                if (
                    store.experiment(experiment_id, detail=False)["state"]
                    in {"completed", "cancelled", "failed", "partial"}
                    and not values
                ):
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.8)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/runs/{run_id}")
    def run(run_id: str) -> dict:
        return store.run(run_id)

    @app.get("/api/v1/runs/{run_id}/trace")
    def trace(run_id: str) -> list[dict]:
        return store.run(run_id)["events"]

    @app.get("/api/v1/baselines")
    def baselines() -> list[dict]:
        return store.baselines()

    @app.post("/api/v1/baselines", status_code=201)
    def baseline(payload: BaselineCreate) -> dict:
        return store.add_baseline(payload.experiment_id, payload.name)

    @app.post("/api/v1/comparisons")
    def comparison(payload: ComparisonCreate) -> dict:
        return compare(
            store.experiment(payload.baseline_id),
            store.experiment(payload.candidate_id),
            allow_agent_changes=payload.allow_agent_changes,
        )

    @app.get("/api/v1/experiments/{experiment_id}/report")
    def report(experiment_id: str, format: str = "json") -> Response:
        experiment = store.experiment(experiment_id)
        if format == "json":
            full = {**experiment, "runs": [store.run(item["id"]) for item in experiment["runs"]]}
            return Response(
                json.dumps(redact(full, settings.secrets), indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="rilo-{experiment_id}.json"'
                },
            )
        if format != "csv":
            raise HTTPException(422, "Report format must be json or csv.")
        handle = io.StringIO(newline="")
        columns = [
            "id",
            "agent_name",
            "task_name",
            "scenario_name",
            "scenario_activated",
            "repetition",
            "outcome",
            "assessment_status",
            "duration_ms",
            "tool_calls",
            "model_calls",
            "steps",
            "observation_coverage",
            "input_tokens",
            "output_tokens",
            "api_cost_usd",
            "tokens_provenance",
            "cost_provenance",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for item in experiment["runs"]:
            row = {
                key: "'" + value
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                else value
                for key, value in item.items()
            }
            writer.writerow(row)
        return Response(
            handle.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="rilo-{experiment_id}.csv"'},
        )

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API route not found.")
        directory = (settings.root / "frontend" / "dist").resolve()
        candidate = (directory / path).resolve()
        if not candidate.is_relative_to(directory):
            raise HTTPException(404, "File not found.")
        if candidate.is_file():
            return FileResponse(candidate)
        if (directory / "index.html").is_file():
            return FileResponse(directory / "index.html")
        return JSONResponse(
            {
                "app": "Rilo",
                "detail": "API is running. Start the frontend on port 5187 or build frontend/dist.",
            }
        )

    return app


app = create_app()

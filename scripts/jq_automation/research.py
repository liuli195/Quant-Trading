from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


RESEARCH_URL = "https://www.joinquant.com/research"
EXTRACTION_METHOD = "joinquant_research_get_backtest"


class ResearchFetchError(RuntimeError):
    """Raised when JoinQuant research data cannot be fetched."""


@dataclass(frozen=True)
class ResearchFetchOptions:
    backtest_id: str
    strategy: str = ""
    strategy_name: str = ""
    start_date: str = ""
    end_date: str = ""
    capital: int | float | None = None
    frequency: str = ""
    py_version: str = ""
    export_path: str = ""
    audit_token: str = ""
    audit_path: str = ""

    @classmethod
    def from_mapping(cls, options: dict[str, Any]) -> "ResearchFetchOptions":
        backtest_id = str(options.get("backtestId") or options.get("backtest_id") or "")
        strategy = str(options.get("strategy") or "")
        export_path = str(options.get("research_export_path") or "")
        if not export_path and backtest_id:
            safe_id = "".join(ch for ch in backtest_id if ch.isalnum() or ch in "_-") or "unknown"
            export_path = f"jq_auto_exports/research_backtest_{safe_id}.json"
        audit_token = str(options.get("auditToken") or options.get("audit_token") or "")
        audit_path = str(options.get("auditPath") or options.get("audit_path") or "")
        if audit_token and not audit_path:
            audit_path = f"jq_auto_audit/{audit_token}.jsonl"
        return cls(
            backtest_id=backtest_id,
            strategy=strategy,
            strategy_name=str(options.get("strategyName") or options.get("strategy_name") or strategy),
            start_date=str(options.get("startDate") or options.get("start_date_effective") or ""),
            end_date=str(options.get("endDate") or options.get("end_date_effective") or ""),
            capital=options.get("capital"),
            frequency=str(options.get("frequency") or ""),
            py_version=str(options.get("pyVersion") or options.get("py_version") or ""),
            export_path=export_path,
            audit_token=audit_token,
            audit_path=audit_path,
        )


class ResearchFileClient:
    """Read files from the JoinQuant research file area via browser-side APIs."""

    def __init__(self, page: Any) -> None:
        self.page = page

    async def read_text(self, path: str) -> str:
        result = await self.page.evaluate(_READ_RESEARCH_FILE_JS, {"path": path})
        if result.get("ok"):
            return str(result.get("content") or "")
        attempts = result.get("attempts") or []
        raise ResearchFetchError(
            "Could not read JoinQuant research file "
            f"{path!r}; attempted APIs: {', '.join(attempts) or 'none'}; "
            f"error={result.get('error') or 'unknown'}"
        )


class ResearchBacktestFetcher:
    """Fetch a completed backtest through the JoinQuant research environment."""

    def __init__(self, browser: Any) -> None:
        self.browser = browser

    async def fetch(
        self,
        backtest_id: str,
        options: dict[str, Any],
        *,
        supplemental_detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fetch_options = ResearchFetchOptions.from_mapping({**options, "backtestId": backtest_id})
        if not fetch_options.backtest_id:
            raise ResearchFetchError("backtest_id is required for research fetching")
        if not fetch_options.export_path:
            raise ResearchFetchError("research export path could not be constructed")

        page = self.browser._require_page()
        await page.goto(RESEARCH_URL, wait_until="domcontentloaded")
        if hasattr(self.browser, "_ensure_not_login_page"):
            await self.browser._ensure_not_login_page()
        research_context = await _research_context(page)

        script = build_research_export_script(fetch_options)
        exec_result = await research_context.evaluate(_EXECUTE_RESEARCH_SCRIPT_JS, {"code": script})
        if not exec_result.get("ok"):
            details = [
                str(exec_result.get("error") or "unknown error"),
                str(exec_result.get("stderr") or "")[-2000:],
                str(exec_result.get("stdout") or "")[-1000:],
            ]
            message = "\n".join(part for part in details if part)
            raise ResearchFetchError(
                "JoinQuant research script execution failed: "
                f"{message or exec_result}"
            )

        file_client = ResearchFileClient(research_context)
        raw_text = await file_client.read_text(fetch_options.export_path)
        audit_log_text = ""
        audit_log_error = ""
        if fetch_options.audit_path:
            try:
                audit_log_text = await file_client.read_text(fetch_options.audit_path)
            except Exception as exc:
                audit_log_error = str(exc)
        bundle = normalize_research_bundle(
            json.loads(raw_text),
            fetch_options=fetch_options,
            supplemental_detail=supplemental_detail or {},
            execution_meta=exec_result,
            audit_log_text=audit_log_text,
            audit_log_error=audit_log_error,
        )
        return bundle


def normalize_research_bundle(
    raw: dict[str, Any],
    *,
    fetch_options: ResearchFetchOptions | None = None,
    supplemental_detail: dict[str, Any] | None = None,
    execution_meta: dict[str, Any] | None = None,
    audit_log_text: str = "",
    audit_log_error: str = "",
) -> dict[str, Any]:
    """Normalize research output to schema v3."""
    options = fetch_options or ResearchFetchOptions.from_mapping(raw.get("metadata") or {})
    meta = dict(raw.get("metadata") or {})
    meta.update(
        {
            "schema_version": 3,
            "strategy": meta.get("strategy") or options.strategy,
            "strategy_name": meta.get("strategy_name") or options.strategy_name,
            "backtest_id": meta.get("backtest_id") or options.backtest_id,
            "start_date_effective": meta.get("start_date_effective") or options.start_date,
            "end_date_effective": meta.get("end_date_effective") or options.end_date,
            "capital": meta.get("capital", options.capital),
            "frequency": meta.get("frequency") or options.frequency,
            "py_version": meta.get("py_version") or options.py_version,
            "generated_at": meta.get("generated_at") or datetime.now().isoformat(timespec="seconds"),
            "extraction_method": EXTRACTION_METHOD,
            "primary_extraction_method": EXTRACTION_METHOD,
            "research_export_path": meta.get("research_export_path") or options.export_path,
            "research_downloaded": True,
            "detail_api_used": bool(supplemental_detail),
            "audit_token": meta.get("audit_token") or options.audit_token,
            "audit_path": meta.get("audit_path") or options.audit_path,
        }
    )

    supplement = dict(supplemental_detail or raw.get("supplemental_detail") or {})
    if execution_meta:
        supplement["research_execution"] = {
            "api_base": execution_meta.get("apiBase"),
            "kernel_id": execution_meta.get("kernelId"),
            "stdout_tail": execution_meta.get("stdout", "")[-2000:],
        }
    source_errors = {
        key: value.get("__error__")
        for key in ("results", "positions", "orders", "records", "risk", "period_risks", "balances")
        for value in [raw.get(key)]
        if isinstance(value, dict) and value.get("__error__")
    }

    return {
        "metadata": meta,
        "results": _ensure_list(raw.get("results")),
        "positions": _ensure_list(raw.get("positions")),
        "orders": _ensure_list(raw.get("orders")),
        "records": _ensure_list(raw.get("records")),
        "risk": _ensure_dict(raw.get("risk")),
        "period_risks": raw.get("period_risks") or {},
        "balances": _ensure_list(raw.get("balances")),
        "supplemental_detail": supplement,
        "counts": {
            "results": len(_ensure_list(raw.get("results"))),
            "positions": len(_ensure_list(raw.get("positions"))),
            "orders": len(_ensure_list(raw.get("orders"))),
            "records": len(_ensure_list(raw.get("records"))),
            "balances": len(_ensure_list(raw.get("balances"))),
            "period_risk_tabs": len(_ensure_dict(raw.get("period_risks"))),
            "audit_log_lines": len([line for line in str(audit_log_text or "").splitlines() if line.strip()]),
        },
        "partial": {
            "results": "results" in source_errors,
            "positions": "positions" in source_errors,
            "orders": "orders" in source_errors,
            "records": "records" in source_errors,
            "risk": "risk" in source_errors,
            "period_risks": "period_risks" in source_errors,
            "balances": "balances" in source_errors,
            "logs": bool(supplement.get("logs_partial")),
            "audit_log": bool(audit_log_error or not audit_log_text),
        },
        "source_errors": source_errors,
        "audit_log_text": str(audit_log_text or ""),
        "audit_log_error": str(audit_log_error or ""),
    }


def build_research_export_script(options: ResearchFetchOptions) -> str:
    """Build the Python script executed inside JoinQuant research."""
    metadata = {
        "schema_version": 3,
        "strategy": options.strategy,
        "strategy_name": options.strategy_name,
        "backtest_id": options.backtest_id,
        "start_date_effective": options.start_date,
        "end_date_effective": options.end_date,
        "capital": options.capital,
        "frequency": options.frequency,
        "py_version": options.py_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "extraction_method": EXTRACTION_METHOD,
        "primary_extraction_method": EXTRACTION_METHOD,
        "research_export_path": options.export_path,
        "research_downloaded": False,
        "detail_api_used": False,
        "audit_token": options.audit_token,
        "audit_path": options.audit_path,
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False)
    return f"""
import datetime
import decimal
import json
import math
import os

try:
    import numpy as _np
except Exception:
    _np = None
try:
    import pandas as _pd
except Exception:
    _pd = None


def _to_jsonable(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if _np is not None:
        try:
            if isinstance(value, _np.generic):
                return _to_jsonable(value.item())
        except Exception:
            pass
    if _pd is not None:
        try:
            if isinstance(value, _pd.DataFrame):
                frame = value.reset_index()
                return [_to_jsonable(row) for row in frame.to_dict(orient="records")]
            if isinstance(value, _pd.Series):
                series = value.reset_index()
                return [_to_jsonable(row) for row in series.to_dict(orient="records")]
            if isinstance(value, _pd.Timestamp):
                return value.isoformat()
        except Exception:
            pass
    if isinstance(value, dict):
        return {{str(k): _to_jsonable(v) for k, v in value.items()}}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return str(value)


def _safe_call(name, func):
    try:
        return _to_jsonable(func())
    except Exception as exc:
        return {{"__error__": str(exc), "__source__": name}}


_backtest_id = {json.dumps(options.backtest_id, ensure_ascii=False)}
_export_path = {json.dumps(options.export_path, ensure_ascii=False)}
_metadata = json.loads({json.dumps(metadata_json, ensure_ascii=False)})

gt = get_backtest(_backtest_id)
payload = {{
    "metadata": _metadata,
    "results": _safe_call("get_results", gt.get_results),
    "positions": _safe_call("get_positions", gt.get_positions),
    "orders": _safe_call("get_orders", gt.get_orders),
    "records": _safe_call("get_records", gt.get_records),
    "risk": _safe_call("get_risk", gt.get_risk),
    "period_risks": _safe_call("get_period_risks", gt.get_period_risks),
    "balances": _safe_call("get_balances", gt.get_balances),
}}
_export_dir = os.path.dirname(_export_path)
if _export_dir:
    _home_dir = os.path.expanduser("~") or "/home/jquser"
    if _home_dir == "/":
        _home_dir = "/home/jquser"
    os.makedirs(os.path.join(_home_dir, _export_dir), exist_ok=True)
write_file(_export_path, json.dumps(payload, ensure_ascii=False), append=False)
print("jq-auto research export written: " + _export_path)
""".strip()


def json_default(value: Any) -> Any:
    """JSON serializer used by tests and local schema helpers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


async def _research_context(page: Any) -> Any:
    """Return the real Jupyter frame behind JoinQuant's research shell page."""
    if "/user/" in str(getattr(page, "url", "")):
        return page

    try:
        await page.wait_for_selector("iframe#research, iframe[name='research']", timeout=30000)
    except Exception as exc:
        raise ResearchFetchError("JoinQuant research iframe was not found") from exc

    last_url = ""
    for _ in range(60):
        frame = page.frame(name="research")
        if frame is not None:
            last_url = str(getattr(frame, "url", "") or "")
            if "/user/" in last_url:
                try:
                    await frame.evaluate("document.readyState")
                    return frame
                except Exception:
                    pass
        await page.wait_for_timeout(500)
    raise ResearchFetchError(f"JoinQuant research iframe did not finish loading; last_url={last_url or 'unknown'}")


_READ_RESEARCH_FILE_JS = r"""
async ({ path }) => {
  const attempts = [];
  const encPath = String(path || "").split("/").map(encodeURIComponent).join("/");

  function normalizeBase(base) {
    if (!base) return "/";
    if (!base.startsWith("/")) base = "/" + base;
    if (!base.endsWith("/")) base += "/";
    return base;
  }

  function addHubUserCandidates(bases, rawPath) {
    const path = String(rawPath || "");
    const match = path.match(/^\/hub\/user\/([^\/?#]+)/);
    if (!match) return;
    bases.add(normalizeBase(`/user/${match[1]}/`));
    bases.add(normalizeBase(path.replace(/^\/hub\/user\//, "/user/").replace(/\/$/, "")));
  }

  function discoverBases() {
    const bases = new Set(["/"]);
    try {
      const cfgEl = document.getElementById("jupyter-config-data");
      if (cfgEl && cfgEl.textContent) {
        const cfg = JSON.parse(cfgEl.textContent);
        bases.add(normalizeBase(cfg.baseUrl || cfg.base_url || cfg.base_url_path || ""));
      }
    } catch (_) {}
    try {
      const bodyBase = document.body && document.body.getAttribute("data-base-url");
      if (bodyBase) bases.add(normalizeBase(bodyBase));
    } catch (_) {}
    try {
      if (window.PageConfig && typeof window.PageConfig.getOption === "function") {
        const pageBase = window.PageConfig.getOption("baseUrl");
        if (pageBase) bases.add(normalizeBase(pageBase));
      }
    } catch (_) {}
    try {
      const serverSettings = window.jupyterapp
        && window.jupyterapp.serviceManager
        && window.jupyterapp.serviceManager.serverSettings;
      if (serverSettings && serverSettings.baseUrl) {
        bases.add(normalizeBase(serverSettings.baseUrl));
      }
    } catch (_) {}
    const path = location.pathname || "/";
    addHubUserCandidates(bases, path);
    const parts = path.split("/");
    const markers = ["tree", "lab", "notebooks", "files", "edit"];
    for (const marker of markers) {
      const idx = parts.indexOf(marker);
      if (idx > 0) bases.add(normalizeBase(parts.slice(0, idx).join("/")));
    }
    bases.add(normalizeBase(path.replace(/\/$/, "")));
    return [...bases].sort((left, right) => basePriority(left) - basePriority(right));
  }

  function basePriority(base) {
    if (base.includes("/user/") && !base.includes("/hub/user/")) return 0;
    if (base.includes("/hub/user/")) return 1;
    return 2;
  }

  for (const base of discoverBases()) {
    const urls = [
      `${base}api/contents/${encPath}?content=1&type=file`,
      `${base}files/${encPath}`,
    ];
    for (const url of urls) {
      attempts.push(url);
      try {
        const response = await fetch(url, { credentials: "include" });
        if (!response.ok) continue;
        const ctype = response.headers.get("content-type") || "";
        if (ctype.includes("application/json") && url.includes("/api/contents/")) {
          const data = await response.json();
          if (typeof data.content === "string") {
            return { ok: true, content: data.content, url, attempts };
          }
        } else {
          const text = await response.text();
          if (ctype.includes("text/html") && /^\s*<!doctype html/i.test(text)) {
            continue;
          }
          return { ok: true, content: text, url, attempts };
        }
      } catch (error) {
        attempts.push(`${url} -> ${error && error.message ? error.message : String(error)}`);
      }
    }
  }
  return { ok: false, attempts, error: "no readable research file endpoint found" };
}
"""


_EXECUTE_RESEARCH_SCRIPT_JS = r"""
async ({ code }) => {
  const log = [];
  const sessionId = (
    (crypto && crypto.randomUUID && crypto.randomUUID())
    || `jq-auto-${Date.now()}-${Math.random()}`
  );

  function xsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function normalizeBase(base) {
    if (!base) return "/";
    if (!base.startsWith("/")) base = "/" + base;
    if (!base.endsWith("/")) base += "/";
    return base;
  }

  function addHubUserCandidates(bases, rawPath) {
    const path = String(rawPath || "");
    const match = path.match(/^\/hub\/user\/([^\/?#]+)/);
    if (!match) return;
    bases.add(normalizeBase(`/user/${match[1]}/`));
    bases.add(normalizeBase(path.replace(/^\/hub\/user\//, "/user/").replace(/\/$/, "")));
  }

  function discoverBases() {
    const bases = new Set(["/"]);
    try {
      const cfgEl = document.getElementById("jupyter-config-data");
      if (cfgEl && cfgEl.textContent) {
        const cfg = JSON.parse(cfgEl.textContent);
        bases.add(normalizeBase(cfg.baseUrl || cfg.base_url || cfg.base_url_path || ""));
      }
    } catch (_) {}
    try {
      const bodyBase = document.body && document.body.getAttribute("data-base-url");
      if (bodyBase) bases.add(normalizeBase(bodyBase));
    } catch (_) {}
    try {
      if (window.PageConfig && typeof window.PageConfig.getOption === "function") {
        const pageBase = window.PageConfig.getOption("baseUrl");
        if (pageBase) bases.add(normalizeBase(pageBase));
      }
    } catch (_) {}
    try {
      const serverSettings = window.jupyterapp
        && window.jupyterapp.serviceManager
        && window.jupyterapp.serviceManager.serverSettings;
      if (serverSettings && serverSettings.baseUrl) {
        bases.add(normalizeBase(serverSettings.baseUrl));
      }
    } catch (_) {}
    const path = location.pathname || "/";
    addHubUserCandidates(bases, path);
    const parts = path.split("/");
    const markers = ["tree", "lab", "notebooks", "files", "edit"];
    for (const marker of markers) {
      const idx = parts.indexOf(marker);
      if (idx > 0) bases.add(normalizeBase(parts.slice(0, idx).join("/")));
    }
    bases.add(normalizeBase(path.replace(/\/$/, "")));
    return [...bases].sort((left, right) => basePriority(left) - basePriority(right));
  }

  function basePriority(base) {
    if (base.includes("/user/") && !base.includes("/hub/user/")) return 0;
    if (base.includes("/hub/user/")) return 1;
    return 2;
  }

  async function apiFetch(base, endpoint, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      options.headers || {}
    );
    const xsrf = xsrfToken();
    if (xsrf) headers["X-XSRFToken"] = xsrf;
    const response = await fetch(`${base}api/${endpoint}`, {
      credentials: "include",
      method: options.method || "GET",
      headers,
      body: options.body,
    });
    if (!response.ok) throw new Error(`${response.status} ${base}api/${endpoint}`);
    return response.status === 204 ? null : response.json();
  }

  async function findApiBases() {
    const found = [];
    const errors = [];
    for (const base of discoverBases()) {
      try {
        const specs = await apiFetch(base, "kernelspecs");
        if (specs && specs.kernelspecs) {
          found.push(base);
          continue;
        }
        throw new Error(`not a Jupyter kernelspecs response: ${JSON.stringify(specs).slice(0, 200)}`);
      } catch (error) {
        errors.push(`${base}: ${error.message}`);
      }
    }
    if (found.length) return found;
    throw new Error(`No Jupyter API base found. ${errors.join("; ")}`);
  }

  function wsUrlFor(base, kernelId) {
    const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${location.host}${base}api/kernels/${kernelId}/channels?session_id=${encodeURIComponent(sessionId)}`;
  }

  function makeMessage(msgType, content) {
    return {
      header: {
        msg_id: `jq-auto-${Date.now()}-${Math.random()}`,
        username: "jq-auto",
        session: sessionId,
        date: new Date().toISOString(),
        msg_type: msgType,
        version: "5.3",
      },
      parent_header: {},
      metadata: {},
      content,
      channel: "shell",
      buffers: [],
    };
  }

  async function executeOnKernel(base, kernelId) {
    return await new Promise((resolve, reject) => {
      const ws = new WebSocket(wsUrlFor(base, kernelId));
      let stdout = "";
      let stderr = "";
      let executeReply = null;
      let idleSeen = false;
      const timeout = setTimeout(() => {
        try { ws.close(); } catch (_) {}
        reject(new Error("Timed out waiting for research kernel execution"));
      }, 240000);

      ws.onopen = () => {
        ws.send(JSON.stringify(makeMessage("execute_request", {
          code,
          silent: false,
          store_history: false,
          user_expressions: {},
          allow_stdin: false,
          stop_on_error: true,
        })));
      };
      ws.onerror = () => {
        clearTimeout(timeout);
        reject(new Error("Research kernel websocket error"));
      };
      ws.onmessage = (event) => {
        let msg;
        try { msg = JSON.parse(event.data); } catch (_) { return; }
        const msgType = msg && msg.header && msg.header.msg_type;
        const content = msg.content || {};
        if (msgType === "stream") {
          if (content.name === "stderr") stderr += content.text || "";
          else stdout += content.text || "";
        }
        if (msgType === "error") {
          stderr += `${content.ename || "Error"}: ${content.evalue || ""}\n`;
          if (Array.isArray(content.traceback)) stderr += content.traceback.join("\n");
        }
        if (msg.channel === "shell" && msgType === "execute_reply") {
          executeReply = content;
        }
        if (msgType === "status" && content.execution_state === "idle") {
          idleSeen = true;
        }
        if (executeReply && idleSeen) {
          clearTimeout(timeout);
          try { ws.close(); } catch (_) {}
          resolve({ executeReply, stdout, stderr });
        }
      };
    });
  }

  let kernelId = "";
  try {
    const apiBases = await findApiBases();
    let apiBase = "";
    let kernel = null;
    for (const candidate of apiBases) {
      try {
        log.push(`apiBaseCandidate=${candidate}`);
        kernel = await apiFetch(candidate, "kernels", {
          method: "POST",
          body: JSON.stringify({ name: "python3" }),
        });
        apiBase = candidate;
        break;
      } catch (error) {
        log.push(`kernelCreateFailed ${candidate}: ${error.message}`);
      }
    }
    if (!kernel || !apiBase) {
      throw new Error(`No Jupyter API base accepted kernel creation. ${log.join("; ")}`);
    }
    log.push(`apiBase=${apiBase}`);
    kernelId = kernel.id;
    if (!kernelId) {
      throw new Error(`Jupyter kernel did not return an id: ${JSON.stringify(kernel).slice(0, 200)}`);
    }
    const result = await executeOnKernel(apiBase, kernelId);
    try {
      await apiFetch(apiBase, `kernels/${kernelId}`, { method: "DELETE" });
    } catch (_) {}
    const status = result.executeReply && result.executeReply.status;
    if (status !== "ok") {
      return {
        ok: false,
        apiBase,
        kernelId,
        stdout: result.stdout,
        stderr: result.stderr,
        error: `execute_reply status=${status || "unknown"}`,
        log,
      };
    }
    return { ok: true, apiBase, kernelId, stdout: result.stdout, stderr: result.stderr, log };
  } catch (error) {
    return { ok: false, kernelId, error: error && error.message ? error.message : String(error), log };
  }
}
"""

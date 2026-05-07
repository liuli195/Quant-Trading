from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from .paths import detail_url_for, extract_backtest_id
from .snippets import read_snippet

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    PlaywrightTimeoutError = TimeoutError
    async_playwright = None


LIST_URL = "https://www.joinquant.com/algorithm/index/list"
EDIT_URL_MARKER = "/algorithm/index/edit"
DETAIL_URL_MARKER = "/algorithm/backtest/detail"
COMPILE_BUTTON_SELECTORS = [
    "#validate-button",
    "#compile-button",
    "#build-button",
    "#run-code",
    "#daily-run-button",
    "text=编译运行",
    "text=编译",
]
logger = logging.getLogger(__name__)


class AutomationError(RuntimeError):
    """Raised when browser automation cannot continue safely."""


class CompileFailed(AutomationError):
    """Raised when JoinQuant reports a compile error."""


class JoinQuantBrowser:
    def __init__(
        self,
        *,
        user_data_dir: str | Path,
        headless: bool = False,
        slow_mo: int = 0,
        snippet_reader: Callable[[str], str] = read_snippet,
    ) -> None:
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self.slow_mo = slow_mo
        self.snippet_reader = snippet_reader
        self._playwright = None
        self.context = None
        self.page = None

    async def __aenter__(self) -> "JoinQuantBrowser":
        if async_playwright is None:
            raise AutomationError("Playwright is not installed. Run: pip install -r requirements.txt")
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        storage_state = self._storage_state_path
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 950},
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        # Restore cookies from persisted storage state
        if storage_state.is_file():
            import json
            state = json.loads(storage_state.read_text(encoding="utf-8"))
            if state.get("cookies"):
                await self.context.add_cookies(state["cookies"])
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.context:
            # Persist cookies to storage state file before closing
            try:
                cookies = await self.context.cookies()
                state = {"cookies": cookies}
                self._storage_state_path.write_text(
                    __import__("json").dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            await self.context.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def _storage_state_path(self) -> Path:
        return self.user_data_dir / "storage_state.json"

    async def open_strategy_editor(self, strategy_name: str, edit_url: str | None = None) -> None:
        page = self._require_page()
        if edit_url:
            await page.goto(edit_url, wait_until="domcontentloaded")
            await self._assert_editor_page()
            await self._dismiss_modals()
            return

        await page.goto(LIST_URL, wait_until="domcontentloaded")
        await self._ensure_not_login_page()
        found = await page.evaluate(
            """
            (strategyName) => {
              const links = [...document.querySelectorAll('a[href*="/algorithm/index/edit"]')];
              const rows = links.map((link) => {
                const row = link.closest('tr, li, .strategy-item, .layui-table-view, .table-row, div') || link;
                const text = (row.innerText || link.innerText || '').trim();
                return { href: link.href, text };
              });
              if (strategyName) {
                return rows.find((row) => row.text.includes(strategyName)) || null;
              }
              return rows[0] || null;
            }
            """,
            strategy_name,
        )
        if not found:
            raise AutomationError(
                "Could not find a JoinQuant strategy editor link. "
                "Pass --edit-url after creating/opening the strategy manually."
            )
        await page.goto(found["href"], wait_until="domcontentloaded")
        await self._assert_editor_page()
        await self._dismiss_modals()

    async def write_strategy_code(self, code: str) -> dict[str, Any]:
        result = await self._eval_snippet_function(
            "editor.js",
            "return writeStrategyCodeToAce(payload.code);",
            {"code": code},
        )
        if not result or not result.get("ok") or result.get("length", 0) <= 0:
            raise AutomationError(f"Ace editor write failed: {result}")
        return result

    async def click_compile(self) -> None:
        page = self._require_page()
        for selector in COMPILE_BUTTON_SELECTORS:
            locator = page.locator(selector).first
            try:
                count = await locator.count()
                visible = count and await locator.is_visible()
                if visible:
                    await locator.click()
                    return
            except Exception:
                continue
        raise AutomationError("Could not find the JoinQuant compile button")

    async def wait_compile_complete(self, timeout_ms: int = 120_000, poll_ms: int = 500) -> dict[str, Any]:
        return await wait_for_compile_completion(
            self._require_page(),
            lambda name: self.snippet_reader(name),
            timeout_ms=timeout_ms,
            poll_ms=poll_ms,
        )

    async def apply_backtest_params(self, start_date: str, end_date: str, capital: int | float, frequency: str = "", py_version: str = "") -> dict[str, str]:
        return await self._eval_snippet_function(
            "backtest.js",
            "return applyBacktestParams(payload.start_date, payload.end_date, payload.capital, payload.frequency, payload.py_version);",
            {"start_date": start_date, "end_date": end_date, "capital": capital, "frequency": frequency, "py_version": py_version},
        )

    async def start_full_backtest(self) -> None:
        await self._eval_snippet_function("backtest.js", "return clickFullBacktestButton();", {})
        page = self._require_page()
        try:
            await page.wait_for_url(f"**{DETAIL_URL_MARKER}**", timeout=60_000)
        except PlaywrightTimeoutError as exc:
            raise AutomationError("Formal backtest did not navigate to the detail page") from exc

    async def wait_backtest_complete(self, timeout_ms: int = 180_000) -> None:
        page = self._require_page()
        await page.get_by_text("回测完成").wait_for(timeout=timeout_ms)

    async def open_backtest_detail(self, target: str) -> None:
        page = self._require_page()
        await page.goto(detail_url_for(target), wait_until="domcontentloaded")
        await self._ensure_not_login_page()

    async def fetch_api_bundle(self, options: dict[str, Any]) -> dict[str, Any]:
        await self._install_extract_contract()
        page = self._require_page()
        return await page.evaluate("(options) => window.fetchExistingBacktestBundle(options)", options)

    async def collect_dom_tabs(self) -> dict[str, str]:
        await self._install_extract_contract()
        page = self._require_page()
        return await page.evaluate(
            """
            async () => {
              await window.collectBacktestTabTexts();
              return window.__bt || {};
            }
            """
        )

    def current_backtest_id(self) -> str:
        page = self._require_page()
        return extract_backtest_id(page.url)

    async def read_daily_runtime_usage(self) -> dict[str, Any]:
        """Read today's actual used time and free limit from the editor page."""
        page = self._require_page()
        popover_text = await page.evaluate("""() => {
            const el = document.querySelector('.run-time-popover-html');
            return el ? el.innerText : '';
        }""")
        import re
        used_match = re.search(r"今日已运行时长[：:]\s*([\d.]+)\s*分钟", popover_text)
        free_match = re.search(r"免费可用时长[：:]\s*([\d.]+)\s*分钟", popover_text)
        return {
            "used_minutes_today": float(used_match.group(1)) if used_match else None,
            "free_limit_minutes": float(free_match.group(1)) if free_match else None,
        }

    async def fetch_runtime_seconds(self) -> float | None:
        """Fetch the actual compute seconds for the current backtest from runTimeInfo."""
        page = self._require_page()
        try:
            result = await page.evaluate("""async () => {
                const backtestId = window.backtestId
                    || new URLSearchParams(location.search).get('backtestId');
                if (!backtestId) return null;
                const resp = await fetch(
                    '/algorithm/backtest/runTimeInfo?backtestId=' + backtestId + '&ajax=1',
                    { credentials: 'include',
                      headers: { 'X-Requested-With': 'XMLHttpRequest' } }
                );
                if (!resp.ok) return null;
                const json = await resp.json();
                return json?.data?.needSeconds ?? null;
            }""")
            if isinstance(result, (int, float)) and result > 0:
                return float(result)
        except Exception:
            pass
        return None

    async def fetch_detail_supplemental(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch detail-page-only fields used to supplement research results."""
        page = self._require_page()
        return await page.evaluate(
            """
            async (options) => {
              const detailBacktestId = options?.backtestId
                || options?.backtest_id
                || new URLSearchParams(location.search).get('backtestId')
                || "";
              const internalBacktestId = window.backtestId
                || document.querySelector("#backtestId")?.value
                || detailBacktestId;
              const apiId = internalBacktestId || detailBacktestId;
              if (!apiId) {
                throw new Error("backtestId not found on detail page");
              }

              async function fetchJson(url) {
                const response = await fetch(url, {
                  credentials: "include",
                  headers: { "X-Requested-With": "XMLHttpRequest" },
                });
                if (!response.ok) throw new Error(`${response.status} ${url}`);
                return response.json();
              }

              async function fetchText(url) {
                const response = await fetch(url, {
                  credentials: "include",
                  headers: { "X-Requested-With": "XMLHttpRequest" },
                });
                if (!response.ok) throw new Error(`${response.status} ${url}`);
                return response.text();
              }

              async function collectLogMeta(endpoint) {
                const pages = [];
                let offset = 0;
                for (let page = 0; page < 20; page += 1) {
                  const query = `/algorithm/backtest/${endpoint}?backtestId=${apiId}&offset=${offset}&ajax=1`;
                  const json = await fetchJson(query);
                  const data = json.data || {};
                  const batch = data.logArr || [];
                  pages.push({
                    page,
                    query,
                    count: batch.length,
                    offset,
                    responseOffset: data.offset ?? null,
                    max: data.max === true,
                  });
                  if (!batch.length || data.max === true) break;
                  offset += batch.length;
                }
                return {
                  count: pages.reduce((sum, item) => sum + item.count, 0),
                  partial: pages.at(-1)?.max === true,
                  pages,
                };
              }

              const result = {
                detail_backtest_id: detailBacktestId,
                internal_backtest_id: internalBacktestId,
                detail_api_used: true,
                detail_api_url: location.href,
                runtime: null,
                source: null,
                profile_text: "",
                logs_partial: null,
                logs_count: null,
                error_logs_partial: null,
                error_logs_count: null,
                errors: {},
              };

              const tasks = [
                ["runtime", () => fetchJson(`/algorithm/backtest/runTimeInfo?backtestId=${apiId}&ajax=1`)],
                ["source", () => fetchJson(`/algorithm/backtest/source?backtestId=${apiId}&ajax=1`)],
                ["profile_text", () => fetchText(`/algorithm/backtest/profile?backtestId=${apiId}&ajax=1`)],
                ["logs", () => collectLogMeta("log")],
                ["error_logs", () => collectLogMeta("error")],
              ];

              for (const [key, fn] of tasks) {
                try {
                  const value = await fn();
                  if (key === "logs") {
                    result.logs_partial = value.partial;
                    result.logs_count = value.count;
                    result.logs_pages = value.pages;
                  } else if (key === "error_logs") {
                    result.error_logs_partial = value.partial;
                    result.error_logs_count = value.count;
                    result.error_logs_pages = value.pages;
                  } else {
                    result[key] = value;
                  }
                } catch (error) {
                  result.errors[key] = error && error.message ? error.message : String(error);
                }
              }
              return result;
            }
            """,
            options or {},
        )

    async def _install_extract_contract(self) -> None:
        page = self._require_page()
        source = self.snippet_reader("extract.js")
        await page.evaluate(
            """
            (source) => {
              if (window.__jqExtractContractLoaded) return true;
              const exports = `
                Object.assign(window, {
                  fetchExistingBacktestBundle,
                  dumpExistingBacktestBundle,
                  fetchAllBacktestData,
                  dumpFetchedBacktestData,
                  collectBacktestTabTexts,
                  dumpCollectedBacktestTabs,
                  extractSummaryMetrics,
                  isProfileReady
                });
                window.__jqExtractContractLoaded = true;
              `;
              new Function(source + exports)();
              return true;
            }
            """,
            source,
        )

    async def _eval_snippet_function(self, snippet_name: str, body: str, payload: dict[str, Any]) -> Any:
        page = self._require_page()
        source = self.snippet_reader(snippet_name)
        return await page.evaluate(
            "(args) => new Function('payload', args.source + '\\n' + args.body)(args.payload)",
            {"source": source, "body": body, "payload": payload},
        )

    async def _assert_editor_page(self) -> None:
        page = self._require_page()
        if EDIT_URL_MARKER not in page.url:
            raise AutomationError(f"Expected JoinQuant editor page, got: {page.url}")
        try:
            await page.wait_for_function(
                """
                () => Boolean(
                  document.getElementById('ide-container')
                  || document.querySelector('.ace_editor')
                  || document.getElementById('code')
                )
                """,
                timeout=15_000,
            )
        except PlaywrightTimeoutError as exc:
            raise AutomationError(f"Expected JoinQuant editor controls on page, got: {page.url}") from exc

    async def _dismiss_modals(self) -> None:
        """Dismiss any Bootstrap modals or onboarding dialogs blocking the editor."""
        page = self._require_page()
        await page.wait_for_timeout(800)
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception as exc:
            logger.debug("Failed to dismiss modal with Escape: %s", exc)
        try:
            close_btn = page.locator(".modal .close, .bootstrap-dialog .close, .bootstrap-dialog-close-button, .modal button:has-text('确定'), .modal button:has-text('关闭'), .modal button:has-text('知道了')").first
            if await close_btn.count() and await close_btn.is_visible():
                await close_btn.click()
                await page.wait_for_timeout(500)
        except Exception as exc:
            logger.debug("Failed to dismiss modal with close button: %s", exc)
        try:
            await page.evaluate("""
                () => {
                    document.querySelectorAll('.modal.in, .modal.show, .bootstrap-dialog, .layui-layer')
                        .forEach(el => { el.style.display = 'none'; el.classList.remove('in', 'show'); });
                    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                }
            """)
            await page.wait_for_timeout(300)
        except Exception as exc:
            logger.debug("Failed to force-hide modal overlays: %s", exc)

    async def _ensure_not_login_page(self) -> None:
        page = self._require_page()
        if "login" not in page.url.lower():
            return
        if self.headless:
            raise AutomationError(
                "JoinQuant login is required. "
                "Run once without --headless to log in interactively, then retry."
            )
        # Non-headless mode: wait for the user to log in
        print("聚宽登录页面已打开，请在浏览器中完成登录...")
        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=300_000,
            )
            print("登录完成，继续自动化流程...")
        except Exception:
            raise AutomationError(
                "Timed out waiting for JoinQuant login. Please log in and retry."
            )

    def _require_page(self):
        if self.page is None:
            raise AutomationError("Browser page is not initialized")
        return self.page


async def wait_for_compile_completion(
    page: Any,
    snippet_reader: Callable[[str], str],
    *,
    timeout_ms: int = 120_000,
    poll_ms: int = 500,
) -> dict[str, Any]:
    source = snippet_reader("compile.js")
    deadline = time.monotonic() + timeout_ms / 1000
    seen_cancel = False
    last_state: dict[str, Any] = {}

    while time.monotonic() < deadline:
        state = await page.evaluate(
            "(source) => new Function(source + '\\nreturn readCompileState();')()",
            source,
        )
        last_state = state or {}
        if last_state.get("hasCancel"):
            seen_cancel = True
        if last_state.get("hasError"):
            errors = await page.evaluate(
                "(source) => new Function(source + '\\nreturn readCompileErrors();')()",
                source,
            )
            raise CompileFailed(errors or _trim_body(last_state))
        if seen_cancel and not last_state.get("hasCancel"):
            return last_state
        await page.wait_for_timeout(poll_ms)

    raise AutomationError(
        "Timed out waiting for JoinQuant compile completion. "
        f"seen_cancel={seen_cancel}, last_state={json.dumps(_trim_body(last_state), ensure_ascii=False)}"
    )


def _trim_body(state: dict[str, Any]) -> dict[str, Any]:
    trimmed = dict(state)
    if "bodyText" in trimmed:
        trimmed["bodyText"] = str(trimmed["bodyText"])[:1000]
    return trimmed

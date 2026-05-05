from __future__ import annotations

import json
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
    "#compile-button",
    "#build-button",
    "#run-code",
    "#daily-run-button",
    "text=编译运行",
    "text=编译",
]


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
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            channel="chrome",
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 950},
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.context:
            await self.context.close()
        if self._playwright:
            await self._playwright.stop()

    async def open_strategy_editor(self, strategy_name: str, edit_url: str | None = None) -> None:
        page = self._require_page()
        if edit_url:
            await page.goto(edit_url, wait_until="domcontentloaded")
            await self._assert_editor_page()
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
            locator = page.locator(selector).first()
            try:
                if await locator.count() and await locator.is_visible(timeout=1200):
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

    async def apply_backtest_params(self, start_date: str, end_date: str, capital: int | float) -> dict[str, str]:
        return await self._eval_snippet_function(
            "backtest.js",
            "return applyBacktestParams(payload.start_date, payload.end_date, payload.capital);",
            {"start_date": start_date, "end_date": end_date, "capital": capital},
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

    async def _ensure_not_login_page(self) -> None:
        page = self._require_page()
        if "login" in page.url.lower():
            raise AutomationError("JoinQuant login is required. Log in in the dedicated Chrome window, then retry.")

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

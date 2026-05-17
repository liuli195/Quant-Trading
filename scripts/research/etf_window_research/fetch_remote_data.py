from __future__ import annotations

from pathlib import Path

from scripts.tools.jq_automation.browser import JoinQuantBrowser
from scripts.tools.jq_automation.research import (
    RESEARCH_URL,
    ResearchFileClient,
    ResearchFetchError,
    _EXECUTE_RESEARCH_SCRIPT_JS,
    _research_context,
)

from .research_export import DEFAULT_EXPORT_PATH, DEFAULT_HISTORY_START, build_joinquant_research_export_script


async def fetch_remote_price_bundle(
    *,
    output: str | Path,
    export_path: str = DEFAULT_EXPORT_PATH,
    history_start: str = DEFAULT_HISTORY_START,
    user_data_dir: str | Path = ".local/chrome-jq",
    headless: bool = False,
    slow_mo: int = 0,
) -> Path:
    script = build_joinquant_research_export_script(
        export_path=export_path,
        history_start=history_start,
    )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with JoinQuantBrowser(
        user_data_dir=user_data_dir,
        headless=headless,
        slow_mo=slow_mo,
    ) as browser:
        page = browser._require_page()
        await page.goto(RESEARCH_URL, wait_until="domcontentloaded")
        await browser._ensure_not_login_page()
        research_context = await _research_context(page)
        exec_result = await research_context.evaluate(_EXECUTE_RESEARCH_SCRIPT_JS, {"code": script})
        if not exec_result.get("ok"):
            details = [
                str(exec_result.get("error") or "unknown error"),
                str(exec_result.get("stderr") or "")[-2000:],
                str(exec_result.get("stdout") or "")[-1000:],
            ]
            raise ResearchFetchError(
                "JoinQuant window-research export failed: "
                + "\n".join(part for part in details if part)
            )
        raw_text = await ResearchFileClient(research_context).read_text(export_path)

    output_path.write_text(raw_text, encoding="utf-8")
    return output_path


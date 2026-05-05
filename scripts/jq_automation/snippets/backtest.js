function setInputValue(id, value, needInputEvent) {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Missing element: #${id}`);
  }

  el.value = String(value);
  el.dispatchEvent(new Event("change", { bubbles: true }));

  if (needInputEvent) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function applyBacktestParams(startDate, endDate, capital) {
  setInputValue("startTime", startDate, false);
  setInputValue("endTime", endDate, false);
  setInputValue("daily_backtest_capital_base_box", capital, true);

  return readEffectiveBacktestParams();
}

function readEffectiveBacktestParams() {
  return {
    start_date: document.getElementById("startTime")?.value || "",
    end_date: document.getElementById("endTime")?.value || "",
    capital: document.getElementById("daily_backtest_capital_base_box")?.value || "",
  };
}

function clickFullBacktestButton() {
  const btn = document.getElementById("full-backtest-button");
  const target = btn?.children?.[0] || btn;

  if (!target) {
    throw new Error("未找到正式回测按钮");
  }

  target.click();
  return true;
}

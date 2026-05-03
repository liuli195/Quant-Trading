async function getTabText(href, containerId) {
  const tab = document.querySelector(`a[href="${href}"]`);
  if (tab) {
    tab.click();
  }

  await new Promise((resolve) => setTimeout(resolve, 600));

  const container = document.getElementById(containerId);
  return container ? container.innerText || "" : "";
}

async function collectBacktestTabTexts() {
  const metricTabs = [
    ["#tab-algorithm_period_return", "tab-algorithm_period_return", "algorithm_period_return"],
    ["#tab-benchmark_period_return", "tab-benchmark_period_return", "benchmark_period_return"],
    ["#tab-alpha", "tab-alpha", "alpha"],
    ["#tab-beta", "tab-beta", "beta"],
    ["#tab-sharpe", "tab-sharpe", "sharpe"],
    ["#tab-sortino", "tab-sortino", "sortino"],
    ["#tab-information", "tab-information", "information"],
    ["#tab-algo_volatility", "tab-algo_volatility", "algo_volatility"],
    ["#tab-benchmark_volatility", "tab-benchmark_volatility", "benchmark_volatility"],
    ["#tab-max_drawdown", "tab-max_drawdown", "max_drawdown"],
  ];

  window.__bt = {};

  window.__bt.transactioninfo = await getTabText("#tab-transactioninfo", "tab-transactioninfo");
  window.__bt.positioninfo = await getTabText("#tab-positioninfo", "tab-positioninfo");
  window.__bt.logs = await getTabText("#tab-logs", "tab-logs");
  window.__bt.profile = await getTabText("#tab-profile", "tab-profile");

  for (const [href, containerId, key] of metricTabs) {
    window.__bt[key] = await getTabText(href, containerId);
  }

  return Object.fromEntries(
    Object.entries(window.__bt).map(([key, value]) => [key, value.length])
  );
}

function dumpCollectedBacktestTabs() {
  return JSON.stringify(window.__bt || {});
}

function extractSummaryMetrics() {
  const container = document.getElementById("tab-summaryinfo");
  if (!container) {
    return {};
  }

  const data = {};
  container.querySelectorAll(".top-level-stat").forEach((block) => {
    const label = block.querySelector(".stat-label")?.innerText?.trim();
    const value = block.querySelector(".stat-value")?.innerText?.trim();
    if (label && value) {
      data[label] = value;
    }
  });

  return data;
}

function isProfileReady() {
  const container = document.getElementById("tab-profile");
  const text = container ? container.innerText || "" : "";
  const rowCount = container ? container.querySelectorAll("tr").length : 0;

  return {
    ready: rowCount > 1 && (text.includes("Total time") || text.includes("总耗时")),
    rowCount,
    textLength: text.length,
  };
}


// ============================================================
// fetchAllBacktestData — 通过内部 API 获取完整回测数据
// ============================================================
// 解决 DOM 提取受虚拟滚动限制的问题。
// 直接调用聚宽内部 XHR 接口，自带分页链式加载，
// 可获取 100% 完整数据。

async function fetchAllBacktestData() {
  const internalId = window.__backtestId;
  if (!internalId) {
    return { error: "window.__backtestId not found — page may not be a backtest detail page" };
  }

  // 通用分页加载器
  async function fetchAllPages(endpoint) {
    const key = endpoint === "transactionInfo" ? "transaction" : "position";
    const allData = [];
    let offset = 0;
    let dateOffset = null;

    for (let i = 0; i < 80; i++) {
      let qs = `backtestId=${internalId}&ajax=1`;
      if (offset > 0) qs += `&offset=${offset}`;
      if (dateOffset) qs += `&dateOffset=${dateOffset}`;

      const resp = await fetch(`/algorithm/backtest/${endpoint}?${qs}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: "undefined&ajax=1",
      });

      const data = await resp.json();
      const items = data?.data?.[key] || [];

      if (items.length === 0) break;

      allData.push(...items);

      const dates = [...new Set(items.map((it) => it.date))].sort();
      offset += items.length;
      dateOffset = dates[dates.length - 1];

      if (data?.data?.max === true) break;
    }

    return allData;
  }

  // 每日收益加载器（result API 使用 offset 分页）
  async function fetchAllResults() {
    const allPages = [];

    for (let offset = 0; offset < 10000; offset += 804) {
      const resp = await fetch(
        `/algorithm/backtest/result?backtestId=${internalId}&offset=${offset}&userRecordOffset=0&ajax=1`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: "undefined&ajax=1",
        }
      );

      const data = await resp.json();
      const result = data?.data?.result;
      if (!result?.benchmark?.time || result.benchmark.time.length === 0) break;

      allPages.push(result);

      if (result.benchmark.time.length < 804) break;
    }

    return allPages;
  }

  const [transactions, positions, results] = await Promise.all([
    fetchAllPages("transactionInfo"),
    fetchAllPages("positionInfo"),
    fetchAllResults(),
  ]);

  return {
    internalId,
    transactions,
    positions,
    results,
    counts: {
      transactions: transactions.length,
      positions: positions.length,
      resultPages: results.length,
    },
  };
}

function dumpFetchedBacktestData() {
  return JSON.stringify(window.__fetchedData || {});
}

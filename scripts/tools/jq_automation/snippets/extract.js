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
  const internalId = window.backtestId;
  if (!internalId) {
    window.__fetchedData = { error: "window.backtestId not found — page may not be a backtest detail page" };
    return window.__fetchedData;
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

  window.__fetchedData = {
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
  return window.__fetchedData;
}

function dumpFetchedBacktestData() {
  return JSON.stringify(window.__fetchedData || {});
}

// One-shot, no-export bundle for an existing JoinQuant backtest detail page.
// Runs entirely in the browser via evaluate_script/DevTools console and only
// calls read-only same-origin JSON endpoints used by the detail page itself.
async function fetchExistingBacktestBundle(options = {}) {
  // 详情页外部 ID（用户可见，来自 URL）
  const detailBacktestId = options.backtestId
    || new URLSearchParams(location.search).get("backtestId")
    || "";
  // 聚宽内部 API ID（可能不同于详情页 ID，但 API 请求必须用它）
  const internalBacktestId = window.backtestId
    || document.querySelector("#backtestId")?.value
    || detailBacktestId;

  const apiId = internalBacktestId || detailBacktestId;
  if (!apiId) {
    throw new Error("backtestId not found. Open a JoinQuant backtest detail page first.");
  }

  const maxPages = options.maxPages || 80;
  const metadata = {
    schema_version: 2,
    strategy: options.strategy || "",
    strategy_name: options.strategyName || options.strategy_name || "",
    backtest_id: detailBacktestId || apiId,
    backtest_url: location.href,
    generated_at: new Date().toISOString(),
    start_date_effective: options.startDate || options.start_date_effective || "",
    end_date_effective: options.endDate || options.end_date_effective || "",
    capital: options.capital || null,
    frequency: options.frequency || "",
    py_version: options.pyVersion || options.py_version || "",
    extraction_method: "joinquant_detail_readonly_api",
    export_used: false,
    internal_backtest_id: internalBacktestId || detailBacktestId,
  };
  if (detailBacktestId && internalBacktestId && detailBacktestId !== internalBacktestId) {
    metadata.id_mismatch = true;
  }

  // 分页抓取所有 result 页
  var resultPages = [];
  var resultRows = [];
  var resultPageMeta = [];
  for (var rp = 0; rp < maxPages; rp++) {
    var rOffset = rp * 804;
    var rJson = await jqFetchJson(
      "/algorithm/backtest/result?backtestId=" + apiId + "&offset=" + rOffset + "&userRecordOffset=0&ajax=1"
    );
    var rData = rJson?.data?.result;
    if (!rData?.benchmark?.time || rData.benchmark.time.length === 0) break;
    resultPages.push(rData);
    resultPageMeta.push({ page: rp, offset: rOffset, count: rData.benchmark.time.length });
    var pageRows = jqBuildResultRowsFromPage(rData);
    for (var ri = 0; ri < pageRows.length; ri++) {
      resultRows.push(pageRows[ri]);
    }
    if (rData.benchmark.time.length < 804) break;
  }

  const [stats, dayResult, risk, runtime, source, profileText] = await Promise.all([
    jqFetchJson("/algorithm/backtest/stats?backtestId=" + apiId + "&ajax=1"),
    jqFetchJson("/algorithm/backtest/dayResult?backtestId=" + apiId + "&offset=0&ajax=1"),
    jqFetchJson("/algorithm/backtest/risk?backtestId=" + apiId + "&ajax=1"),
    jqFetchJson("/algorithm/backtest/runTimeInfo?backtestId=" + apiId + "&ajax=1"),
    jqFetchJson("/algorithm/backtest/source?backtestId=" + apiId + "&ajax=1"),
    jqFetchText("/algorithm/backtest/profile?backtestId=" + apiId + "&ajax=1"),
  ]);

  const [transactions, positions, logs, errorLogs] = await Promise.all([
    jqCollectTransactions(apiId, maxPages),
    jqCollectPositionsByDate(apiId, maxPages, metadata.end_date_effective),
    jqCollectLogs("log", apiId, maxPages),
    jqCollectLogs("error", apiId, maxPages),
  ]);

  var bundle = {
    metadata: metadata,
    stats: stats,
    result_pages: resultPages,
    result_page_meta: resultPageMeta,
    day_result: dayResult,
    risk: risk,
    runtime: runtime,
    source: source,
    profile_text: profileText,
    transactions: transactions,
    positions: positions,
    logs: logs,
    error_logs: errorLogs,
    result_rows: resultRows,
    risk_tabs: jqBuildRiskTabs(risk),
  };

  var resultsPartial = resultPages.length >= maxPages
    && resultPages.length > 0
    && (resultPages[resultPages.length - 1].benchmark?.time?.length || 0) >= 804;

  bundle.counts = {
    transactions: transactions.rows.length,
    positions: positions.rows.length,
    logs: logs.rows.length,
    error_logs: errorLogs.rows.length,
    result_rows: resultRows.length,
    result_pages: resultPages.length,
    risk_rows: Object.values(bundle.risk_tabs).reduce(function(sum, tab) { return sum + tab.rows.length; }, 0),
  };
  bundle.partial = {
    transactions: transactions.partial,
    positions: positions.partial,
    logs: logs.partial,
    results: resultsPartial,
  };

  window.__jqBacktestBundle = bundle;
  return bundle;
}

function dumpExistingBacktestBundle() {
  return JSON.stringify(window.__jqBacktestBundle || {});
}

async function jqFetchJson(url) {
  const response = await fetch(url, {
    credentials: "include",
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

async function jqFetchText(url) {
  const response = await fetch(url, {
    credentials: "include",
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.text();
}

function jqLastDate(rows) {
  if (!rows.length) return null;
  const row = rows[rows.length - 1];
  return row.tradeDate || row.date || null;
}

async function jqCollectTransactions(backtestId, maxPages) {
  const rows = [];
  const pages = [];
  let offset = 0;
  let dateOffset = null;

  for (let page = 0; page < maxPages; page += 1) {
    let query = `/algorithm/backtest/transactionInfo?backtestId=${backtestId}&ajax=1`;
    if (offset > 0) query += `&offset=${offset}`;
    if (dateOffset) query += `&dateOffset=${encodeURIComponent(dateOffset)}`;
    const json = await jqFetchJson(query);
    const data = json.data || {};
    const batch = data.transaction || [];
    rows.push(...batch);
    pages.push({ page, query, count: batch.length, offset, dateOffset, max: data.max === true, firstDate: batch[0]?.date || null, lastDate: jqLastDate(batch) });
    if (!batch.length || data.max === true) break;
    offset += batch.length;
    dateOffset = jqLastDate(batch) || dateOffset;
  }

  return { rows, pages, partial: pages.at(-1)?.max === true };
}

async function jqCollectPositionsByDate(backtestId, maxPages, endDate = "") {
  const rows = [];
  const pages = [];
  const seen = new Set();
  let dateOffset = null;

  for (let page = 0; page < maxPages; page += 1) {
    let query = `/algorithm/backtest/positionInfo?backtestId=${backtestId}&ajax=1`;
    if (dateOffset) query += `&dateOffset=${encodeURIComponent(dateOffset)}`;
    const json = await jqFetchJson(query);
    const data = json.data || {};
    const batch = data.position || [];
    let added = 0;
    for (const row of batch) {
      const key = JSON.stringify([row.date, row.time, row.stock, row.amount, row.value, row.dailyGains, row.positionPersent]);
      if (!seen.has(key)) {
        seen.add(key);
        rows.push(row);
        added += 1;
      }
    }
    const lastDate = jqLastDate(batch);
    pages.push({ page, query, count: batch.length, added, max: data.max === true, firstDate: batch[0]?.date || null, lastDate });
    if (!batch.length || !lastDate) break;
    if (lastDate === dateOffset) break;
    dateOffset = lastDate;
    if (endDate && lastDate >= endDate) break;
  }

  return { rows, pages, partial: false, method: "dateOffset segmented without export" };
}

async function jqCollectLogs(endpoint, backtestId, maxPages) {
  const rows = [];
  const pages = [];
  let offset = 0;

  for (let page = 0; page < maxPages; page += 1) {
    const query = `/algorithm/backtest/${endpoint}?backtestId=${backtestId}&offset=${offset}&ajax=1`;
    const json = await jqFetchJson(query);
    const data = json.data || {};
    const batch = data.logArr || [];
    rows.push(...batch);
    pages.push({ page, query, count: batch.length, offset, responseOffset: data.offset ?? null, max: data.max === true });
    if (!batch.length || data.max === true) break;
    offset += batch.length;
  }

  return { rows, pages, partial: pages.at(-1)?.max === true };
}

function jqDateFromMs(ms) {
  const date = new Date(ms);
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${date.getUTCFullYear()}-${month}-${day}`;
}

function jqBuildResultRows(resultJson) {
  // resultJson 是完整 API 响应（含 data.result 包装），供 fetchAllBacktestData 使用
  const result = resultJson?.data?.result || {};
  return jqBuildResultRowsFromPage(result);
}

function jqBuildResultRowsFromPage(result) {
  // result 是单个 result 页对象（即 data.result 内容）
  const times = result.overallReturn?.time || result.benchmark?.time || [];
  if (!times.length) return [];
  return times.map(function(time, index) {
    return {
      date: jqDateFromMs(time),
      algorithm_return_value: result.overallReturn?.value?.[index] ?? "",
      benchmark_return_value: result.benchmark?.value?.[index] ?? "",
      gains_earn: result.gains?.earn?.value?.[index] ?? "",
      gains_lose: result.gains?.lose?.value?.[index] ?? "",
      orders_buy: result.orders?.buy?.value?.[index] ?? "",
      orders_sell: result.orders?.sell?.value?.[index] ?? "",
    };
  });
}

function jqBuildRiskTabs(riskJson) {
  const risk = riskJson?.data?.risk || {};
  const tabs = {};
  const definitions = [
    ["algorithm_period_return", "策略收益", "algorithmPeriodReturn"],
    ["benchmark_period_return", "基准收益", "benchmarkPeriodReturn"],
    ["alpha", "阿尔法", "alpha"],
    ["beta", "贝塔", "beta"],
    ["sharpe", "夏普比率", "sharp"],
    ["sortino", "索提诺比率", "sortino"],
    ["information", "信息比率", "information"],
    ["algo_volatility", "波动率", "algovolatility"],
    ["benchmark_volatility", "基准波动率", "benchmarkvolatility"],
    ["max_drawdown", "最大回撤", "maxdrawdown"],
  ];
  for (const [name, label, sourceKey] of definitions) {
    tabs[name] = { label, source_key: sourceKey, rows: Array.isArray(risk[sourceKey]) ? risk[sourceKey] : [] };
  }
  return tabs;
}

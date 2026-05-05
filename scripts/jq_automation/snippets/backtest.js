function setInputValue(id, value, needInputEvent) {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error("Missing element: #" + id);
  }

  el.value = String(value);
  el.dispatchEvent(new Event("change", { bubbles: true }));

  if (needInputEvent) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function normalizeFrequency(raw) {
  var v = String(raw || "").trim().toLowerCase();
  if (["每天", "daily", "day", "1d", "d"].indexOf(v) !== -1) return "1d";
  if (["每分钟", "minute", "1m", "m"].indexOf(v) !== -1) return "1m";
  if (["每五分钟", "5m", "5min"].indexOf(v) !== -1) return "5m";
  if (["每十五分钟", "15m", "15min"].indexOf(v) !== -1) return "15m";
  if (["每三十分钟", "30m", "30min"].indexOf(v) !== -1) return "30m";
  if (["每小时", "hourly", "60m", "1h", "h"].indexOf(v) !== -1) return "60m";
  return raw ? v : "";
}

function normalizePyVersion(raw) {
  var v = String(raw || "").trim().toLowerCase();
  if (["python3", "py3", "3", "python 3"].indexOf(v) !== -1) return "Python3";
  if (["python2", "py2", "2", "python 2"].indexOf(v) !== -1) return "Python2";
  return raw || "";
}

function applySelectValue(selectors, normalizedValue, rawValue) {
  for (var s = 0; s < selectors.length; s++) {
    var el = document.querySelector(selectors[s]);
    if (!el) continue;
    var options = el.options || [];
    for (var i = 0; i < options.length; i++) {
      var optVal = (options[i].value || "").trim();
      var optText = (options[i].textContent || "").trim();
      if (optVal === normalizedValue || optVal === rawValue
          || optText === normalizedValue || optText === rawValue) {
        el.value = options[i].value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
  }
  return false;
}

function applyFrequency(freq) {
  if (!freq) return;
  var normalized = normalizeFrequency(freq);
  if (!normalized) return;
  var selectors = ["#frequency", "#runFreq", "select[name=\"frequency\"]", "select[name=\"runFreq\"]"];
  if (applySelectValue(selectors, normalized, freq)) return;

  var radios = document.querySelectorAll("input[type=\"radio\"][name*=\"freq\"], input[type=\"radio\"][name*=\"Freq\"]");
  for (var i = 0; i < radios.length; i++) {
    var rv = (radios[i].value || "").trim();
    if (rv === normalized || rv === freq) {
      radios[i].checked = true;
      radios[i].dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
  }

  throw new Error("Unable to set frequency to \"" + freq + "\". The frequency selector was not found on the page.");
}

function applyPyVersion(pyVer) {
  if (!pyVer) return;
  var normalized = normalizePyVersion(pyVer);
  if (!normalized) return;
  var selectors = ["#pyVersion", "#py_version", "select[name=\"pyVersion\"]", "select[name=\"py_version\"]"];
  if (applySelectValue(selectors, normalized, pyVer)) return;

  var radios = document.querySelectorAll("input[type=\"radio\"][name*=\"py\"], input[type=\"radio\"][name*=\"version\"]");
  for (var i = 0; i < radios.length; i++) {
    var rv = (radios[i].value || "").trim().toLowerCase();
    if (normalizePyVersion(rv) === normalized || rv === pyVer.toLowerCase()) {
      radios[i].checked = true;
      radios[i].dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
  }

  throw new Error("Unable to set Python version to \"" + pyVer + "\". The Python version selector was not found on the page.");
}

function applyBacktestParams(startDate, endDate, capital, frequency, pyVersion) {
  setInputValue("startTime", startDate, false);
  setInputValue("endTime", endDate, false);
  setInputValue("daily_backtest_capital_base_box", capital, true);

  if (frequency) {
    applyFrequency(frequency);
  }
  if (pyVersion) {
    applyPyVersion(pyVersion);
  }

  var effective = readEffectiveBacktestParams();

  if (frequency) {
    var expectedFreq = normalizeFrequency(frequency);
    var actualFreq = effective.frequency;
    if (expectedFreq && actualFreq && normalizeFrequency(actualFreq) !== expectedFreq) {
      throw new Error(
        "Frequency mismatch: requested \"" + frequency + "\" (normalized: \"" + expectedFreq
        + "\"), but page shows \"" + actualFreq + "\""
      );
    }
  }
  if (pyVersion) {
    var expectedPy = normalizePyVersion(pyVersion);
    var actualPy = effective.py_version;
    if (expectedPy && actualPy && normalizePyVersion(actualPy) !== expectedPy) {
      throw new Error(
        "Python version mismatch: requested \"" + pyVersion + "\" (normalized: \"" + expectedPy
        + "\"), but page shows \"" + actualPy + "\""
      );
    }
  }

  return effective;
}

function readEffectiveBacktestParams() {
  var freqEl = document.querySelector("#frequency, #runFreq, select[name=\"frequency\"]");
  var pyEl = document.querySelector("#pyVersion, #py_version, select[name=\"py_version\"]");

  return {
    start_date: document.getElementById("startTime")?.value || "",
    end_date: document.getElementById("endTime")?.value || "",
    capital: document.getElementById("daily_backtest_capital_base_box")?.value || "",
    frequency: freqEl ? (freqEl.value || "") : "",
    py_version: pyEl ? (pyEl.value || "") : "",
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

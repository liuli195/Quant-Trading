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
  if (["day", "daily", "1d", "d"].indexOf(v) !== -1) return "day";
  if (["min", "minute", "1m", "m"].indexOf(v) !== -1) return "minute";
  if (["tick"].indexOf(v) !== -1) return "tick";
  if (["5m", "5min"].indexOf(v) !== -1) return "5m";
  if (["15m", "15min"].indexOf(v) !== -1) return "15m";
  if (["30m", "30min"].indexOf(v) !== -1) return "30m";
  if (["60m", "60min", "1h", "h", "hourly"].indexOf(v) !== -1) return "60m";
  return raw ? v : "";
}

function normalizePyVersion(raw) {
  var v = String(raw || "").trim().toLowerCase();
  if (["python3", "py3", "3", "python 3"].indexOf(v) !== -1) return "3";
  if (["python2", "py2", "2", "python 2"].indexOf(v) !== -1) return "2";
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

function _clickSelectpickerOption(freqHiddenInput, normalizedValue) {
  // Find the Bootstrap selectpicker container near the hidden frequency input.
  var container = freqHiddenInput.parentElement;
  while (container && container.tagName !== "BODY") {
    var btn = container.querySelector("button.dropdown-toggle, button.selectpicker");
    if (btn) {
      // Open the dropdown if not already open.
      if (!btn.parentElement.classList.contains("open")) {
        btn.click();
      }
      // Find and click the matching option.
      var dropdown = container.querySelector("ul.dropdown-menu, div.dropdown-menu");
      if (dropdown) {
        var items = dropdown.querySelectorAll("li");
        for (var i = 0; i < items.length; i++) {
          var text = (items[i].textContent || "").trim().toLowerCase();
          if (text === normalizedValue || items[i].classList.contains("selected")) {
            items[i].querySelector("a")?.click();
            return true;
          }
        }
        // Fallback: click the first non-separator item that contains matching text
        for (var j = 0; j < items.length; j++) {
          var t = (items[j].textContent || "").trim().toLowerCase();
          if (t.indexOf(normalizedValue) !== -1 || normalizedValue.indexOf(t) !== -1) {
            items[j].querySelector("a")?.click();
            return true;
          }
        }
      }
      // Close dropdown if we couldn't find the option.
      if (btn.parentElement.classList.contains("open")) {
        btn.click();
      }
      break;
    }
    container = container.parentElement;
  }
  return false;
}

function applyFrequency(freq) {
  if (!freq) return;
  var normalized = normalizeFrequency(freq);
  if (!normalized) return;

  // 1. Set hidden input directly (new JoinQuant UI).
  var freqHidden = document.getElementById("frequency");
  if (freqHidden && freqHidden.type === "hidden") {
    freqHidden.value = normalized;
    freqHidden.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }

  // 2. Try legacy <select> elements.
  var selectors = ["#frequency", "#runFreq", "select[name=\"frequency\"]", "select[name=\"runFreq\"]"];
  if (applySelectValue(selectors, normalized, freq)) return;

  // 3. Try Bootstrap selectpicker (visible dropdown).
  if (freqHidden && _clickSelectpickerOption(freqHidden, normalized)) return;

  // 4. Try radio buttons.
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

  // 1. Try legacy <select> elements.
  var selectors = ["#pyVersion", "#py_version", "select[name=\"pyVersion\"]", "select[name=\"py_version\"]"];
  if (applySelectValue(selectors, normalized, pyVer)) return;

  // 2. Try hidden input (new JoinQuant UI).
  var hidden = document.querySelector("input[name=\"backtest[pyVersion]\"]");
  if (hidden) {
    hidden.value = normalized;
    hidden.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }

  // 3. Try radio buttons.
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
  var pyEl = document.querySelector("#pyVersion, #py_version, select[name=\"py_version\"], input[name=\"backtest[pyVersion]\"]");

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

function readCompileState() {
  const cancelBtn = document.querySelector("#cancel-daily-backtest-button, .cancel-build, .cancel-button");
  // Only treat as compiling if the cancel button is actually visible in the layout
  const hasCancel = !!(cancelBtn && cancelBtn.offsetParent !== null);
  const bodyText = document.body ? document.body.innerText || "" : "";
  const hasError = bodyText.includes("ERROR") || bodyText.includes("Traceback");

  return {
    hasCancel,
    hasError,
    bodyText,
  };
}

function isCompileFinished(seenCancel, state) {
  return seenCancel && !state.hasCancel && !state.hasError;
}

function readCompileErrors() {
  const errorTab = document.getElementById("daily-errors-tab");
  return errorTab ? errorTab.innerText || "" : "";
}

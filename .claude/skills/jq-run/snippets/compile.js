function readCompileState() {
  const hasCancel = !!document.querySelector(".cancel-build");
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

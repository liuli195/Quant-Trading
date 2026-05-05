function writeStrategyCodeToAce(code) {
  const editor = ace.edit("ide-container");
  if (!editor) {
    throw new Error("Ace 编辑器未初始化");
  }

  editor.setValue(String(code), -1);
  editor.clearSelection();

  const hiddenTextarea = document.getElementById("code");
  if (hiddenTextarea) {
    hiddenTextarea.value = String(code);
  }

  return {
    ok: true,
    length: String(code).length,
  };
}

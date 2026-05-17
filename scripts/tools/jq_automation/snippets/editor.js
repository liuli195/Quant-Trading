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

function writeBase64ToAce(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i) & 0xFF;
  }
  const code = new TextDecoder("utf-8").decode(bytes);
  const editor = ace.edit("ide-container");
  if (!editor) {
    throw new Error("Ace 编辑器未初始化");
  }

  editor.setValue(code, -1);
  editor.clearSelection();

  const hiddenTextarea = document.getElementById("code");
  if (hiddenTextarea) {
    hiddenTextarea.value = code;
  }

  return {
    ok: true,
    length: code.length,
  };
}

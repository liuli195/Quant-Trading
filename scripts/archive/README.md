# archive — 归档脚本工具

不再活跃使用但保留备查的独立脚本。

## 工具列表

### convert_docx_to_md.py

将 `.docx` 文件转换为 Markdown，支持标题层级、加粗/斜体、表格、列表和图片提取。

```powershell
.\.venv\Scripts\python.exe scripts/archive/convert_docx_to_md.py <输入.docx> [输出.md]
```

- `输入.docx` — 必填，源文件路径
- `输出.md` — 可选，默认与输入同名的 `.md` 文件

功能：
- 识别 Word 标题样式（Heading 1-6 / 标题 1-6），输出 `#`~`######`
- 保留加粗（`**`）、斜体（`*`）、加粗斜体（`***`）
- 列表项（带项目符号/编号）转为 `- ` 前缀
- 表格转为 Markdown 表格格式
- 图片提取到 `images/` 子目录

### convert_html_to_md.py

将聚宽 API 离线 HTML 文档（SingleFile 保存）转换为干净 Markdown，提取 base64 内嵌图片为 PNG。

```powershell
# 自动查找项目根目录下的聚宽 HTML 文件
.\.venv\Scripts\python.exe scripts/archive/convert_html_to_md.py

# 指定输入输出
.\.venv\Scripts\python.exe scripts/archive/convert_html_to_md.py `
  --html "API新 - JoinQuant.html" --out docs/reference/joinquant-api.md

# 指定图片目录
.\.venv\Scripts\python.exe scripts/archive/convert_html_to_md.py `
  --html input.html --out output.md --images docs/imgs
```

参数：
- `--html` — 输入 HTML 路径（默认：自动查找 `API新*.html`）
- `--out` — 输出 Markdown 路径（默认：`docs/reference/joinquant-api.md`）
- `--images` — 图片输出目录（默认：`docs/images`）

依赖：`beautifulsoup4`、`markdownify`（首次运行自动安装）

### RelayTools.py

纯函数库，无 CLI 入口。提供文档格式转换相关的工具函数。

## 注意事项

- 此目录下脚本不再活跃维护，保留备查
- 所有脚本从项目根目录执行，使用 `.\.venv\Scripts\python.exe` 作为 Python 解释器

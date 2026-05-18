"""
聚宽 API 离线 HTML 文档转换器
===============================
将 SingleFile 保存的聚宽 API 离线 HTML 文件转换为干净的 Markdown 文档，
提取图片并保存为独立的 PNG 文件。

用法:
    python scripts/convert_html_to_md.py
    python scripts/convert_html_to_md.py --html "path/to/input.html" --out "docs/output.md"
"""

import argparse
import base64
import os
import re
import subprocess
import sys
import hashlib
from pathlib import Path
from io import BytesIO

# ============================================================
# 依赖检查与安装
# ============================================================

def ensure_dependencies():
    """确保必要的第三方库已安装，缺失时自动安装"""
    deps = {
        'bs4': 'beautifulsoup4',
        'markdownify': 'markdownify',
    }
    missing = []
    for import_name, pkg_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        print(f"[依赖] 正在安装缺失的包: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', *missing],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("[依赖] 安装完成")


ensure_dependencies()

from bs4 import BeautifulSoup, Tag, NavigableString
from markdownify import MarkdownConverter


# ============================================================
# 图片提取器
# ============================================================

class ImageExtractor:
    """从 HTML 中提取 base64 内嵌图片，保存为 PNG 文件"""

    def __init__(self, images_dir: Path):
        self.images_dir = images_dir
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.image_map = {}  # src_hash → filename
        self.count = 0

    def extract_base64(self, soup_tag, context_heading: str = '') -> str:
        """解析 base64 图片的 src 属性，提取 data URI 并保存为 PNG"""
        src = soup_tag.get('src', '')
        if not src.startswith('data:'):
            return src  # 非 base64，保留原值

        # 解析 data URI: data:image/png;base64,xxxxx
        match = re.match(r'data:image/(\w+);base64,(.+)', src, re.DOTALL)
        if not match:
            return src

        img_format = match.group(1)  # png, jpeg, gif 等
        b64_data = match.group(2)

        try:
            raw = base64.b64decode(b64_data)
        except Exception as e:
            print(f"  [警告] base64 解码失败: {e}")
            return src

        # 用内容哈希确保唯一性
        content_hash = hashlib.md5(raw).hexdigest()[:8]

        # 尝试从 alt 或 context_heading 获取可读文件名
        alt_text = soup_tag.get('alt', '').strip()
        if alt_text:
            slug = re.sub(r'[^\w一-鿿-]', '_', alt_text)[:40]
        elif context_heading:
            slug = re.sub(r'[^\w一-鿿-]', '_', context_heading)[:40]
        else:
            slug = content_hash

        filename = f"{slug}_{content_hash}.{img_format}"
        filepath = self.images_dir / filename

        if not filepath.exists():
            filepath.write_bytes(raw)

        self.count += 1
        rel_path = f"images/{filename}"
        self.image_map[content_hash] = rel_path
        return rel_path


# ============================================================
# Markdown 转换器
# ============================================================

class JoinQuantMDConverter(MarkdownConverter):
    """继承 markdownify 的转换器，针对聚宽文档做定制化处理"""

    # 代码块前缀标记，用于后续修复语言标注
    CODE_PLACEHOLDER = '%%CODEBLOCK%%'

    def __init__(self, image_extractor: ImageExtractor, **kwargs):
        super().__init__(**kwargs)
        self.img_extractor = image_extractor
        self._current_section_heading = ''  # 当前所在章节标题，用于图片命名

    def convert_a(self, el, text, parent_tags):
        """处理 <a> 标签，保留链接目标"""
        href = el.get('href', '')
        if href and not href.startswith('#'):
            # 外部链接保留完整 URL
            pass
        return super().convert_a(el, text, parent_tags)

    def convert_img(self, el, text, parent_tags):
        """处理 <img> 标签，提取 base64 图片并替换为本地路径"""
        src = el.get('src', '')
        if src.startswith('data:'):
            new_src = self.img_extractor.extract_base64(el, self._current_section_heading)
            el['src'] = new_src
        elif src.startswith(('http://', 'https://')):
            pass  # 外部图片保持原样
        return super().convert_img(el, text, parent_tags)


# ============================================================
# HTML 预处理
# ============================================================

def preprocess_html(soup: BeautifulSoup) -> BeautifulSoup:
    """对 BeautifulSoup 解析后的 DOM 做预处理"""

    # 1. 移除不需要的元素
    for selector in [
        'script', 'style', 'link[rel=stylesheet]',
        'div.am-tree',           # 左侧导航树
        'div.help-api-left',     # 左侧边栏
        '.sf-hidden',            # 隐藏元素
        '.hidden',               # 隐藏元素
    ]:
        for el in soup.select(selector):
            el.decompose()

    # 2. 提取 jq-api-content 主体内容
    api_content = soup.select_one('#jq-api-content')
    if not api_content:
        # 尝试提取 help-api-right 区域
        api_content = soup.select_one('div.help-api-right')
    if not api_content:
        raise ValueError("未找到 #jq-api-content 或 .help-api-right 内容区域")

    # 3. 处理 div.group 结构 — 每个 group 是一个 API 函数文档
    # 结构: <div class=group>
    #         <label>函数名</label>
    #         <label>简要描述</label>
    #         <article>详细文档</article>
    #       </div>
    for group in api_content.select('div.group'):
        labels = group.select('label')
        article = group.select_one('article')

        if not labels or not article:
            continue

        # 获取函数名（第一个 label）
        func_name_tag = labels[0]
        func_name = func_name_tag.get_text(strip=True)
        func_name_span = func_name_tag.select_one('span')
        if func_name_span:
            func_name = func_name.replace(func_name_span.get_text(strip=True), '').strip()

        # 获取简要描述（第二个 label，如果有）
        brief_desc = ''
        if len(labels) >= 2:
            brief_desc = labels[1].get_text(strip=True)

        # 跳过空的 article
        article_html = article.decode_contents().strip()
        if not article_html:
            continue

        # 构建一个包装 section，用 h3 标题标记函数名
        section = soup.new_tag('div')
        h3 = soup.new_tag('h3')
        h3.string = f"{func_name} — {brief_desc}" if brief_desc else func_name
        section.append(h3)

        # 将 article 内容移入 section
        for child in list(article.children):
            section.append(child)

        # 用 section 替换原来的 group
        group.replace_with(section)

    # 4. 移除 group 外面的 <span class="glyphicon...">
    for span in api_content.select('span.glyphicon'):
        span.decompose()

    # 5. 处理 code 块中的类名，保留语言标注
    for code_el in api_content.select('pre code'):
        classes = code_el.get('class', [])
        lang = ''
        for cls in classes:
            if cls in ('python', 'javascript', 'java', 'sql', 'bash', 'json', 'xml', 'yaml'):
                lang = cls
                break
            if 'python' in cls:
                lang = 'python'
                break
        if lang:
            code_el['data-lang'] = lang
        # 标记 code 块的 pre 父元素
        pre_parent = code_el.parent
        if pre_parent and pre_parent.name == 'pre':
            pre_parent['data-codeblock'] = 'true'

    return api_content


# ============================================================
# Markdown 后处理
# ============================================================

def postprocess_markdown(md_text: str) -> str:
    """对生成的 Markdown 文本做后处理"""

    # 1. 将 markdownify 生成的代码块标记转换为标准 fenced code blocks
    # markdownify 会将 <pre><code class="python"> 转为换行缩进格式
    # 我们需要将其转为 ```python ... ``` 格式

    lines = md_text.split('\n')
    result = []
    i = 0
    in_code_block = False
    code_lines_buffer = []

    while i < len(lines):
        line = lines[i]

        # 检测代码块开始（markdownify 生成的多行代码通常以空行后的缩进开始）
        stripped = line.strip()
        if stripped and not line.startswith(' ') and not line.startswith('\t'):
            # 非缩进行，可能是普通文本
            if code_lines_buffer:
                # 结束之前的代码块
                result.append('```')
                result.extend(code_lines_buffer)
                result.append('```')
                result.append('')
                code_lines_buffer = []
                in_code_block = False
            result.append(line)
            i += 1
            continue

        # 检查缩进行（4空格或tab）
        if stripped and (line.startswith('    ') or line.startswith('\t')):
            # 收集连续缩进行作为代码块
            if not in_code_block:
                # 确定语言
                lang = ''
                # 检查上一行是否包含语言标记（markdownify 可能保留了 class 信息）
                if code_lines_buffer:
                    lang = ''
                code_lines_buffer = []
                in_code_block = True
            # 移除缩进
            unindented = re.sub(r'^(?:\t|    )', '', line) if line.startswith('    ') else line[1:]
            code_lines_buffer.append(unindented)
            i += 1
            continue

        if not stripped and in_code_block:
            # 空行 — 可能是代码块内空行，也可能结束代码块
            # 先查看后续是否还有缩进行
            look_ahead = i + 1
            while look_ahead < len(lines) and not lines[look_ahead].strip():
                look_ahead += 1
            if look_ahead < len(lines) and (
                lines[look_ahead].startswith('    ') or lines[look_ahead].startswith('\t')
            ):
                # 后续还有缩进行，空行属于代码块
                code_lines_buffer.append('')
                i += 1
                continue
            else:
                # 代码块结束
                if code_lines_buffer:
                    # 移除代码块末尾多余空行
                    while code_lines_buffer and not code_lines_buffer[-1].strip():
                        code_lines_buffer.pop()
                    result.append('```')
                    result.extend(code_lines_buffer)
                    result.append('```')
                    result.append('')
                    code_lines_buffer = []
                    in_code_block = False
                result.append(line)
                i += 1
                continue

        result.append(line)
        i += 1

    # 处理末尾残留代码块
    if code_lines_buffer:
        result.append('```')
        result.extend(code_lines_buffer)
        result.append('```')

    md_text = '\n'.join(result)

    # 2. 合并过多的连续空行（最多保留 2 个空行）
    md_text = re.sub(r'\n\n\n+', '\n\n', md_text)

    # 3. 清理行尾空白
    md_text = '\n'.join(line.rstrip() for line in md_text.split('\n'))

    # 4. 在标题前后确保有空行
    md_text = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', md_text)
    md_text = re.sub(r'(#{1,6} [^\n]+)\n([^\n`#])', r'\1\n\n\2', md_text)

    # 5. 修复 markdownify 产生的 [code]...[/code] 包裹 (旧版 html2text 残留格式)
    md_text = re.sub(
        r'\[code\](.*?)\[/code\]',
        lambda m: '```\n' + m.group(1).strip() + '\n```',
        md_text, flags=re.DOTALL
    )

    return md_text


# ============================================================
# 主处理流程
# ============================================================

def convert_html_to_md(html_path: str, output_path: str, images_dir: str = 'docs/images'):
    """
    将聚宽离线 HTML 文档转换为 Markdown

    Args:
        html_path: 输入 HTML 文件路径
        output_path: 输出 Markdown 文件路径
        images_dir: 图片输出目录
    """
    project_root = Path(html_path).parent
    images_full_dir = project_root / images_dir

    print(f"[输入] {html_path}")
    print(f"[输出] {output_path}")
    print(f"[图片] {images_full_dir}")

    # --- 读取并解析 HTML ---
    print("[步骤 1/5] 读取并解析 HTML...")
    with open(html_path, 'r', encoding='utf-8') as f:
        raw_html = f.read()

    soup = BeautifulSoup(raw_html, 'html.parser')

    # --- 提取图片 ---
    print("[步骤 2/5] 提取图片...")
    img_extractor = ImageExtractor(images_full_dir)

    # --- 预处理 DOM ---
    print("[步骤 3/5] 预处理 HTML 结构...")
    content_root = preprocess_html(soup)

    # --- 转换 Markdown ---
    print("[步骤 4/5] 转换 HTML → Markdown...")

    converter = JoinQuantMDConverter(
        img_extractor,
        heading_style='ATX',           # 使用 # 风格标题
        bullets='-',                    # 使用 - 作为无序列表符号
        strip=['script', 'style'],      # 剥离脚本和样式
        code_language_callback=lambda el: el.get('data-lang', ''),
        default_title=True,
    )

    # 提取图片时使用上下文标题信息
    for h_tag in content_root.find_all(['h2', 'h3', 'h4']):
        h_text = h_tag.get_text(strip=True)
        # 将上下文信息注入该标题区域内的 img 处理
        for img in h_tag.find_all('img'):
            if img.get('src', '').startswith('data:'):
                new_src = img_extractor.extract_base64(img, h_text)
                img['src'] = new_src

    # 对所有 img 统一处理
    for img in content_root.find_all('img'):
        src = img.get('src', '')
        if src.startswith('data:'):
            new_src = img_extractor.extract_base64(img, '')
            img['src'] = new_src

    # 执行转换
    md_text = converter.convert(str(content_root))

    # --- 后处理 ---
    print("[步骤 5/5] 后处理 Markdown...")
    md_text = postprocess_markdown(md_text)

    # --- 写入文件 ---
    output_full_path = project_root / output_path
    output_full_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_full_path, 'w', encoding='utf-8') as f:
        f.write(md_text)

    # --- 统计信息 ---
    line_count = md_text.count('\n') + 1
    file_size = len(md_text.encode('utf-8'))

    print()
    print("=" * 60)
    print("  转换完成")
    print("=" * 60)
    print(f"  输出文件:     {output_path}")
    print(f"  文件大小:     {file_size:,} 字节 ({file_size/1024:.1f} KB)")
    print(f"  行数:         {line_count}")
    print(f"  图片提取:     {img_extractor.count} 张 → {images_dir}/")
    print("=" * 60)

    return {
        'line_count': line_count,
        'file_size': file_size,
        'image_count': img_extractor.count,
        'output_path': str(output_full_path),
        'images_dir': str(images_full_dir),
    }


# ============================================================
# 命令行入口
# ============================================================

def main():
    # 项目根目录（脚本所在目录的上级）
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description='聚宽 API 离线 HTML 文档 → Markdown 转换器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/convert_html_to_md.py
  python scripts/convert_html_to_md.py --html "API新 - JoinQuant.html" --out docs/reference/joinquant-api.md
  python scripts/convert_html_to_md.py --html input.html --out output.md --images docs/imgs
        """
    )

    parser.add_argument(
        '--html',
        type=str,
        default=None,
        help='输入 HTML 文件路径（默认: 自动查找项目根目录下的 聚宽 HTML 文件）'
    )
    parser.add_argument(
        '--out',
        type=str,
        default='docs/reference/joinquant-api.md',
        help='输出 Markdown 路径，相对于项目根目录（默认: docs/reference/joinquant-api.md）'
    )
    parser.add_argument(
        '--images',
        type=str,
        default='docs/images',
        help='图片输出目录，相对于项目根目录（默认: docs/images）'
    )

    args = parser.parse_args()

    # 确定输入文件
    if args.html:
        html_path = args.html
    else:
        # 自动查找项目根目录下以 "API新" 开头的 .html 文件
        candidates = sorted(project_root.glob('API新*.html'))
        if not candidates:
            print("[错误] 未找到聚宽离线 HTML 文件。请用 --html 指定路径。")
            sys.exit(1)
        # 取最新的文件（按修改时间）
        html_path = str(max(candidates, key=lambda p: p.stat().st_mtime))
        print(f"[自动选择] {html_path}")

    try:
        convert_html_to_md(html_path, args.out, args.images)
    except Exception as e:
        print(f"\n[错误] 转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

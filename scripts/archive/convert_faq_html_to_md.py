"""
聚宽 FAQ 离线 HTML 文档转换器
================================
将 SingleFile 保存的聚宽 常见问题 离线 HTML 文件转换为干净的 Markdown 文档，
提取 base64 内嵌图片并保存为独立的 PNG 文件。

FAQ 页面结构:
  <div class=help-api-right>
    <div id=jq-api-content>
      <h2>常见问题</h2>
      <h3 id=分类名>分类名</h3>        ← 分类（## 标题）
      <h4 id=问题>问题文本</h4>         ← 问题（### 标题）
      <p>/<ul>/<ol>/<table>/<pre>...  ← 答案内容

用法:
    python scripts/archive/convert_faq_html_to_md.py
    python scripts/archive/convert_faq_html_to_md.py --html "path/to/faq.html" --out "docs/output.md"
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
# 图片提取器（与 convert_html_to_md.py 共用逻辑）
# ============================================================

class ImageExtractor:
    """从 HTML 中提取 base64 内嵌图片，保存为 PNG 文件"""

    def __init__(self, images_dir: Path, output_md_dir: Path = None):
        self.images_dir = images_dir
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.image_map = {}
        self.count = 0
        # 计算从 MD 所在目录到 images 目录的相对路径前缀
        if output_md_dir:
            try:
                self.rel_prefix = Path(os.path.relpath(images_dir, output_md_dir)).as_posix() + '/'
            except ValueError:
                self.rel_prefix = 'images/'
        else:
            self.rel_prefix = 'images/'

    def extract_base64(self, src: str, alt_text: str = '') -> str:
        """解析 base64 data URI，保存为图片文件，返回相对 MD 的正确路径"""
        if not src.startswith('data:'):
            return src

        match = re.match(r'data:image/(\w+);base64,(.+)', src, re.DOTALL)
        if not match:
            return src

        img_format = match.group(1)
        b64_data = match.group(2)

        try:
            raw = base64.b64decode(b64_data)
        except Exception as e:
            print(f"  [警告] base64 解码失败: {e}")
            return src

        content_hash = hashlib.md5(raw).hexdigest()[:8]

        if alt_text:
            slug = re.sub(r'[^\w一-鿿-]', '_', alt_text)[:40]
        else:
            slug = content_hash

        filename = f"{slug}_{content_hash}.{img_format}"
        filepath = self.images_dir / filename

        if not filepath.exists():
            filepath.write_bytes(raw)

        self.count += 1
        rel_path = f"{self.rel_prefix}{filename}"
        self.image_map[content_hash] = rel_path
        return rel_path


# ============================================================
# Markdown 转换器
# ============================================================

class FAQMarkdownConverter(MarkdownConverter):
    """针对聚宽 FAQ 页面的 Markdown 转换器"""

    def __init__(self, image_extractor: ImageExtractor, **kwargs):
        super().__init__(**kwargs)
        self.img_extractor = image_extractor

    def convert_img(self, el, text, parent_tags):
        """处理 <img> 标签，提取 base64 图片"""
        src = el.get('src', '')
        alt = el.get('alt', '')
        if src.startswith('data:'):
            new_src = self.img_extractor.extract_base64(src, alt)
            el['src'] = new_src
        return super().convert_img(el, text, parent_tags)


# ============================================================
# HTML 预处理：提取 FAQ 内容
# ============================================================

def extract_faq_content(soup: BeautifulSoup) -> Tag:
    """从 SingleFile HTML 中提取 FAQ 内容区域，重构为干净的 DOM"""

    # 1. 找到主内容容器
    api_content = soup.select_one('#jq-api-content')
    if not api_content:
        api_content = soup.select_one('div.help-api-right')
    if not api_content:
        raise ValueError("未找到 #jq-api-content 或 .help-api-right 内容区域")

    # 2. 移除隐藏元素
    for hidden in api_content.select('.sf-hidden, .hidden'):
        hidden.decompose()

    # 3. 跳过 <h2>常见问题</h2> 标题及其后的介绍段落，
    #    直到第一个 <h3> 分类标题
    first_h3 = None
    for child in list(api_content.children):
        if isinstance(child, Tag) and child.name == 'h3':
            first_h3 = child
            break

    if not first_h3:
        raise ValueError("未找到任何 h3 分类标题")

    # 4. 构建新的内容容器，从第一个 h3 开始
    container = soup.new_tag('div')

    # 添加页面标题
    h1 = soup.new_tag('h1')
    h1.string = '常见问题'
    container.append(h1)

    # 从第一个 h3 开始复制所有内容
    should_copy = False
    for child in list(api_content.children):
        if child is first_h3:
            should_copy = True
        if should_copy:
            container.append(child)

    # 5. 处理 code 块：提取语言标注，剥离 syntax-highlighting span
    for pre in container.select('pre code'):
        classes = pre.get('class', [])
        lang = ''
        for cls in classes:
            # 识别 language-xxx 或直接的 xxx 类名
            lang_match = re.match(r'(?:language-)?(python|javascript|java|sql|bash|json|xml|yaml|text|shell|css|html)', cls)
            if lang_match:
                lang = lang_match.group(1)
                break
            if cls in ('python', 'javascript', 'java', 'sql', 'bash', 'json', 'xml', 'yaml'):
                lang = cls
                break
        if lang:
            pre['data-lang'] = lang

        # 移除 syntax-highlighting span，保留纯文本
        has_hljs_spans = pre.find_all(
            lambda t: t.name == 'span' and any(c.startswith('hljs') for c in t.get('class', []))
        )
        if has_hljs_spans:
            code_text = pre.get_text()
            pre.clear()
            pre.string = code_text

        # 标记 pre
        pre_parent = pre.parent
        if pre_parent and pre_parent.name == 'pre':
            pre_parent['data-codeblock'] = 'true'

    # 6. 分类 h3 标签：区分"分类标题"与"分类内子问题"
    #    规则：
    #      - 不带 id 的 h3 → 子问题（如 "为什么有时看到的期货主力合约..."）
    #      - id 含 "pandas" 的 h3 → 子问题（如 "Pandas: 如何增加..."）
    #      - 其余带 id 的 h3 → 分类标题
    for h3 in container.find_all('h3'):
        h3_id = h3.get('id', '')
        if not h3_id or 'pandas' in h3_id.lower():
            h3['data-level'] = 'subquestion'
        else:
            h3['data-level'] = 'category'

    # 7. 为所有 h4 问题编号（用于锚点）
    question_index = 0
    for tag in container.find_all(['h3', 'h4']):
        if tag.name == 'h4' or (tag.name == 'h3' and tag.get('data-level') == 'subquestion'):
            question_index += 1
            tag['data-qnum'] = str(question_index)

    return container


# ============================================================
# 元素级渲染（精细控制 Markdown 输出）
# ============================================================

def render_element_to_md(el, converter: FAQMarkdownConverter) -> str:
    """将单个 HTML 元素渲染为 Markdown，特殊处理 code/table/img"""
    if not isinstance(el, Tag):
        # 文本节点
        text = str(el).strip()
        return text if text else ''

    tag_name = el.name

    # --- 标题 ---
    if tag_name == 'h3':
        text = el.get_text(strip=True)
        level = el.get('data-level', 'category')
        if level == 'subquestion':
            return f'\n### {text}\n\n'
        else:
            return f'\n## {text}\n\n'
    elif tag_name == 'h4':
        text = el.get_text(strip=True)
        return f'\n### {text}\n\n'

    # --- 代码块：直接提取纯文本 + 手动加 fences，绕过 markdownify 避免 ## 泄漏 ---
    elif tag_name == 'pre':
        code_el = el.select_one('code')
        lang = ''
        if code_el:
            lang = code_el.get('data-lang', '')
            code_text = code_el.get_text()
        else:
            code_text = el.get_text()
        return f'\n```{lang}\n{code_text.strip()}\n```\n\n'

    # --- 表格 ---
    elif tag_name == 'table':
        return '\n' + converter.convert(str(el)).strip() + '\n\n'

    # --- 图片 ---
    elif tag_name == 'img':
        src = el.get('src', '')
        alt = el.get('alt', '')
        if src.startswith('data:'):
            src = converter.img_extractor.extract_base64(src, alt)
        return f'\n![{alt}]({src})\n\n'

    # --- 段落、列表 ---
    elif tag_name in ('p', 'ul', 'ol', 'blockquote', 'dl'):
        md = converter.convert(str(el)).strip()
        return '\n' + md + '\n\n'

    # --- 其他 ---
    else:
        md = converter.convert(str(el)).strip()
        return '\n' + md + '\n\n' if md else ''


# ============================================================
# Markdown 后处理
# ============================================================

def postprocess_markdown(md_text: str) -> str:
    """清理生成的 Markdown"""

    # 1. 合并过多空行（最多保留 2 个）
    md_text = re.sub(r'\n\n\n+', '\n\n', md_text)

    # 2. 清理行尾空白
    md_text = '\n'.join(line.rstrip() for line in md_text.split('\n'))

    # 3. 标题前后确保有空行
    md_text = re.sub(r'([^\n])\n(#{1,3} )', r'\1\n\n\2', md_text)
    md_text = re.sub(r'(#{1,3} [^\n]+)\n([^\n`#>])', r'\1\n\n\2', md_text)

    # 4. 确保文件以换行结尾
    if not md_text.endswith('\n'):
        md_text += '\n'

    # 5. 修复 markdownify 产生的非标准代码包裹
    md_text = re.sub(
        r'\[code\](.*?)\[/code\]',
        lambda m: '```\n' + m.group(1).strip() + '\n```',
        md_text, flags=re.DOTALL
    )

    return md_text


# ============================================================
# 主处理流程
# ============================================================

# 导入路径别名系统
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'tools' / 'path_tools'))
from aliases import resolve_path


def convert_faq_html_to_md(html_path: str, images_alias: str = 'docs_images',
                           output_alias: str = 'joinquant_data', output_filename: str = 'JQ_常见问题.md'):
    """
    将聚宽 FAQ 离线 HTML 文档转换为 Markdown

    Args:
        html_path: 输入 HTML 文件路径
        images_alias: 图片输出目录别名（默认 docs_images → docs/images）
        output_alias: MD 输出目录别名（默认 joinquant_data → docs/joinquant-data）
        output_filename: 输出 Markdown 文件名
    """
    images_full_dir = resolve_path(images_alias)
    output_md_dir = resolve_path(output_alias)
    output_full_path = output_md_dir / output_filename

    print(f"[输入] {html_path}")
    print(f"[输出] {output_full_path}")
    print(f"[图片] {images_full_dir}")

    # --- 读取并解析 HTML ---
    print("[步骤 1/4] 读取并解析 HTML...")
    with open(html_path, 'r', encoding='utf-8') as f:
        raw_html = f.read()

    soup = BeautifulSoup(raw_html, 'html.parser')

    # --- 提取图片（传入 MD 所在目录以计算正确相对路径）---
    print("[步骤 2/4] 提取图片...")
    img_extractor = ImageExtractor(images_full_dir, output_md_dir)

    # --- 提取并重构 FAQ 内容 ---
    print("[步骤 3/4] 提取 FAQ 内容并转换...")
    content_root = extract_faq_content(soup)

    # 创建转换器
    converter = FAQMarkdownConverter(
        img_extractor,
        heading_style='ATX',
        bullets='-',
        strip=['script', 'style'],
        code_language_callback=lambda el: el.get('data-lang', ''),
    )

    # 逐个子元素渲染
    md_parts = []
    for child in content_root.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                md_parts.append(text + '\n\n')
            continue
        if not isinstance(child, Tag):
            continue
        rendered = render_element_to_md(child, converter)
        md_parts.append(rendered)

    md_text = ''.join(md_parts)

    # --- 后处理 ---
    print("[步骤 4/4] 后处理 Markdown...")
    md_text = postprocess_markdown(md_text)

    # --- 写入文件 ---
    output_full_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_full_path, 'w', encoding='utf-8') as f:
        f.write(md_text)

    # --- 统计 ---
    line_count = md_text.count('\n') + 1
    file_size = len(md_text.encode('utf-8'))

    # 统计真实分类和问题数（排除代码围栏内的 ##/###）
    md_no_fences = re.sub(r'```.*?```', '', md_text, flags=re.DOTALL)
    category_count = len(re.findall(r'^## ', md_no_fences, re.MULTILINE))
    question_count = len(re.findall(r'^### ', md_no_fences, re.MULTILINE))

    print()
    print("=" * 60)
    print("  转换完成")
    print("=" * 60)
    print(f"  输出文件:     {output_full_path}")
    print(f"  文件大小:     {file_size:,} 字节 ({file_size/1024:.1f} KB)")
    print(f"  行数:         {line_count}")
    print(f"  分类数:       {category_count}")
    print(f"  问题数:       {question_count}")
    print(f"  图片提取:     {img_extractor.count} 张 → {images_full_dir}")
    print("=" * 60)

    return {
        'line_count': line_count,
        'file_size': file_size,
        'image_count': img_extractor.count,
        'category_count': category_count,
        'question_count': question_count,
        'output_path': str(output_full_path),
        'images_dir': str(images_full_dir),
    }


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='聚宽 FAQ 离线 HTML → Markdown 转换器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/archive/convert_faq_html_to_md.py
  python scripts/archive/convert_faq_html_to_md.py --html "docs/joinquant-data/常见问题.html" --out docs/joinquant-data/JQ_常见问题.md
        """
    )

    parser.add_argument(
        '--html', type=str, default=None,
        help='输入 HTML 文件路径（默认: 自动查找 joinquant-data 下的 常见问题 HTML）'
    )
    parser.add_argument(
        '--out', type=str, default='JQ_常见问题.md',
        help='输出 Markdown 文件名（默认: JQ_常见问题.md）'
    )
    parser.add_argument(
        '--images-alias', type=str, default='docs_images',
        help='图片输出目录别名（默认: docs_images）'
    )
    parser.add_argument(
        '--output-alias', type=str, default='joinquant_data',
        help='MD 输出目录别名（默认: joinquant_data）'
    )

    args = parser.parse_args()

    # 确定输入文件
    if args.html:
        html_path = args.html
    else:
        joinquant_dir = resolve_path('joinquant_data')
        candidates = sorted(joinquant_dir.glob('常见问题*.html'))
        if not candidates:
            print("[错误] 未找到 FAQ HTML 文件。请用 --html 指定路径。")
            sys.exit(1)
        html_path = str(max(candidates, key=lambda p: p.stat().st_mtime))
        print(f"[自动选择] {html_path}")

    try:
        convert_faq_html_to_md(
            html_path,
            images_alias=args.images_alias,
            output_alias=args.output_alias,
            output_filename=args.out,
        )
    except Exception as e:
        print(f"\n[错误] 转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

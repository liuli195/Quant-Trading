"""Remove comments from strategy file for JoinQuant upload."""
import re
import sys

def strip_python_comments(code):
    """Remove # comments and docstrings, keep code structure."""
    lines = code.split('\n')
    stripped_lines = []
    for line in lines:
        result = []
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == "'" and not in_double:
                in_single = not in_single
                result.append(c)
            elif c == '"' and not in_single:
                in_double = not in_double
                result.append(c)
            elif c == '#' and not in_single and not in_double:
                break
            else:
                result.append(c)
            i += 1
        stripped = ''.join(result).rstrip()
        if stripped.strip():
            stripped_lines.append(stripped)
    result = '\n'.join(stripped_lines)
    # Remove module-level docstring (first thing after imports)
    result = re.sub(r'^"""[\s\S]*?"""', '', result, count=1)
    # Remove function docstrings
    result = re.sub(r'\n    """[\s\S]*?"""', '', result)
    return result

if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2]
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()
    stripped = strip_python_comments(content)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(stripped)
    print(f'Original: {len(content)} chars, Stripped: {len(stripped)} chars')

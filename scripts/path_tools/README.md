# Path Tools

This directory contains the repository path governance tools.

## Directory Aliases

`path_aliases.json` lives at the repository root and is the single source for
semantic directories such as `strategy_reports`, `backtest_report_dir`, and
`docs_images`.

Resolve an alias:

```bash
python -m scripts.path_tools.aliases resolve backtest_report_dir strategy=etf_dynamic_rebalance run_id=xxx
```

Use it from Python:

```python
from scripts.path_tools.aliases import resolve, resolve_path
```

## Markdown Dual References

Important internal Markdown file links should include both a normal clickable
path and a machine-readable `pathref` comment:

```md
[Threshold comparison](../../strategies/etf_dynamic_rebalance/reports/01-threshold-comparison.md) <!-- pathref: strategy_reports(strategy=etf_dynamic_rebalance)/01-threshold-comparison.md -->
```

The normal Markdown path is for humans and editors. The `pathref` is the source
used by tooling to check and rewrite links when directories move.

## Refactor Commands

Check pathrefs:

```bash
python -m scripts.path_tools.refactor check
```

Rewrite Markdown links from pathrefs:

```bash
python -m scripts.path_tools.refactor rewrite-md --dry-run
python -m scripts.path_tools.refactor rewrite-md
```

Move a file or directory and update references:

```bash
python -m scripts.path_tools.refactor move old/path.md new/path.md
```

Apply multiple moves:

```bash
python -m scripts.path_tools.refactor rewrite --map moves.json --dry-run
python -m scripts.path_tools.refactor rewrite --map moves.json
```

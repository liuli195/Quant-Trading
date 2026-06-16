# 日常增量验证提速方案设计

## Why
日常迭代不再默认跑完整 pathref、governance、skill owner 全链路。核心策略：新增 repo-native affected 验证层，本地 PR 提交走 pr-submit，最终完整验证证据来自 GitHub verify-full。

## What Changes
- 新增三层验证合同：verify-fast（日常迭代）、verify-full（CI 兜底）、verify-explain（命中/跳过/缓存说明）
- 新增轻量 affected 引擎，根据路径映射选择 scoped checks
- 新增 .local/governance-cache/ 本地缓存，只缓存通过结果
- 更新 hooks：pre-commit 改为 verify fast --staged；pre-push 不再运行本地 verify full

## Impact
日常文档小改不会运行 full governance gate。verify-fast 通过只代表"可继续开发"，不代表"可合并"。PR 合并依赖 GitHub required checks。

---
source: docs/design/日常增量验证提速方案设计.md

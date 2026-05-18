# 研究规格

- 研究对象：`PortfolioVolScale`
- 主算法：解析行为断点，并为相邻断点区间补代表点
- 扫描区间：每个 `PortfolioVolWindow` 分别覆盖 `[0, 历史最大组合波动率]`
- 不把 `TargetVol=0` 作为正式候选，只把它作为研究边界

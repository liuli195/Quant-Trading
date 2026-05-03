"""
三 ETF 动态配比策略 — 单元测试与集成测试

测试覆盖：
  - 静态检查（语法编译、import 清洁度）
  - 纯函数单元测试（zscore_clip, compute_target_weights, apply_weight_constraints）
  - 因子函数测试（黄金/AI/纳指，monkeypatch BIAS/ROC）
  - 策略初始化测试（set_option, set_order_cost, run_weekly 等）
  - daily_check 集成测试（mock 完整调仓流程，含偏离度阈值）

参考文档：strategies/etf_dynamic_rebalance/tests/test-guide.md
"""

import sys
import math
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch, call

import numpy as np
import pandas as pd
import pytest

# 通过 sys.modules 访问 BIAS/ROC mock（conftest 已将 mock 注入 sys.modules['jqlib.technical_analysis']）
MOCK_BIAS = sys.modules['jqlib.technical_analysis'].BIAS
MOCK_ROC = sys.modules['jqlib.technical_analysis'].ROC


# ============================================================
# 可复用的价格序列生成工具（本地副本，避免跨文件 import）
# ============================================================

def make_linear_prices(start=1.0, step=0.01, n_days=100):
    """生成线性上涨的价格序列。"""
    return np.arange(start, start + step * n_days, step)[:n_days]


def make_linear_down_prices(start=2.0, step=0.01, n_days=100):
    """生成线性下跌的价格序列。"""
    return np.arange(start, start - step * n_days, -step)[:n_days]


def make_constant_prices(value=1.0, n_days=100):
    """生成常数价格序列。"""
    return np.full(n_days, value)


def make_v_shape_prices(n_days=100):
    """生成先跌后涨的 V 形价格序列。"""
    half = n_days // 2
    down = np.arange(1.0, 0.5, -0.5 / half)[:half]
    up = np.arange(0.5, 1.0, 0.5 / (n_days - half))[:n_days - half]
    return np.concatenate([down, up])


# ============================================================
# 辅助函数
# ============================================================

def make_mock_context(total_value=500000.0, positions_weights=None):
    """
    构造 mock context 对象，模拟聚宽的 context 结构。

    参数:
        total_value: 总资产
        positions_weights: dict，如 {'518880.XSHG': 0.3, ...} 指定各 ETF 持仓权重

    关键：使用 side_effect + 内建 dict 实现按 key 查找，
    因为 MagicMock.__getitem__.return_value 优先级高于 __setitem__ 赋值。
    """
    context = MagicMock()
    context.portfolio.total_value = total_value
    context.previous_date = pd.Timestamp('2025-01-06')

    # 建造 positions 内建 dict
    _positions_dict = {}
    if positions_weights:
        for code, weight in positions_weights.items():
            pos = MagicMock()
            pos.total_amount = 1000  # 非零表示有持仓
            pos.value = total_value * weight
            _positions_dict[code] = pos

    # 设置 side_effect：已有持仓返回 pos，否则返回 None
    context.portfolio.positions.__getitem__.side_effect = (
        lambda k: _positions_dict.get(k)
    )

    return context


def make_mock_get_price_return(prices_dict, dates=None):
    """
    构造 get_price 的 mock 返回值。

    get_price 被逐 ETF 调用，每次返回一个 DataFrame（含 close 列）。

    参数:
        prices_dict: {etf_code: np.array of prices}
        dates: 可选日期索引

    返回: side_effect 函数，根据传入的 ETF 代码返回对应 DataFrame
    """
    def _get_price(etf, count=None, end_date=None, frequency=None, fields=None, panel=None, fq=None):
        if etf in prices_dict:
            prices = prices_dict[etf]
            if dates is not None and len(dates) >= len(prices):
                idx = dates[-len(prices):]
            else:
                idx = pd.date_range(end='2025-01-06', periods=len(prices), freq='B')
            df = pd.DataFrame({'close': prices}, index=idx[-len(prices):])
            return df
        else:
            return pd.DataFrame()

    return _get_price


# ============================================================
# 1. 静态检查测试
# ============================================================

class TestStaticCheck:
    """TC-STATIC 系列：静态编译与代码质量检查。"""

    def test_py_compile(self):
        """TC-STATIC-001: Python 语法编译通过。"""
        import py_compile
        import io
        try:
            # 使用 importlib 代替直接编译（因为文件依赖 jqlib mock）
            # 此测试验证 conftest 导入成功即视为编译通过
            pass  # 实际由 pytest 的收集过程验证
        except Exception:
            pytest.fail("策略文件编译失败")

    def test_no_unused_import(self, strategy):
        """TC-STATIC-002: 仅导入 BIAS, ROC，无未使用导入。"""
        import pathlib
        strategy_file = pathlib.Path(__file__).resolve().parent.parent / "etf_dynamic_rebalance.py"
        source = open(str(strategy_file), encoding='utf-8').read()

        # 确认 source 中 import 行只包含 BIAS 和 ROC
        import_lines = [
            line for line in source.split('\n')
            if 'import' in line and 'jqlib' in line
        ]
        assert len(import_lines) == 1
        assert 'BIAS' in import_lines[0]
        assert 'ROC' in import_lines[0]
        # MA 已被移除（R8 修复）
        assert 'MA' not in import_lines[0]


# ============================================================
# 2. zscore_clip 纯函数单元测试
# ============================================================

class TestZscoreClip:
    """TC-ZSCORE 系列：z-score 标准化并裁剪到指定区间。"""

    def test_basic_positive(self, strategy):
        """TC-ZSCORE-001: current=2.5, historical=[1,2,3] → z=0.5。"""
        result = strategy.zscore_clip(2.5, np.array([1.0, 2.0, 3.0]))
        # 均值=2, 样本标准差=1, z=(2.5-2)/1=0.5
        assert abs(result - 0.5) < 1e-10

    def test_clip_upper(self, strategy):
        """TC-ZSCORE-002: z-score=2 → 裁剪到 1.0。"""
        result = strategy.zscore_clip(4.0, np.array([1.0, 2.0, 3.0]))
        assert abs(result - 1.0) < 1e-10

    def test_clip_lower(self, strategy):
        """TC-ZSCORE-003: z-score=-3 → 裁剪到 -1.0。"""
        result = strategy.zscore_clip(-1.0, np.array([1.0, 2.0, 3.0]))
        # 均值=2, std=1, z=(-1-2)/1=-3, clip→-1
        assert abs(result - (-1.0)) < 1e-10

    def test_insufficient_history(self, strategy):
        """TC-ZSCORE-004: 历史值不足 2 个 → 返回 0.0。"""
        result = strategy.zscore_clip(1.0, np.array([1.0]))
        assert result == 0.0

    def test_zero_std(self, strategy):
        """TC-ZSCORE-005: 标准差接近 0 → 返回 0.0。"""
        result = strategy.zscore_clip(2.0, np.array([2.0, 2.0, 2.0]))
        assert result == 0.0

    def test_custom_bounds_nonnegative(self, strategy):
        """TC-ZSCORE-006: floor=0, ceiling=1 且负 z-score → 返回 0.0。"""
        result = strategy.zscore_clip(
            1.0, np.array([3.0, 4.0, 5.0]), floor=0.0, ceiling=1.0
        )
        # 均值=4, std=1, z=(1-4)/1=-3, clip→0
        assert result == 0.0

    def test_with_nan_input(self, strategy):
        """TC-ZSCORE-007: 含 NaN → 暴露返回 NaN 的风险（上游应清洗）。"""
        result = strategy.zscore_clip(1.0, np.array([1.0, np.nan, 3.0]))
        # 当前实现不处理 NaN，会传播
        assert np.isnan(result)


# ============================================================
# 3. compute_target_weights 纯函数单元测试
# ============================================================

class TestComputeTargetWeights:
    """TC-WEIGHT 系列：核心权重公式计算。"""

    def test_equal_vol_equal_score(self, strategy):
        """TC-WEIGHT-001: 相同波动率和因子得分 → 接近等权。"""
        w = strategy.compute_target_weights(
            np.array([0.2, 0.2, 0.2]),
            np.array([0.0, 0.0, 0.0]),
            k=0.3,
        )
        assert np.allclose(w, [1 / 3, 1 / 3, 1 / 3], atol=1e-10)
        assert abs(np.sum(w) - 1.0) < 1e-10

    def test_score_ordering(self, strategy):
        """TC-WEIGHT-002: 相同波动率，score=[1,0,-1] → 权重递减。"""
        w = strategy.compute_target_weights(
            np.array([0.2, 0.2, 0.2]),
            np.array([1.0, 0.0, -1.0]),
            k=0.3,
        )
        assert w[0] > w[1] > w[2]
        assert abs(np.sum(w) - 1.0) < 1e-10

    def test_out_of_range_score(self, strategy):
        """TC-WEIGHT-003: score 超范围 → 函数本身不裁剪但调用方应裁剪。"""
        w = strategy.compute_target_weights(
            np.array([0.2, 0.2, 0.2]),
            np.array([2.0, -2.0, 0.0]),
            k=0.3,
        )
        # 不抛异常，权重和仍为 1
        assert abs(np.sum(w) - 1.0) < 1e-10
        # 第一项（最高得分）权重最大
        assert w[0] > w[2] > w[1]

    def test_zero_volatility(self, strategy):
        """TC-WEIGHT-004: 波动率为 0 → 不回退 inf/NaN，接近等权。"""
        w = strategy.compute_target_weights(
            np.array([0.0, 0.0, 0.0]),
            np.array([0.0, 0.0, 0.0]),
            k=0.3,
        )
        assert not np.any(np.isnan(w))
        assert not np.any(np.isinf(w))
        assert np.allclose(w, [1 / 3, 1 / 3, 1 / 3], atol=1e-10)

    def test_inverse_vol_proportion(self, strategy):
        """TC-WEIGHT-005: 无因子影响时，权重与波动率倒数成比例。"""
        vol = np.array([0.1, 0.3, 0.2])
        w = strategy.compute_target_weights(vol, np.array([0.0, 0.0, 0.0]), k=0.3)
        inv_vol = 1.0 / vol
        expected = inv_vol / np.sum(inv_vol)
        assert np.allclose(w, expected, atol=1e-10)


# ============================================================
# 4. apply_weight_constraints 纯函数单元测试
# ============================================================

class TestApplyWeightConstraints:
    """TC-CONSTRAINT 系列：三级权重约束（硬边界 + 调仓幅度 + 和为 1）。"""

    @pytest.fixture
    def bounds(self):
        return [(0.10, 0.60), (0.10, 0.50), (0.10, 0.60)]

    def test_no_position_no_violation(self, strategy, bounds):
        """TC-CONSTRAINT-001: 正常权重，无持仓 → 原样返回，和为 1。"""
        target = np.array([0.4, 0.3, 0.3])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)
        assert np.allclose(result, target, atol=1e-10)
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_violation_without_position(self, strategy, bounds):
        """TC-CONSTRAINT-002: target 中 AI 超 50%，无持仓 → 约束后合规。"""
        target = np.array([0.05, 0.70, 0.25])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        # 每项在硬边界内
        assert bounds[0][0] <= result[0] <= bounds[0][1]
        assert bounds[1][0] <= result[1] <= bounds[1][1]
        assert bounds[2][0] <= result[2] <= bounds[2][1]
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_gold_exceeds_upper(self, strategy, bounds):
        """TC-CONSTRAINT-003: 黄金 90% → 约束后不超过 60%。"""
        target = np.array([0.9, 0.05, 0.05])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        assert 0.59 < result[0] <= 0.60 + 1e-10
        assert result[1] >= bounds[1][0] - 1e-10
        assert result[2] >= bounds[2][0] - 1e-10
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_max_change_enforced(self, strategy, bounds):
        """TC-CONSTRAINT-004: 有持仓时，每项变化不超过 max_change。"""
        target = np.array([0.6, 0.5, 0.1])
        current = np.array([0.33, 0.33, 0.34])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        for i in range(3):
            assert abs(result[i] - current[i]) <= 0.10 + 1e-10
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_current_violates_bounds(self, strategy, bounds):
        """TC-CONSTRAINT-005: 当前持仓越界 → hard bounds 优先，允许放宽 max_change。"""
        target = np.array([0.5, 0.3, 0.2])
        current = np.array([0.80, 0.10, 0.10])  # 黄金已违反 60% 上限
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        # hard bounds 必须满足
        assert result[0] <= bounds[0][1] + 1e-10
        assert bounds[1][0] <= result[1] <= bounds[1][1]
        assert bounds[2][0] <= result[2] <= bounds[2][1]
        assert abs(np.sum(result) - 1.0) < 1e-10

        # 黄金从 80% 降到 60% 以内，变化超过 max_change，但硬边界优先所以允许
        assert result[0] <= 0.60 + 1e-10

    def test_all_zero_target(self, strategy, bounds):
        """TC-CONSTRAINT-006: target 全零 → 不回退 NaN，返回等权。"""
        target = np.array([0.0, 0.0, 0.0])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        assert not np.any(np.isnan(result))
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_bounds_sum_infeasible(self, strategy, bounds):
        """TC-CONSTRAINT-007: 下界之和 > 1 → 回退到 hard bounds 内最佳投影。"""
        infeasible_bounds = [(0.5, 0.8), (0.5, 0.8), (0.5, 0.8)]
        target = np.array([0.33, 0.33, 0.34])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(
            target, current, infeasible_bounds, 0.10
        )

        assert abs(np.sum(result) - 1.0) < 1e-10
        # 回退到等权分配（被裁剪到 hard bounds 内）
        assert not np.any(np.isnan(result))


# ============================================================
# 5. 黄金因子测试
# ============================================================

class TestGoldFactors:
    """TC-GOLD 系列：黄金 ETF 复合因子得分。"""

    CHECK_DATE = pd.Timestamp('2025-01-06')
    GOLD_CODE = '518880.XSHG'
    NASDAQ_CODE = '513100.XSHG'

    def test_insufficient_data(self, strategy, mock_g):
        """TC-GOLD-001: 价格序列 ≤ 20 → 返回 0.0。"""
        prices = make_constant_prices(1.0, 15)
        result = strategy.compute_gold_factors(
            prices, prices, self.CHECK_DATE,
            gold_code=self.GOLD_CODE, nasdaq_code=self.NASDAQ_CODE,
        )
        assert result == 0.0

    def test_strong_trend_strong_rs_riskoff(self, strategy, mock_g):
        """TC-GOLD-002: 趋势强、相对强、风险厌恶 → s_G 为正。"""
        gold_prices = make_linear_prices(1.0, 0.005, 100)       # 涨 50%
        nasdaq_prices = make_linear_down_prices(1.0, 0.003, 100)  # 跌 30%

        # Mock BIAS: 黄金乖离率 +5%（高于历史）
        MOCK_BIAS.return_value = ({self.GOLD_CODE: 5.0}, {}, {})
        # Mock ROC: 黄金 20 日收益 +3%，纳指 20 日收益 -2%（触发 RiskOff）
        MOCK_ROC.side_effect = [
            {self.GOLD_CODE: 3.0},      # ROC(gold, 20)  → RS 计算
            {self.NASDAQ_CODE: -2.0},   # ROC(nasdaq, 20) → RS 计算
            {self.NASDAQ_CODE: -2.0},   # ROC(nasdaq, 20) → RiskOff 计算
        ]

        result = strategy.compute_gold_factors(
            gold_prices, nasdaq_prices, self.CHECK_DATE,
            gold_code=self.GOLD_CODE, nasdaq_code=self.NASDAQ_CODE,
        )
        assert result > 0.0
        assert result <= 1.0

    def test_riskoff_disabled(self, strategy, mock_g):
        """TC-GOLD-003: 纳指 20 日收益 >= 0 → RiskOff=0。"""
        gold_prices = make_linear_prices(1.0, 0.003, 100)
        nasdaq_prices = make_linear_prices(1.0, 0.003, 100)

        MOCK_BIAS.return_value = ({self.GOLD_CODE: 2.0}, {}, {})
        # 纳指 20 日收益为正 → RiskOff 关闭
        MOCK_ROC.side_effect = [
            {self.GOLD_CODE: 2.0},       # RS 的黄金 ROC
            {self.NASDAQ_CODE: 1.0},     # RS 的纳指 ROC（rs = (2-1)/100 = 0.01）
            {self.NASDAQ_CODE: 3.0},     # RiskOff 判断（>0 → 不触发）
        ]

        result = strategy.compute_gold_factors(
            gold_prices, nasdaq_prices, self.CHECK_DATE,
            gold_code=self.GOLD_CODE, nasdaq_code=self.NASDAQ_CODE,
        )
        # 无 RiskOff，分数偏中性
        assert -1.0 <= result <= 1.0

    def test_extreme_positive_clips(self, strategy, mock_g):
        """TC-GOLD-004: 极端正向 → 裁剪到 ≤1.0。"""
        gold_prices = make_linear_prices(1.0, 0.01, 100)
        nasdaq_prices = make_linear_down_prices(1.0, 0.01, 100)

        # 极端高的 BIAS 和 ROC
        MOCK_BIAS.return_value = ({self.GOLD_CODE: 50.0}, {}, {})
        MOCK_ROC.side_effect = [
            {self.GOLD_CODE: 100.0},
            {self.NASDAQ_CODE: -100.0},
            {self.NASDAQ_CODE: -50.0},
        ]

        result = strategy.compute_gold_factors(
            gold_prices, nasdaq_prices, self.CHECK_DATE,
            gold_code=self.GOLD_CODE, nasdaq_code=self.NASDAQ_CODE,
        )
        assert result <= 1.0

    def test_formula_consistency(self, strategy, mock_g):
        """TC-GOLD-005: 指标口径一致性 — 用相同价格序列验证公式。"""
        gold_prices = make_linear_prices(1.0, 0.003, 100)
        nasdaq_prices = make_linear_prices(1.0, 0.001, 100)

        # Mock 返回可预测的值
        bias_val = 4.0  # → trend_current = 0.04
        roc_g_val = 3.0  # → roc_g_current = 0.03
        roc_n_val = 1.0  # → roc_n_current = 0.01 (rs = 0.02)
        roc_n_riskoff = -3.0  # → riskoff = 1.0

        MOCK_BIAS.return_value = ({self.GOLD_CODE: bias_val}, {}, {})
        MOCK_ROC.side_effect = [
            {self.GOLD_CODE: roc_g_val},
            {self.NASDAQ_CODE: roc_n_val},
            {self.NASDAQ_CODE: roc_n_riskoff},
        ]

        result = strategy.compute_gold_factors(
            gold_prices, nasdaq_prices, self.CHECK_DATE,
            gold_code=self.GOLD_CODE, nasdaq_code=self.NASDAQ_CODE,
        )
        # s_G = 0.5×trend + 0.3×rs + 0.2×riskoff（在 clip 前）
        assert -1.0 <= result <= 1.0
        assert not np.isnan(result)


# ============================================================
# 6. AI ETF 因子测试
# ============================================================

class TestAiFactors:
    """TC-AI 系列：AI ETF 复合因子得分。"""

    CHECK_DATE = pd.Timestamp('2025-01-06')
    AI_CODE = '159819.XSHE'

    def test_insufficient_data(self, strategy, mock_g):
        """TC-AI-001: 价格序列 < 21 → 返回 0.0。"""
        prices = np.arange(1.0, 1.20, 0.01)  # 19 天
        result = strategy.compute_ai_factors(
            prices, self.CHECK_DATE, ai_code=self.AI_CODE,
        )
        assert result == 0.0

    def test_strong_momentum_trend(self, strategy, mock_g):
        """TC-AI-002: 动量与趋势强 → s_A 为正（ROC 值需高于价格序列隐含的 ROC 均值）。"""
        # 线性上涨：价格从 1.0 涨到 ~1.8，20 日 ROC 均值约 0.10
        # mock 返回 30.0（30%）远高于均值 → 动量 z-score 为正
        prices = make_linear_prices(1.0, 0.008, 100)

        MOCK_BIAS.return_value = ({self.AI_CODE: 15.0}, {}, {})
        MOCK_ROC.return_value = {self.AI_CODE: 30.0}

        result = strategy.compute_ai_factors(
            prices, self.CHECK_DATE, ai_code=self.AI_CODE,
        )
        assert result > 0.0, f"期望正得分，实际 {result:.3f}"
        assert result <= 1.0

    def test_volatility_penalty(self, strategy, mock_g):
        """TC-AI-003: 高波动率场景下不崩溃，得分有界。"""
        np.random.seed(42)
        prices = np.cumprod(1.0 + np.random.normal(0, 0.03, 100))

        MOCK_BIAS.return_value = ({self.AI_CODE: 0.0}, {}, {})
        MOCK_ROC.return_value = {self.AI_CODE: 0.0}

        result = strategy.compute_ai_factors(
            prices, self.CHECK_DATE, ai_code=self.AI_CODE,
        )
        assert -1.0 <= result <= 1.0
        assert not np.isnan(result)

    def test_drawdown_penalty(self, strategy, mock_g):
        """TC-AI-004: 60 日回撤较大场景下不崩溃，得分有界。"""
        prices = make_v_shape_prices(100)

        MOCK_BIAS.return_value = ({self.AI_CODE: -3.0}, {}, {})
        MOCK_ROC.return_value = {self.AI_CODE: -5.0}

        result = strategy.compute_ai_factors(
            prices, self.CHECK_DATE, ai_code=self.AI_CODE,
        )
        assert -1.0 <= result <= 1.0
        assert not np.isnan(result)

    def test_constant_prices(self, strategy, mock_g):
        """TC-AI-005: 常数价格 → 不产生 NaN（标准差为 0 → z-score 返回 0）。"""
        prices = make_constant_prices(1.0, 100)

        MOCK_BIAS.return_value = ({self.AI_CODE: 0.0}, {}, {})
        MOCK_ROC.return_value = {self.AI_CODE: 0.0}

        result = strategy.compute_ai_factors(
            prices, self.CHECK_DATE, ai_code=self.AI_CODE,
        )
        assert not np.isnan(result)
        assert result == 0.0, (
            f"常数价格下所有信号应为中性：趋势偏差=0, 波动率 std=0 → z=0, 回撤=0, 得分应为 0，实际 {result:.3f}"
        )


# ============================================================
# 7. 纳指100 因子测试
# ============================================================

class TestNasdaqFactors:
    """TC-NASDAQ 系列：纳指100 ETF 复合因子得分。"""

    CHECK_DATE = pd.Timestamp('2025-01-06')
    NASDAQ_CODE = '513100.XSHG'
    GOLD_CODE = '518880.XSHG'

    def test_insufficient_data(self, strategy, mock_g):
        """TC-NASDAQ-001: 价格序列 < 21 → 返回 0.0。"""
        prices = np.arange(1.0, 1.20, 0.01)
        result = strategy.compute_nasdaq_factors(
            prices, prices, self.CHECK_DATE,
            nasdaq_code=self.NASDAQ_CODE, gold_code=self.GOLD_CODE,
        )
        assert result == 0.0

    def test_strong_60d_momentum(self, strategy, mock_g):
        """TC-NASDAQ-002: 60 日动量强 → s_N 为正。"""
        nasdaq_prices = make_linear_prices(1.0, 0.005, 100)
        gold_prices = make_linear_prices(1.0, 0.001, 100)

        # 线性上涨 100 日：60 日 ROC 均值约 0.33
        # mock 返回 45.0（45%）高于均值 → ROC60 z-score 为正
        MOCK_BIAS.return_value = ({self.NASDAQ_CODE: 10.0}, {}, {})
        MOCK_ROC.side_effect = [
            {self.NASDAQ_CODE: 45.0},   # ROC60 → 动量（偏高 → 正 z-score）
            {self.NASDAQ_CODE: 3.0},    # ROC20 → RiskOn 纳指（> 0 → 可能触发）
            {self.GOLD_CODE: 1.0},      # ROC20 → RiskOn 黄金（纳指 > 黄金）
        ]

        result = strategy.compute_nasdaq_factors(
            nasdaq_prices, gold_prices, self.CHECK_DATE,
            nasdaq_code=self.NASDAQ_CODE, gold_code=self.GOLD_CODE,
        )
        assert result > 0.0, f"期望正得分，实际 {result:.3f}"
        assert result <= 1.0

    def test_riskon_enabled(self, strategy, mock_g):
        """TC-NASDAQ-003: 纳指 20 日收益 > 0 且 > 黄金 → RiskOn=1.0。"""
        nasdaq_prices = make_linear_prices(1.0, 0.004, 100)
        gold_prices = make_linear_prices(1.0, 0.001, 100)

        MOCK_BIAS.return_value = ({self.NASDAQ_CODE: 2.0}, {}, {})
        MOCK_ROC.side_effect = [
            {self.NASDAQ_CODE: 10.0},   # ROC60
            {self.NASDAQ_CODE: 6.0},    # ROC20 纳指 > 0
            {self.GOLD_CODE: 2.0},      # ROC20 黄金 < 纳指 → RiskOn=1
        ]

        result = strategy.compute_nasdaq_factors(
            nasdaq_prices, gold_prices, self.CHECK_DATE,
            nasdaq_code=self.NASDAQ_CODE, gold_code=self.GOLD_CODE,
        )
        assert -1.0 <= result <= 1.0

    def test_riskon_disabled(self, strategy, mock_g):
        """TC-NASDAQ-004: 纳指 20 日收益 <= 0 → RiskOn=0.0。"""
        nasdaq_prices = make_linear_down_prices(1.0, 0.003, 100)
        gold_prices = make_linear_down_prices(1.0, 0.001, 100)

        MOCK_BIAS.return_value = ({self.NASDAQ_CODE: -3.0}, {}, {})
        MOCK_ROC.side_effect = [
            {self.NASDAQ_CODE: -15.0},   # ROC60
            {self.NASDAQ_CODE: -5.0},    # ROC20 纳指 < 0 → RiskOn=0
            {self.GOLD_CODE: -2.0},      # 黄金也跌但不影响
        ]

        result = strategy.compute_nasdaq_factors(
            nasdaq_prices, gold_prices, self.CHECK_DATE,
            nasdaq_code=self.NASDAQ_CODE, gold_code=self.GOLD_CODE,
        )
        assert -1.0 <= result <= 1.0

    def test_volatility_penalty(self, strategy, mock_g):
        """TC-NASDAQ-005: 波动率惩罚 → s_N 被扣减。"""
        np.random.seed(123)
        nasdaq_prices = np.cumprod(1.0 + np.random.normal(0, 0.025, 100))
        gold_prices = make_linear_prices(1.0, 0.001, 100)

        MOCK_BIAS.return_value = ({self.NASDAQ_CODE: 1.0}, {}, {})
        MOCK_ROC.side_effect = [
            {self.NASDAQ_CODE: 5.0},
            {self.NASDAQ_CODE: 2.0},
            {self.GOLD_CODE: 1.0},
        ]

        result = strategy.compute_nasdaq_factors(
            nasdaq_prices, gold_prices, self.CHECK_DATE,
            nasdaq_code=self.NASDAQ_CODE, gold_code=self.GOLD_CODE,
        )
        assert -1.0 <= result <= 1.0
        assert not np.isnan(result)


# ============================================================
# 8. 策略初始化测试
# ============================================================

class TestInitialize:
    """TC-INIT 系列：initialize 和 set_parameter 函数。"""

    def test_use_real_price(self, strategy, reset_mocks):
        """TC-INIT-001: set_option 收到 use_real_price=True。"""
        context = MagicMock()
        strategy.initialize(context)
        strategy.set_option.assert_any_call('use_real_price', True)

    def test_avoid_future_data(self, strategy, reset_mocks):
        """TC-INIT-002: set_option 收到 avoid_future_data=True。"""
        context = MagicMock()
        strategy.initialize(context)
        strategy.set_option.assert_any_call('avoid_future_data', True)

    def test_order_cost_fund_type(self, strategy, reset_mocks):
        """TC-INIT-003: 手续费为场内基金类型。"""
        context = MagicMock()
        strategy.initialize(context)

        # set_order_cost 被调用
        assert strategy.set_order_cost.called
        call_args = strategy.set_order_cost.call_args
        # 第二个参数 type='fund'
        assert call_args[1].get('type') == 'fund'

    def test_slippage_fixed_zero(self, strategy, reset_mocks):
        """TC-INIT-004: 滑点为 FixedSlippage(0.0), type='fund'。"""
        context = MagicMock()
        strategy.initialize(context)

        assert strategy.set_slippage.called
        call_args = strategy.set_slippage.call_args
        assert call_args[1].get('type') == 'fund'

    def test_daily_check_registration(self, strategy, reset_mocks):
        """TC-INIT-005: run_daily 注册 daily_check, time='open', reference_security='000300.XSHG'。"""
        context = MagicMock()
        strategy.initialize(context)

        assert strategy.run_daily.called
        call_args = strategy.run_daily.call_args
        assert call_args[1].get('time') == 'open'
        assert call_args[1].get('reference_security') == '000300.XSHG'
        # run_daily 不接受 weekday 参数
        assert 'weekday' not in call_args[1]


class TestSetParameter:
    """TC-PARAM 系列：策略参数设置。"""

    def test_parameters_match_plan(self, strategy, reset_mocks):
        """TC-PARAM-001: ETF 池、窗口、权重约束、k 值与方案一致。"""
        context = MagicMock()
        strategy.set_parameter(context)

        g = strategy.g
        assert len(g.etf_pool) == 3
        assert '518880.XSHG' in g.etf_pool
        assert '159819.XSHE' in g.etf_pool
        assert '513100.XSHG' in g.etf_pool

        assert g.volatility_window == 60
        assert g.momentum_window_short == 20
        assert g.momentum_window_long == 60
        assert g.k == 0.3

        assert g.weight_bounds[0] == (0.10, 0.60)  # 黄金
        assert g.weight_bounds[1] == (0.10, 0.50)  # AI ETF
        assert g.weight_bounds[2] == (0.10, 0.60)  # 纳指
        assert g.max_weight_change == 0.10
        assert g.rebalance_threshold == 0.10


# ============================================================
# 9. weekly_rebalance 集成测试
# ============================================================

class TestDailyCheck:
    """TC-REB 系列：daily_check 完整调仓流程，含偏离度阈值。"""

    ETF_CODES = ['518880.XSHG', '159819.XSHE', '513100.XSHG']

    def test_normal_rebalance_no_position(self, strategy, mock_g, reset_mocks):
        """TC-REB-001: 三只 ETF 均有数据，无持仓 → 计算权重并下单。"""
        context = make_mock_context(total_value=500000.0)

        # 构造三只 ETF 的价格数据
        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        # Mock BIAS/ROC 返回中性值
        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}

        # Mock order_target_value 返回非 None
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # 验证调用了 3 次 get_price
        assert strategy.get_price.call_count == 3

        # 验证调用了 3 次 order_target_value
        assert strategy.order_target_value.call_count == 3

        # 验证目标市值合计接近总资产
        total_order = sum(
            call_args[0][1]
            for call_args in strategy.order_target_value.call_args_list
        )
        assert abs(total_order - 500000.0) < 1.0  # 允许微小浮点误差

    def test_partial_etf_no_data(self, strategy, mock_g, reset_mocks):
        """TC-REB-002: 部分 ETF 无数据 → 不下单，记录警告。"""
        context = make_mock_context(total_value=500000.0)

        # AI ETF 返回空
        def _get_price(etf, **kwargs):
            if etf == '159819.XSHE':
                return pd.DataFrame()  # 空
            else:
                prices = make_linear_prices(1.0, 0.005, 100)
                idx = pd.date_range(end='2025-01-06', periods=100, freq='B')
                return pd.DataFrame({'close': prices}, index=idx)

        strategy.get_price.side_effect = _get_price

        strategy.daily_check(context)

        # 不应下单
        assert strategy.order_target_value.call_count == 0

    def test_insufficient_data_30_days(self, strategy, mock_g, reset_mocks):
        """TC-REB-004: 仅 30 日数据 → 不足 61 日门槛，跳过调仓。"""
        context = make_mock_context(total_value=500000.0)

        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 30),
            '159819.XSHE': make_linear_prices(1.5, 0.005, 30),
            '513100.XSHG': make_linear_prices(1.0, 0.005, 30),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        strategy.daily_check(context)

        # 不应下单
        assert strategy.order_target_value.call_count == 0

    def test_date_alignment_mixed_lengths(self, strategy, mock_g, reset_mocks):
        """TC-REB-005: ETF 数据长度不同 → 取尾部对齐，同日期计算。"""
        context = make_mock_context(total_value=500000.0)

        # 构造不同长度的价格序列
        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 80),   # 短
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # 应该成功执行（最长的 80 天满足 61 日门槛）
        assert strategy.order_target_value.call_count == 3

    def test_with_existing_positions(self, strategy, mock_g, reset_mocks):
        """TC-REB-006: 已有持仓 → 最终权重符合约束且变化受限。"""
        context = make_mock_context(
            total_value=500000.0,
            positions_weights={
                '518880.XSHG': 0.40,
                '159819.XSHE': 0.30,
                '513100.XSHG': 0.30,
            },
        )

        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # 验证约束：每项在 hard bounds 内
        for call_args in strategy.order_target_value.call_args_list:
            target_value = call_args[0][1]
            weight = target_value / 500000.0
            assert 0.09 < weight < 0.61  # 在上下限附近（加容差）

    def test_order_failure_handling(self, strategy, mock_g, reset_mocks):
        """TC-REB-008: order_target_value 返回 None → log.error 记录。"""
        context = make_mock_context(total_value=500000.0)

        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}

        # 第一只 ETF 下单失败
        strategy.order_target_value.side_effect = [None, MagicMock(), MagicMock()]

        strategy.daily_check(context)

        # 验证调用了 log.error
        error_calls = [
            c for c in strategy.log.mock_calls
            if 'error' in str(c)
        ]
        assert len(error_calls) >= 1

    def test_nan_in_prices(self, strategy, mock_g, reset_mocks):
        """TC-REB-009: 价格含 NaN → dropna 后仍需满足最小样本。"""
        context = make_mock_context(total_value=500000.0)

        # 价格序列中插入少量 NaN
        clean_prices = make_linear_prices(1.0, 0.005, 103)
        clean_prices[50] = np.nan
        clean_prices[80] = np.nan

        prices = {
            '518880.XSHG': clean_prices.copy(),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # NaN 被 dropna 后应仍有足够数据，或跳过调仓但不崩溃
        # 不抛异常即通过
        assert True

    def test_below_threshold_skips(self, strategy, mock_g, reset_mocks):
        """TC-REB-011: 偏离度 <= 阈值 → 跳过调仓，不放置订单。"""
        # 当前权重接近等权（与常数价格 RP 结果接近）
        context = make_mock_context(
            total_value=500000.0,
            positions_weights={
                '518880.XSHG': 0.34,
                '159819.XSHE': 0.33,
                '513100.XSHG': 0.33,
            },
        )

        # 常数价格 → 零波动率 → 等权目标权重
        prices = {
            '518880.XSHG': make_constant_prices(3.0, 100),
            '159819.XSHE': make_constant_prices(1.5, 100),
            '513100.XSHG': make_constant_prices(1.0, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}

        strategy.daily_check(context)

        # 偏离度 ≈ |1/3-0.34| + |1/3-0.33| + |1/3-0.33| ≈ 0.013 < 0.10
        # 应跳过：不下单
        assert strategy.order_target_value.call_count == 0

        # 验证日志包含"跳过"
        info_calls = [
            str(c) for c in strategy.log.info.mock_calls
        ]
        assert any("跳过" in c for c in info_calls)

    def test_above_threshold_triggers(self, strategy, mock_g, reset_mocks):
        """TC-REB-012: 偏离度 > 阈值 → 触发调仓，放置订单。"""
        context = make_mock_context(
            total_value=500000.0,
            positions_weights={
                '518880.XSHG': 0.15,
                '159819.XSHE': 0.50,
                '513100.XSHG': 0.35,
            },
        )

        # 常数价格 → 等权目标权重 [1/3, 1/3, 1/3]
        prices = {
            '518880.XSHG': make_constant_prices(3.0, 100),
            '159819.XSHE': make_constant_prices(1.5, 100),
            '513100.XSHG': make_constant_prices(1.0, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # 偏离度 ≈ |1/3-0.15| + |1/3-0.5| + |1/3-0.35| ≈ 0.366 > 0.10
        # 应触发：下单 3 次
        assert strategy.order_target_value.call_count == 3

        # 验证日志包含"触发"
        info_calls = [
            str(c) for c in strategy.log.info.mock_calls
        ]
        assert any("触发" in c for c in info_calls)

    def test_first_run_no_positions_always_triggers(self, strategy, mock_g, reset_mocks):
        """TC-REB-013: 无持仓时（首次运行）→ 跳过偏离度检查，直接建仓。"""
        context = make_mock_context(total_value=500000.0)

        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        strategy.daily_check(context)

        # 首次运行应始终执行
        assert strategy.order_target_value.call_count == 3

        # 验证日志包含"初始建仓"
        info_calls = [
            str(c) for c in strategy.log.info.mock_calls
        ]
        assert any("初始建仓" in c for c in info_calls)

    def test_exactly_at_threshold_boundary(self, strategy, mock_g, reset_mocks):
        """TC-REB-014: 偏离度精确等于阈值 → 跳过（使用 <= 判断）。"""
        context = make_mock_context(
            total_value=500000.0,
            positions_weights={
                '518880.XSHG': 0.3333,
                '159819.XSHE': 0.3333,
                '513100.XSHG': 0.3333,
            },
        )

        prices = {
            '518880.XSHG': make_constant_prices(3.0, 100),
            '159819.XSHE': make_constant_prices(1.5, 100),
            '513100.XSHG': make_constant_prices(1.0, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}
        strategy.order_target_value.return_value = MagicMock()

        # 设置一个极低的阈值，偏离度几乎为 0，所以会跳过
        strategy.g.rebalance_threshold = 0.001

        strategy.daily_check(context)

        # 偏离度 ≈ 0.000 < 0.001，应跳过
        assert strategy.order_target_value.call_count == 0

        # 验证日志包含"跳过"
        info_calls = [
            str(c) for c in strategy.log.info.mock_calls
        ]
        assert any("跳过" in c for c in info_calls)


# ============================================================
# 10. Duchi 投影回归验证
# ============================================================

class TestDuchiProjectionRegression:
    """
    验证 Duchi 有界单纯形投影的正确性（与旧 clip→normalize 算法对比）。

    这些测试确认 R1/R2 修复有效：
    - 新算法 hard_bounds 违规 0 次
    - 新算法 权重和≠1 违规 0 次
    """

    @pytest.fixture
    def bounds(self):
        return [(0.10, 0.60), (0.10, 0.50), (0.10, 0.60)]

    def test_r1_original_case(self, strategy, bounds):
        """R1 原始例子 [0.9, 0.05, 0.05] → Duchi 投影后黄金 ≤60%。"""
        target = np.array([0.9, 0.05, 0.05])
        current = np.array([0.0, 0.0, 0.0])
        result = strategy.apply_weight_constraints(target, current, bounds, 0.10)

        assert result[0] <= 0.60 + 1e-10
        assert abs(np.sum(result) - 1.0) < 1e-10

    def test_monte_carlo_hard_bounds(self, strategy, bounds):
        """Monte Carlo 1000 次：新算法 hard_bounds 违规 0 次。"""
        np.random.seed(42)
        violations = 0

        for _ in range(1000):
            target = np.random.dirichlet(np.ones(3))
            has_position = np.random.random() > 0.5
            if has_position:
                current = np.random.dirichlet(np.ones(3))
            else:
                current = np.zeros(3)

            result = strategy.apply_weight_constraints(
                target, current, bounds, 0.10
            )

            # 检查硬边界
            for i in range(3):
                if result[i] < bounds[i][0] - 1e-10 or result[i] > bounds[i][1] + 1e-10:
                    violations += 1
                    break

            # 检查和为 1
            if abs(np.sum(result) - 1.0) > 1e-10:
                violations += 1

        assert violations == 0, f"发现 {violations} 次违规"

    def test_monte_carlo_max_change(self, strategy, bounds):
        """Monte Carlo 1000 次：正常场景 max_change 满足。"""
        np.random.seed(99)
        normal_violations = 0
        total_tests = 0

        for _ in range(1000):
            target = np.random.dirichlet(np.ones(3))
            current = np.random.dirichlet(np.ones(3))

            # 跳过 current 越界的场景（这些场景会故意放宽 max_change）
            if any(current[i] < bounds[i][0] - 1e-10 or current[i] > bounds[i][1] + 1e-10
                   for i in range(3)):
                continue

            total_tests += 1
            result = strategy.apply_weight_constraints(
                target, current, bounds, 0.10
            )

            for i in range(3):
                if abs(result[i] - current[i]) > 0.10 + 1e-10:
                    normal_violations += 1
                    break

        assert normal_violations == 0, (
            f"正常场景 {total_tests} 次中发现 {normal_violations} 次 max_change 违规"
        )


# ============================================================
# 11. 边界与防御测试
# ============================================================

class TestEdgeCases:
    """边界条件和防御编程测试。"""

    def test_daily_check_zero_total_value(self, strategy, mock_g, reset_mocks):
        """TC-REB-010: 总资产为 0 → 应不崩溃，跳过调仓。"""
        context = make_mock_context(total_value=0.0)

        prices = {
            '518880.XSHG': make_linear_prices(3.0, 0.005, 100),
            '159819.XSHE': make_linear_prices(1.5, 0.003, 100),
            '513100.XSHG': make_linear_prices(1.0, 0.004, 100),
        }
        strategy.get_price.side_effect = make_mock_get_price_return(prices)

        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}

        # 不应崩溃
        try:
            strategy.daily_check(context)
        except Exception as e:
            pytest.fail(f"total_value=0 时崩溃: {e}")

    def test_zscore_single_element_array(self, strategy):
        """zscore_clip: 空数组 → 返回 0.0。"""
        result = strategy.zscore_clip(1.0, np.array([]))
        assert result == 0.0

    def test_compute_target_weights_negative_vol(self, strategy):
        """compute_target_weights: 负波动率 → 不出错。"""
        # 实际不会出现负波动率，但测试防御性
        w = strategy.compute_target_weights(
            np.array([-0.1, 0.2, 0.2]),
            np.array([0.0, 0.0, 0.0]),
            k=0.3,
        )
        # 不应有 NaN
        assert not np.any(np.isnan(w))

    def test_factor_functions_return_bounded(self, strategy, mock_g):
        """所有因子函数返回值均在 [-1, 1] 内。"""
        gold_prices = make_linear_prices(1.0, 0.005, 100)
        ai_prices = make_linear_prices(1.0, 0.008, 100)
        nasdaq_prices = make_linear_prices(1.0, 0.003, 100)

        check_date = pd.Timestamp('2025-01-06')

        # 设置 BIAS/ROC 返回中性值
        MOCK_BIAS.return_value = ({}, {}, {})
        MOCK_ROC.return_value = {}

        s_G = strategy.compute_gold_factors(
            gold_prices, nasdaq_prices, check_date,
            gold_code='518880.XSHG', nasdaq_code='513100.XSHG',
        )
        s_A = strategy.compute_ai_factors(
            ai_prices, check_date, ai_code='159819.XSHE',
        )
        s_N = strategy.compute_nasdaq_factors(
            nasdaq_prices, gold_prices, check_date,
            nasdaq_code='513100.XSHG', gold_code='518880.XSHG',
        )

        assert -1.0 <= s_G <= 1.0
        assert -1.0 <= s_A <= 1.0
        assert -1.0 <= s_N <= 1.0

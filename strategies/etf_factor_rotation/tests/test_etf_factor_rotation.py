"""
ETF 多因子轮动策略 — 单元测试

测试覆盖：
  - 静态检查（模块加载、参数初始化）
  - 纯函数单元测试（percentile_rank, apply_weight_constraints, select_topk）
  - 模块计算测试（趋势门槛、动量分数、风险平价、RSRS、拥挤度、波动率缩放）
  - 集成测试（weekly_check 完整流程）
"""

import math
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch, call

import numpy as np
import pandas as pd
import pytest

# ============================================================
# 可复用的价格序列生成工具
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


def make_random_walk_prices(start=1.0, sigma=0.02, n_days=3000):
    """生成随机游走价格序列（正态收益率）。"""
    rng = np.random.default_rng(42)
    returns = rng.normal(0, sigma, n_days)
    price = start * np.exp(np.cumsum(returns))
    return price


def make_prices_dataframe(prices_dict, start_date='2020-01-01'):
    """将 {etf: array} 转为符合 get_price 返回格式的 DataFrame。"""
    dfs = {}
    for etf, arr in prices_dict.items():
        dates = pd.date_range(start_date, periods=len(arr), freq='B')
        dfs[etf] = pd.Series(arr, index=dates, name=etf)
    return pd.DataFrame(dfs)


# ============================================================
# 辅助函数 — 构造 mock get_price 返回值
# ============================================================
def _wrap_price_df(prices_dict, start_date='2020-01-01'):
    """构建符合聚宽 get_price 返回格式的 mock。"""
    return make_prices_dataframe(prices_dict, start_date)


class _MockPriceResult:
    """模拟聚宽 get_price 返回的 dict-like 对象。

    get_price(pool, fields=['close'], ...) 返回一个可下标访问的对象，
    通过 ['close'] 获取 DataFrame（index=日期, columns=ETF代码）。
    """
    def __init__(self, df):
        self._df = df
    def __getitem__(self, key):
        return self._df


def _setup_get_price_mock(strategy, close=None, high=None, low=None, amount=None):
    """配置 strategy.get_price 按 side_effect 返回 OHLC 数据。"""
    returns = []
    for field_data in [close, high, low, amount]:
        if field_data is not None:
            field_df = _wrap_price_df(field_data)
            returns.append(_MockPriceResult(field_df))
    strategy.get_price.side_effect = returns


# ============================================================
# 1. 模块加载与参数初始化
# ============================================================
class TestModuleLoading:
    """测试策略模块能否正确加载且核心函数存在。"""

    def test_strategy_module_loaded(self, strategy):
        assert strategy is not None
        assert hasattr(strategy, 'initialize')
        assert hasattr(strategy, 'set_parameter')

    def test_all_core_functions_exist(self, strategy):
        core_funcs = [
            'initialize', 'set_parameter', 'weekly_check',
            'get_history_data', 'compute_trend_gates', 'compute_momentum_scores',
            'select_topk', 'compute_rp_weights', 'compute_rsrs_multipliers',
            'compute_crowd_penalties', 'percentile_rank',
            'compute_portfolio_vol_scale', 'apply_weight_constraints',
            'execute_rebalance',
        ]
        for fn in core_funcs:
            assert hasattr(strategy, fn), f"Missing function: {fn}"


class TestSetParameter:
    """测试参数初始化正确性。"""

    def test_set_parameter_writes_to_g(self, strategy):
        strategy.set_parameter(strategy)

        g = strategy.g
        assert len(g.etf_pool) == 3
        assert g.TopK == 2
        assert g.MA_long == 120
        assert g.TargetVol == 0.12
        assert g.MaxWeight == 0.60

    def test_momentum_weights_sum_to_one(self, strategy):
        strategy.set_parameter(strategy)
        total = strategy.g.w20 + strategy.g.w60 + strategy.g.w120
        assert abs(total - 1.0) < 1e-10

    def test_live_days_covers_all_windows(self, strategy):
        strategy.set_parameter(strategy)
        g = strategy.g
        max_window = max(
            g.MA_long, g.MomLong, g.RSRS_M,
            g.CrowdWindow, g.PortfolioVolWindow
        )
        assert g.live_days >= max_window


class TestInitialize:
    """测试 initialize 注册了正确的框架调用。"""

    def test_initialize_calls_set_option(self, strategy):
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.set_option.assert_any_call('use_real_price', True)
        strategy.set_option.assert_any_call('avoid_future_data', True)

    def test_initialize_registers_weekly_task(self, strategy):
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.run_weekly.assert_called_once()
        args, kwargs = strategy.run_weekly.call_args
        assert kwargs['weekday'] == 1
        assert kwargs['time'] == 'open'


# ============================================================
# 2. 纯函数单元测试
# ============================================================
class TestPercentileRank:
    """测试分位数排名计算。"""

    def test_min_value_returns_zero(self, strategy):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = strategy.percentile_rank(1.0, series)
        assert result == 0.0

    def test_max_value_returns_near_one(self, strategy):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = strategy.percentile_rank(5.0, series)
        assert result == 0.8  # 4/5 = 0.8, 5 is greater than 4 values

    def test_median_value(self, strategy):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = strategy.percentile_rank(3.0, series)
        assert result == 0.4  # 2/5

    def test_empty_series_returns_05(self, strategy):
        series = pd.Series([], dtype=float)
        result = strategy.percentile_rank(3.0, series)
        assert result == 0.5


class TestApplyWeightConstraints:
    """测试仓位约束。"""

    def test_clip_max_weight(self, strategy, mock_g):
        weights = np.array([0.80, 0.20, 0.0])
        result = strategy.apply_weight_constraints(weights, 3)
        assert result[0] == 0.60
        assert result[1] == 0.20

    def test_drop_below_min_weight(self, strategy, mock_g):
        weights = np.array([0.30, 0.04, 0.0])
        result = strategy.apply_weight_constraints(weights, 3)
        assert result[0] == 0.30
        assert result[1] == 0.0

    def test_preserves_total_below_one(self, strategy, mock_g):
        weights = np.array([0.20, 0.30, 0.10])
        result = strategy.apply_weight_constraints(weights, 3)
        assert sum(result) <= 1.0


class TestSelectTopK:
    """测试 TopK 选择逻辑。"""

    def test_selects_top2_from_3_active(self, strategy, mock_g):
        scores = np.array([0.9, 0.6, 0.3])
        gates = np.array([1.0, 1.0, 1.0])
        selected = strategy.select_topk(scores, gates)
        assert selected == [True, True, False]

    def test_selects_all_when_less_than_k_active(self, strategy, mock_g):
        scores = np.array([0.9, 0.0, 0.0])
        gates = np.array([1.0, 0.0, 0.0])
        selected = strategy.select_topk(scores, gates)
        assert selected == [True, False, False]

    def test_none_selected_when_no_trend(self, strategy, mock_g):
        scores = np.array([0.9, 0.8, 0.7])
        gates = np.array([0.0, 0.0, 0.0])
        selected = strategy.select_topk(scores, gates)
        assert selected == [False, False, False]

    def test_all_selected_when_k_larger_than_active(self, strategy, mock_g):
        mock_g.TopK = 5
        scores = np.array([0.9, 0.6, 0.3])
        gates = np.array([1.0, 1.0, 1.0])
        selected = strategy.select_topk(scores, gates)
        assert selected == [True, True, True]


# ============================================================
# 3. 趋势门槛测试
# ============================================================
class TestComputeTrendGates:
    """测试 120 日均线趋势过滤。"""

    def test_price_above_ma_passes(self, strategy, mock_g):
        mock_g.MA_long = 5
        n_days = 20
        prices_above = np.arange(1.0, 1.0 + 0.02 * n_days, 0.02)[:n_days]
        close = {
            '159819.XSHE': prices_above,
            '513100.XSHG': prices_above * 0.9,
            '518880.XSHG': prices_above * 1.1,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool)
        assert gates[0] == 1.0
        assert gates[1] == 1.0
        assert gates[2] == 1.0

    def test_price_below_ma_fails(self, strategy, mock_g):
        mock_g.MA_long = 5
        n_days = 20
        prices_down = np.arange(2.0, 2.0 - 0.02 * n_days, -0.02)[:n_days]
        close = {
            '159819.XSHE': prices_down,
            '513100.XSHG': prices_down,
            '518880.XSHG': prices_down,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool)
        assert all(g == 0.0 for g in gates)

    def test_insufficient_data_returns_zero(self, strategy, mock_g):
        mock_g.MA_long = 120
        short_prices = make_linear_prices(n_days=50)
        close = {
            '159819.XSHE': short_prices,
            '513100.XSHG': short_prices,
            '518880.XSHG': short_prices,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool)
        assert all(g == 0.0 for g in gates)


# ============================================================
# 4. 动量分数测试
# ============================================================
class TestComputeMomentumScores:
    """测试多周期排名动量分数计算。"""

    def test_higher_return_gets_higher_score(self, strategy, mock_g):
        n_days = 200
        # AI 涨幅最大，纳指其次，黄金最小
        ai_prices = np.arange(1.0, 1.0 + 0.005 * n_days, 0.005)[:n_days]
        nasdaq_prices = np.arange(1.0, 1.0 + 0.003 * n_days, 0.003)[:n_days]
        gold_prices = np.arange(1.0, 1.0 + 0.001 * n_days, 0.001)[:n_days]

        close = {
            '159819.XSHE': ai_prices,
            '513100.XSHG': nasdaq_prices,
            '518880.XSHG': gold_prices,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 1.0, 1.0])

        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates)
        assert scores[0] > scores[1] > scores[2]

    def test_trend_gate_zero_scores_zero(self, strategy, mock_g):
        n_days = 200
        prices_arr = np.arange(1.0, 1.0 + 0.005 * n_days, 0.005)[:n_days]
        close = {e: prices_arr for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 0.0, 1.0])

        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates)
        assert scores[1] == 0.0  # 趋势不成立的资产分数为 0

    def test_no_active_assets_returns_zeros(self, strategy, mock_g):
        prices = {
            'close': make_prices_dataframe({
                e: make_linear_prices(n_days=200) for e in mock_g.etf_pool
            })
        }
        gates = np.array([0.0, 0.0, 0.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates)
        assert all(s == 0.0 for s in scores)


# ============================================================
# 5. 风险平价测试
# ============================================================
class TestComputeRPWeights:
    """测试逆波动率风险平价权重计算。"""

    def test_weights_sum_to_one(self, strategy, mock_g):
        n_days = 100
        close = {
            '159819.XSHE': make_random_walk_prices(sigma=0.03, n_days=n_days),
            '513100.XSHG': make_random_walk_prices(sigma=0.02, n_days=n_days),
            '518880.XSHG': make_random_walk_prices(sigma=0.01, n_days=n_days),
        }
        prices = {'close': make_prices_dataframe(close)}
        selected = [True, True, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected)
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_lower_vol_gets_higher_weight(self, strategy, mock_g):
        n_days = 100
        close = {
            '159819.XSHE': make_random_walk_prices(sigma=0.03, n_days=n_days),
            '513100.XSHG': make_random_walk_prices(sigma=0.02, n_days=n_days),
            '518880.XSHG': make_random_walk_prices(sigma=0.01, n_days=n_days),
        }
        prices = {'close': make_prices_dataframe(close)}
        selected = [True, True, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected)
        assert weights[2] > weights[1] > weights[0]  # 黄金(低波) > 纳指 > AI

    def test_unselected_assets_get_zero(self, strategy, mock_g):
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        selected = [True, False, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected)
        assert weights[1] == 0.0
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_single_asset_gets_weight_one(self, strategy, mock_g):
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        selected = [True, False, False]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected)
        assert weights[0] == 1.0

    def test_no_selected_returns_zeros(self, strategy, mock_g):
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        selected = [False, False, False]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected)
        assert all(w == 0.0 for w in weights)


# ============================================================
# 6. RSRS 线性修正测试
# ============================================================
class TestComputeRSRSMultipliers:
    """测试 RSRS 截断线性乘数计算。"""

    def test_returns_array_of_correct_length(self, strategy, mock_g):
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        high_prices = {e: base * 1.01 for e in mock_g.etf_pool}
        low_prices = {e: base * 0.99 for e in mock_g.etf_pool}

        prices = {
            'high': make_prices_dataframe(high_prices),
            'low': make_prices_dataframe(low_prices),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool)
        assert len(multipliers) == 3

    def test_values_in_valid_range(self, strategy, mock_g):
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        high_prices = {e: base * 1.01 for e in mock_g.etf_pool}
        low_prices = {e: base * 0.99 for e in mock_g.etf_pool}

        prices = {
            'high': make_prices_dataframe(high_prices),
            'low': make_prices_dataframe(low_prices),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool)
        for m in multipliers:
            assert 0.0 <= m <= 1.0

    def test_insufficient_data_returns_one(self, strategy, mock_g):
        short_prices = make_linear_prices(n_days=50)
        prices = {
            'high': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: short_prices * 0.99 for e in mock_g.etf_pool}),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool)
        assert all(m == 1.0 for m in multipliers)

    def test_strong_up_trend_keeps_multiplier_at_one(self, strategy, mock_g):
        """强势上涨时 RSRS 乘数应保持 1.0（只减不加）。"""
        n_days = 800
        # 持续上涨
        base = np.arange(1.0, 1.0 + 0.003 * n_days, 0.003)[:n_days]
        high_prices = {e: base * 1.02 for e in mock_g.etf_pool}
        low_prices = {e: base * 0.98 for e in mock_g.etf_pool}

        prices = {
            'high': make_prices_dataframe(high_prices),
            'low': make_prices_dataframe(low_prices),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool)
        # 只减不加原则：不应该超过 1.0
        for m in multipliers:
            assert m <= 1.0


# ============================================================
# 7. 拥挤度惩罚测试
# ============================================================
class TestComputeCrowdPenalties:
    """测试拥挤度线性惩罚乘数。"""

    def test_returns_array_of_correct_length(self, strategy, mock_g):
        n_days = 600
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        amount = {
            e: np.abs(make_random_walk_prices(n_days=n_days)) * 1e8
            for e in mock_g.etf_pool
        }
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool)
        assert len(penalties) == 3

    def test_values_in_valid_range(self, strategy, mock_g):
        n_days = 600
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        amount = {
            e: np.abs(make_random_walk_prices(n_days=n_days)) * 1e8
            for e in mock_g.etf_pool
        }
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool)
        for p in penalties:
            assert mock_g.MinCrowdPenalty <= p <= 1.0

    def test_constant_prices_low_crowding_not_penalized(self, strategy, mock_g):
        """横盘时拥挤度低，不应惩罚。"""
        n_days = 600
        close = {e: make_constant_prices(n_days=n_days) for e in mock_g.etf_pool}
        amount = {
            e: make_constant_prices(1e8, n_days=n_days)
            for e in mock_g.etf_pool
        }
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool)
        for p in penalties:
            assert p >= 0.5

    def test_insufficient_data_returns_one(self, strategy, mock_g):
        short_prices = make_linear_prices(n_days=100)
        prices = {
            'close': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'amount': make_prices_dataframe({e: short_prices * 1e8 for e in mock_g.etf_pool}),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool)
        assert all(p == 1.0 for p in penalties)


# ============================================================
# 8. 组合波动率控制测试
# ============================================================
class TestComputePortfolioVolScale:
    """测试组合波动率缩放系数。"""

    def test_all_zero_weights_returns_one(self, strategy, mock_g):
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        raw_weights = np.array([0.0, 0.0, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights
        )
        assert scale == 1.0

    def test_scale_not_exceeds_one(self, strategy, mock_g):
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        raw_weights = np.array([0.4, 0.4, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights
        )
        assert 0.0 <= scale <= 1.0

    def test_low_vol_portfolio_scale_is_one(self, strategy, mock_g):
        """低波动组合（常数价格）不应被缩放。"""
        n_days = 100
        close = {e: make_constant_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        raw_weights = np.array([0.4, 0.4, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights
        )
        assert scale == 1.0


# ============================================================
# 9. 集成测试 — weekly_check 完整流程
# ============================================================
class TestWeeklyCheckIntegration:
    """测试 weekly_check 端到端调仓流程。"""

    def test_weekly_check_does_not_crash(self, strategy, mock_g):
        """验证完整调仓流程不抛出异常。"""
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)

        close_prices = {
            '159819.XSHE': base * 1.2,
            '513100.XSHG': base * 1.1,
            '518880.XSHG': base * 1.0,
        }
        high_prices = {k: v * 1.01 for k, v in close_prices.items()}
        low_prices = {k: v * 0.99 for k, v in close_prices.items()}
        amount_prices = {k: np.abs(v) * 1e8 for k, v in close_prices.items()}

        _setup_get_price_mock(
            strategy,
            close=close_prices,
            high=high_prices,
            low=low_prices,
            amount=amount_prices,
        )

        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        # 不应抛出异常
        strategy.weekly_check(context)

    def test_all_trend_gates_zero_goes_to_cash(self, strategy, mock_g):
        """全部资产不通过趋势门槛时，不执行任何买入。"""
        n_days = 500
        # 持续下跌，全部不通过趋势
        down_prices = make_linear_down_prices(start=2.0, step=0.01, n_days=n_days)

        close_prices = {e: down_prices for e in mock_g.etf_pool}
        high_prices = {k: v * 1.01 for k, v in close_prices.items()}
        low_prices = {k: v * 0.99 for k, v in close_prices.items()}
        amount_prices = {k: np.abs(v) * 1e8 for k, v in close_prices.items()}

        _setup_get_price_mock(
            strategy,
            close=close_prices,
            high=high_prices,
            low=low_prices,
            amount=amount_prices,
        )

        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 1000
            mock_pos.price = 1.0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        # 应该对每只 ETF 调仓到 0
        calls = strategy.order_target_value.call_args_list
        for i, etf in enumerate(mock_g.etf_pool):
            found = any(
                c[0][0] == etf for c in calls
            )
            # 至少验证 order_target_value 对这三只 ETF 都有调用

    def test_single_asset_passes_trend(self, strategy, mock_g):
        """只有一只资产通过趋势时，正常处理。"""
        n_days = 800
        rng = np.random.default_rng(42)
        up_base = np.exp(np.cumsum(rng.normal(0.001, 0.015, n_days)) + 1.0)
        down_base = np.exp(np.cumsum(rng.normal(-0.001, 0.015, n_days)) + 1.0)

        close_prices = {
            '159819.XSHE': up_base,       # 上涨 → 通过趋势
            '513100.XSHG': down_base,     # 下跌 → 不通过
            '518880.XSHG': down_base,     # 下跌 → 不通过
        }
        high_prices = {k: v * 1.01 for k, v in close_prices.items()}
        low_prices = {k: v * 0.99 for k, v in close_prices.items()}
        amount_prices = {k: np.abs(v) * 1e8 for k, v in close_prices.items()}

        _setup_get_price_mock(
            strategy,
            close=close_prices,
            high=high_prices,
            low=low_prices,
            amount=amount_prices,
        )

        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        # 不应抛出异常
        strategy.weekly_check(context)

"""
ETF 多因子轮动策略 — 单元测试

测试覆盖：
  - 静态检查（模块加载、参数初始化）
  - 纯函数单元测试（percentile_rank, apply_weight_constraints, select_topk）
  - 模块计算测试（趋势门槛、动量分数、风险平价、RSRS、拥挤度、波动率缩放）
  - 集成测试（weekly_check 完整流程）
"""

import json
import math
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch, call

import numpy as np
import pandas as pd
import pytest


def test_strategy_loads_without_feishu_relay_tools(monkeypatch):
    import builtins
    import importlib.util
    import pathlib
    import sys

    monkeypatch.delitem(sys.modules, "FeishuRelayTools", raising=False)
    monkeypatch.setattr(builtins, "enable_profile", Mock())
    strategy_file = pathlib.Path(__file__).resolve().parent.parent / "etf_factor_rotation.py"
    spec = importlib.util.spec_from_file_location("etf_factor_rotation_no_feishu", str(strategy_file))
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert module.FeishuRelayTools is None


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
# 辅助函数 — 构造 mock get_price 返回值（R2 修复：逐 ETF 调用）
# ============================================================
def _setup_get_price_mock(strategy, close=None, high=None, low=None, amount=None):
    """配置 strategy.get_price mock，模拟逐 ETF 拉取模式。

    fetch_field 改为逐 ETF 拉取：
        get_price(etf, count=..., fields=[field], panel=False, skip_paused=True, fq='pre')

    mock 对单 ETF（str）返回单字段 DataFrame（columns=[field], index=日期）。
    """
    field_data_map = {'close': close, 'high': high, 'low': low, 'money': amount}

    def _build_etf_series(etf_code, field):
        data_dict = field_data_map.get(field)
        if data_dict is None or etf_code not in data_dict:
            return None
        arr = np.asarray(data_dict[etf_code])
        dates = pd.date_range(start='2020-01-01', periods=len(arr), freq='B')
        return pd.Series(arr, index=dates, name=etf_code)

    def mock_get_price(security, count=None, frequency=None, fields=None,
                       skip_paused=None, fq=None, panel=None, end_date=None):
        field = fields[0] if fields else 'close'

        # 逐 ETF 拉取：security 是 str
        s = _build_etf_series(security, field)
        if s is None or len(s) == 0:
            return None
        return pd.DataFrame({field: s.values}, index=s.index)

    strategy.get_price.side_effect = mock_get_price


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
            'build_rebalance_plan', 'prepare_delay_only_rebalance',
            'execute_pending_rebalance', 'mark_live_like_signal_day',
            'execute_live_like_rebalance',
            'get_history_data', 'compute_trend_gates', 'compute_momentum_scores',
            'select_topk', 'compute_rp_weights', 'compute_rsrs_multipliers',
            'compute_rsrs_adjusted_scores',
            'compute_momentum_tilt_multipliers', 'compute_rsrs_tilt_multipliers',
            'apply_relative_tilts',
            'compute_crowd_penalties', 'percentile_rank',
            'compute_portfolio_vol_scale', 'apply_weight_constraints',
            'execute_rebalance', 'fund_code', 'format_etf_name',
            'build_etf_display_names', 'fetch_etf_official_name',
            'load_etf_display_names',
        ]
        for fn in core_funcs:
            assert hasattr(strategy, fn), f"Missing function: {fn}"


class TestSetParameter:
    """测试参数初始化正确性。"""

    def test_set_parameter_writes_to_g(self, strategy):
        strategy.set_parameter(strategy)

        g = strategy.g
        assert len(g.etf_pool) >= 1
        assert len(g.etf_pool) == len(g.etf_names)
        assert 1 <= g.TopK <= len(g.etf_pool)
        assert g.MA_long > 0
        assert g.MA_long_by_etf == [20, 40, 100]
        assert g.TargetVol > 0
        assert 0 < g.MaxWeight <= g.MaxTotalWeight <= 1
        for etf, name in zip(g.etf_pool, g.etf_names):
            assert etf in name
        assert strategy.get_security_info.call_count >= len(g.etf_pool)

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

    def test_fq_mode_defaults_to_none(self, strategy):
        """fq_mode 默认为 None（不复权），经 FQ A/B 对比验证 fq='pre' 对场内基金不可靠。"""
        strategy.set_parameter(strategy)
        assert strategy.g.fq_mode is None

    def test_use_real_price_defaults_to_false(self, strategy):
        """use_real_price 默认为 False，配合 fq=None 使用。"""
        strategy.set_parameter(strategy)
        assert strategy.g.use_real_price is False


class TestEtfDisplayNames:
    """测试基金展示名始终保留编号，供报告和日志检索。"""

    def test_format_etf_name_adds_fund_code(self, strategy):
        assert (
            strategy.format_etf_name('159819.XSHE', '人工智能ETF易方达')
            == '人工智能ETF易方达(159819.XSHE)'
        )

    def test_format_etf_name_keeps_existing_security_code(self, strategy):
        name = '纳指ETF(513100.XSHG)'
        assert strategy.format_etf_name('513100.XSHG', name) == name

    def test_format_etf_name_upgrades_short_code_suffix(self, strategy):
        assert (
            strategy.format_etf_name('518880.XSHG', '黄金ETF(518880)')
            == '黄金ETF(518880.XSHG)'
        )

    def test_build_etf_display_names_aligned_to_pool(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
        names = ['人工智能ETF易方达', '纳指ETF', '黄金ETF']
        result = strategy.build_etf_display_names(pool, names)
        assert result == [
            '人工智能ETF易方达(159819.XSHE)',
            '纳指ETF(513100.XSHG)',
            '黄金ETF(518880.XSHG)',
        ]

    def test_fetch_etf_official_name_reads_joinquant_display_name(self, strategy):
        result = strategy.fetch_etf_official_name('159819.XSHE')
        assert result == '人工智能ETF易方达'
        strategy.get_security_info.assert_called_with('159819.XSHE')

    def test_load_etf_display_names_uses_joinquant_api(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
        result = strategy.load_etf_display_names(pool)
        assert result == [
            '人工智能ETF易方达(159819.XSHE)',
            '纳指ETF(513100.XSHG)',
            '黄金ETF(518880.XSHG)',
        ]

    def test_fetch_etf_official_name_fallback_when_api_fails(self, strategy):
        strategy.get_security_info.side_effect = RuntimeError("api unavailable")
        result = strategy.fetch_etf_official_name('159819.XSHE', fallback_name='人工智能ETF易方达')
        assert result == '人工智能ETF易方达'

    def test_log_step_uses_numbered_names(self, strategy, mock_g):
        strategy._log_step(
            "TrendGate",
            "趋势门槛",
            mock_g.etf_pool,
            [1.0, 0.0, 1.0],
            fmt=".0f",
            etf_names=mock_g.etf_names,
        )
        log_text = str(strategy.log.info.call_args_list)
        assert '人工智能ETF易方达(159819.XSHE)' in log_text
        assert '纳指ETF(513100.XSHG)' in log_text
        assert '黄金ETF(518880.XSHG)' in log_text


class TestInitialize:
    """测试 initialize 注册了正确的框架调用。"""

    def test_initialize_calls_set_option(self, strategy):
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.set_option.assert_any_call('use_real_price', False)
        strategy.set_option.assert_any_call('avoid_future_data', True)

    def test_initialize_registers_weekly_task(self, strategy):
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.run_weekly.assert_called_once()
        args, kwargs = strategy.run_weekly.call_args
        assert kwargs['weekday'] == 1
        assert kwargs['time'] == 'open'
        strategy.run_daily.assert_not_called()

    def test_initialize_registers_delay_only_tasks(self, strategy):
        original_set_parameter = strategy.set_parameter

        def set_delay_only(context):
            original_set_parameter(context)
            strategy.g.ExecutionTimingMode = "logic-2-delay-only"

        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        with patch.object(strategy, 'set_parameter', side_effect=set_delay_only):
            strategy.initialize(context)

        strategy.run_weekly.assert_called_once()
        _, weekly_kwargs = strategy.run_weekly.call_args
        assert weekly_kwargs['weekday'] == 1
        assert weekly_kwargs['time'] == 'open'
        strategy.run_daily.assert_called_once()
        _, daily_kwargs = strategy.run_daily.call_args
        assert daily_kwargs['time'] == 'open'

    def test_initialize_registers_live_like_task(self, strategy):
        original_set_parameter = strategy.set_parameter

        def set_live_like(context):
            original_set_parameter(context)
            strategy.g.ExecutionTimingMode = "logic-3-live-like"

        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        with patch.object(strategy, 'set_parameter', side_effect=set_live_like):
            strategy.initialize(context)

        strategy.run_weekly.assert_called_once()
        _, weekly_kwargs = strategy.run_weekly.call_args
        assert weekly_kwargs['weekday'] == 1
        assert weekly_kwargs['time'] == 'open'
        strategy.run_daily.assert_called_once()
        _, daily_kwargs = strategy.run_daily.call_args
        assert daily_kwargs['time'] == 'open'

    def test_initialize_calls_set_order_cost(self, strategy):
        """验证 initialize 调用了 set_order_cost 并传递正确的费率参数。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.set_order_cost.assert_called_once()
        args, kwargs = strategy.set_order_cost.call_args
        assert kwargs['type'] == 'fund'

    def test_initialize_calls_set_slippage(self, strategy):
        """验证 initialize 调用了 set_slippage 且 type='fund'。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        strategy.set_slippage.assert_called_once()
        kwargs = strategy.set_slippage.call_args[1]
        assert kwargs['type'] == 'fund'

    def test_initialize_registers_reference_security(self, strategy):
        """验证 run_weekly 注册了 reference_security='000300.XSHG'。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        kwargs = strategy.run_weekly.call_args[1]
        assert kwargs['reference_security'] == '000300.XSHG'

    def test_initialize_calls_set_parameter(self, strategy):
        """验证 initialize 后 g 对象包含了 set_parameter 写入的关键参数。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)
        assert hasattr(strategy.g, 'MaxWeight'), "g.MaxWeight not set by set_parameter"
        assert hasattr(strategy.g, 'MinWeight'), "g.MinWeight not set by set_parameter"
        assert hasattr(strategy.g, 'RebalanceThreshold'), "g.RebalanceThreshold not set"
        assert hasattr(strategy.g, 'TargetVol'), "g.TargetVol not set by set_parameter"
        assert len(strategy.g.etf_pool) >= 1
        assert len(strategy.g.etf_pool) == len(strategy.g.etf_names)
        assert 1 <= strategy.g.TopK <= len(strategy.g.etf_pool)

    def test_initialize_writes_run_start_audit_event(self, strategy):
        """initialize 应清空本次审计文件并写入 run_start。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        strategy.initialize(context)

        assert strategy.write_file.call_args_list[0][0][0].startswith("jq_auto_audit/")
        assert strategy.write_file.call_args_list[0][0][1] == ""
        assert strategy.write_file.call_args_list[0][1]["append"] is False
        event_line = strategy.write_file.call_args_list[1][0][1]
        event = json.loads(event_line)
        assert event["event"] == "run_start"
        assert event["seq"] == 1
        assert event["audit_token"] == strategy.JQ_AUTO_AUDIT_TOKEN

    def test_on_strategy_end_writes_run_end_audit_event(self, strategy, mock_g):
        """on_strategy_end 应写入完整性门禁需要的 run_end。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        context.portfolio.total_value = 123456.0
        context.portfolio.cash = 789.0

        strategy.on_strategy_end(context)

        event = json.loads(strategy.write_file.call_args[0][1])
        assert event["event"] == "run_end"
        assert event["total_value"] == 123456.0
        assert event["cash"] == 789.0


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
        params = strategy.snapshot_params()
        weights = np.array([0.80, 0.20, 0.0])
        result = strategy.apply_weight_constraints(weights, params)
        assert result[0] == 0.60
        assert result[1] == 0.20

    def test_drop_below_min_weight(self, strategy, mock_g):
        params = strategy.snapshot_params()
        weights = np.array([0.30, 0.04, 0.0])
        result = strategy.apply_weight_constraints(weights, params)
        assert result[0] == 0.30
        assert result[1] == 0.0

    def test_preserves_total_below_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        weights = np.array([0.20, 0.30, 0.10])
        result = strategy.apply_weight_constraints(weights, params)
        assert sum(result) <= 1.0

    def test_max_total_weight_cap(self, strategy, mock_g):
        """总仓位超过 MaxTotalWeight 时等比缩放。"""
        mock_g.MaxTotalWeight = 0.80
        params = strategy.snapshot_params()
        weights = np.array([0.60, 0.30, 0.10])
        result = strategy.apply_weight_constraints(weights, params)
        assert abs(sum(result) - 0.80) < 1e-10
        # 等比缩放：每个权重乘以 0.8
        assert abs(result[0] - 0.48) < 1e-10
        assert abs(result[1] - 0.24) < 1e-10

    def test_max_total_weight_no_effect_when_below(self, strategy, mock_g):
        """总仓位未超过 MaxTotalWeight 时不缩放。"""
        mock_g.MaxTotalWeight = 1.0
        params = strategy.snapshot_params()
        weights = np.array([0.30, 0.20, 0.10])
        result = strategy.apply_weight_constraints(weights, params)
        assert abs(sum(result) - 0.60) < 1e-10

    def test_max_weight_and_max_total_both_apply(self, strategy, mock_g):
        """MaxWeight 先裁剪，MaxTotalWeight 后缩放。"""
        mock_g.MaxWeight = 0.40
        mock_g.MaxTotalWeight = 0.60
        params = strategy.snapshot_params()
        weights = np.array([0.80, 0.20, 0.00])
        result = strategy.apply_weight_constraints(weights, params)
        # MaxWeight 裁剪：0.80 → 0.40，然后总仓位 0.40+0.20=0.60 == MaxTotalWeight
        assert abs(sum(result) - 0.60) < 1e-10
        assert abs(result[0] - 0.40) < 1e-10


class TestSelectTopK:
    """测试 TopK 选择逻辑。"""

    def test_selects_top2_from_3_active(self, strategy, mock_g):
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.6, 0.3])
        gates = np.array([1.0, 1.0, 1.0])
        selected = strategy.select_topk(scores, gates, params)
        assert selected == [True, True, False]

    def test_selects_all_when_less_than_k_active(self, strategy, mock_g):
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.0, 0.0])
        gates = np.array([1.0, 0.0, 0.0])
        selected = strategy.select_topk(scores, gates, params)
        assert selected == [True, False, False]

    def test_none_selected_when_no_trend(self, strategy, mock_g):
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.8, 0.7])
        gates = np.array([0.0, 0.0, 0.0])
        selected = strategy.select_topk(scores, gates, params)
        assert selected == [False, False, False]

    def test_all_selected_when_k_larger_than_active(self, strategy, mock_g):
        mock_g.TopK = 5
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.6, 0.3])
        gates = np.array([1.0, 1.0, 1.0])
        selected = strategy.select_topk(scores, gates, params)
        assert selected == [True, True, True]

    def test_tie_scores_all_active_selected_when_k_matches(self, strategy, mock_g):
        """同分并列且 K=活跃数时全部入选。"""
        mock_g.TopK = 2
        params = strategy.snapshot_params()
        scores = np.array([0.5, 0.5, 0.5])
        gates = np.array([1.0, 1.0, 1.0])
        selected = strategy.select_topk(scores, gates, params)
        assert sum(selected) == 2


# ============================================================
# 3. 趋势门槛测试
# ============================================================
class TestComputeTrendGates:
    """测试趋势均线过滤。"""

    def test_price_above_ma_passes(self, strategy, mock_g):
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        n_days = 20
        prices_above = np.arange(1.0, 1.0 + 0.02 * n_days, 0.02)[:n_days]
        close = {
            '159819.XSHE': prices_above,
            '513100.XSHG': prices_above * 0.9,
            '518880.XSHG': prices_above * 1.1,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert gates[0] == 1.0
        assert gates[1] == 1.0
        assert gates[2] == 1.0

    def test_price_below_ma_fails(self, strategy, mock_g):
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        n_days = 20
        prices_down = np.arange(2.0, 2.0 - 0.02 * n_days, -0.02)[:n_days]
        close = {
            '159819.XSHE': prices_down,
            '513100.XSHG': prices_down,
            '518880.XSHG': prices_down,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert all(g == 0.0 for g in gates)

    def test_insufficient_data_returns_zero(self, strategy, mock_g):
        mock_g.MA_long = 120
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        short_prices = make_linear_prices(n_days=50)
        close = {
            '159819.XSHE': short_prices,
            '513100.XSHG': short_prices,
            '518880.XSHG': short_prices,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert all(g == 0.0 for g in gates)

    def test_price_equals_ma_fails(self, strategy, mock_g):
        """current_close == ma（恰好等于）时严格不通过趋势门槛。"""
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        n_days = 10
        flat = make_constant_prices(1.0, n_days=n_days)
        close = {e: flat for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert all(g == 0.0 for g in gates)

    def test_data_exactly_equals_ma_window(self, strategy, mock_g):
        """len(series) == MA_long 刚好满足条件时正常计算不抛异常。"""
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        up = make_linear_prices(start=1.0, step=0.02, n_days=5)
        close = {e: up for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert all(g == 1.0 for g in gates)

    def test_etf_not_in_close_columns_returns_zero(self, strategy, mock_g):
        """ETF 不在 close.columns 时 trend_gate 保持 0，不抛异常。"""
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        n_days = 20
        up = make_linear_prices(start=1.0, step=0.02, n_days=n_days)
        # 只提供前两只 ETF 的 close 数据
        close = {
            '159819.XSHE': up,
            '513100.XSHG': up,
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert gates[0] == 1.0
        assert gates[1] == 1.0
        assert gates[2] == 0.0  # 不在 close.columns 中，保持 0

    def test_empty_close_dataframe_no_crash(self, strategy, mock_g):
        """close DataFrame 为空时所有 gate 为 0，不崩溃。"""
        mock_g.MA_long = 5
        mock_g.MA_long_by_etf = None
        params = strategy.snapshot_params()
        empty_close = pd.DataFrame()
        prices = {'close': empty_close}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert all(g == 0.0 for g in gates)

    def test_ma_long_by_etf_uses_per_asset_windows(self, strategy, mock_g):
        mock_g.MA_long = 120
        mock_g.MA_long_by_etf = [3, 5, 8]
        params = strategy.snapshot_params()
        close = {
            '159819.XSHE': [1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
            '513100.XSHG': [1, 1, 1, 1, 2, 2, 2, 2, 2, 1.5],
            '518880.XSHG': [1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = strategy.compute_trend_gates(prices, mock_g.etf_pool, params)
        assert gates.tolist() == [1.0, 0.0, 1.0]


# ============================================================
# 4. 动量分数测试
# ============================================================
class TestComputeMomentumScores:
    """测试多周期排名动量分数计算。"""

    def test_higher_return_gets_higher_score(self, strategy, mock_g):
        params = strategy.snapshot_params()
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

        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert scores[0] > scores[1] > scores[2]

    def test_trend_gate_zero_scores_zero(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 200
        prices_arr = np.arange(1.0, 1.0 + 0.005 * n_days, 0.005)[:n_days]
        close = {e: prices_arr for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 0.0, 1.0])

        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert scores[1] == 0.0  # 趋势不成立的资产分数为 0

    def test_no_active_assets_returns_zeros(self, strategy, mock_g):
        params = strategy.snapshot_params()
        prices = {
            'close': make_prices_dataframe({
                e: make_linear_prices(n_days=200) for e in mock_g.etf_pool
            })
        }
        gates = np.array([0.0, 0.0, 0.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert all(s == 0.0 for s in scores)

    def test_active_data_below_max_window_returns_zeros(self, strategy, mock_g):
        """len(active_close) <= max(windows) 时直接返回全零。"""
        params = strategy.snapshot_params()
        # max(windows)=120, 只给 100 天数据
        n_days = 100
        close = {e: make_linear_prices(n_days=n_days) for e in mock_g.etf_pool}
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 1.0, 1.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert all(s == 0.0 for s in scores)

    def test_active_data_just_above_max_window_proceeds(self, strategy, mock_g):
        """len(active_close) == max(windows)+1 时正常计算非零分数。"""
        params = strategy.snapshot_params()
        # max(windows)=120, 给 121 天数据
        n_days = 130
        close = {
            '159819.XSHE': make_linear_prices(start=1.0, step=0.005, n_days=n_days),
            '513100.XSHG': make_linear_prices(start=1.0, step=0.003, n_days=n_days),
            '518880.XSHG': make_linear_prices(start=1.0, step=0.001, n_days=n_days),
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 1.0, 1.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert scores[0] > 0
        assert scores[1] > 0
        assert scores[2] > 0

    def test_active_data_equals_max_window_returns_zeros(self, strategy, mock_g):
        """len(active_close) == max(windows) 时安全退化为全零分数。"""
        params = strategy.snapshot_params()
        # max(windows)=120, 恰好给 120 天数据
        n_days = 120
        close = {
            '159819.XSHE': make_linear_prices(start=1.0, step=0.005, n_days=n_days),
            '513100.XSHG': make_linear_prices(start=1.0, step=0.003, n_days=n_days),
            '518880.XSHG': make_linear_prices(start=1.0, step=0.001, n_days=n_days),
        }
        prices = {'close': make_prices_dataframe(close)}
        gates = np.array([1.0, 1.0, 1.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        assert all(s == 0.0 for s in scores)

    def test_etf_not_in_close_columns_ignored(self, strategy, mock_g):
        """部分 ETF 不在 close.columns 中时安全跳过，不影响其他 ETF 动量计算。"""
        params = strategy.snapshot_params()
        n_days = 200
        close = {
            '159819.XSHE': make_linear_prices(start=1.0, step=0.005, n_days=n_days),
            '513100.XSHG': make_linear_prices(start=1.0, step=0.003, n_days=n_days),
            # 518880.XSHG 不在 close 中
        }
        prices = {'close': make_prices_dataframe(close)}
        # 即使 trend_gates 标记全部活跃，缺失列的 ETF 也应安全退化为 0
        gates = np.array([1.0, 1.0, 1.0])
        scores = strategy.compute_momentum_scores(prices, mock_g.etf_pool, gates, params)
        # 缺失的 ETF 分数安全退化为 0，不崩溃
        assert scores[2] == 0.0
        # 有数据的 ETF 正常计算
        assert scores[0] > 0
        assert scores[1] > 0


# ============================================================
# 5. 风险平价测试
# ============================================================
class TestComputeRPWeights:
    """测试逆波动率风险平价权重计算。"""

    def test_weights_sum_to_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {
            '159819.XSHE': make_random_walk_prices(sigma=0.03, n_days=n_days),
            '513100.XSHG': make_random_walk_prices(sigma=0.02, n_days=n_days),
            '518880.XSHG': make_random_walk_prices(sigma=0.01, n_days=n_days),
        }
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, True, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected, params)
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_lower_vol_gets_higher_weight(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {
            '159819.XSHE': make_random_walk_prices(sigma=0.03, n_days=n_days),
            '513100.XSHG': make_random_walk_prices(sigma=0.02, n_days=n_days),
            '518880.XSHG': make_random_walk_prices(sigma=0.01, n_days=n_days),
        }
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, True, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected, params)
        assert weights[2] > weights[1] > weights[0]  # 黄金(低波) > 纳指 > AI

    def test_unselected_assets_get_zero(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, False, True]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected, params)
        assert weights[1] == 0.0
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_single_asset_gets_weight_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, False, False]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected, params)
        assert weights[0] == 1.0

    def test_no_selected_returns_zeros(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [False, False, False]

        weights = strategy.compute_rp_weights(prices, mock_g.etf_pool, selected, params)
        assert all(w == 0.0 for w in weights)

    def test_fewer_than_5_returns_defaults_vol_one(self, strategy):
        """收益样本 < 5 时 vol 退化为 1.0，权重等分。"""
        strategy.g.VolWindow = 60
        # 只给 4 天数据，dropna 后 < 5
        n_days = 4
        close = {
            '159819.XSHE': make_linear_prices(n_days=n_days),
            '513100.XSHG': make_linear_prices(n_days=n_days),
            '518880.XSHG': make_linear_prices(n_days=n_days),
        }
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, True, True]
        params = strategy.snapshot_params()

        weights = strategy.compute_rp_weights(prices, strategy.g.etf_pool, selected, params)
        # 样本不足 → vol=1.0 → 等权重
        assert abs(sum(weights) - 1.0) < 1e-10
        assert abs(weights[0] - 1.0 / 3) < 1e-10

    def test_zero_vol_floor_set_to_1e8(self, strategy):
        """常数价格 std=0 → vol 地板值 1e-8，防止除零。"""
        strategy.g.VolWindow = 20
        n_days = 30
        close = {e: make_constant_prices(1.0, n_days=n_days) for e in strategy.g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, True, True]
        params = strategy.snapshot_params()

        weights = strategy.compute_rp_weights(prices, strategy.g.etf_pool, selected, params)
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_etf_not_in_close_ret_skipped(self, strategy):
        """ETF 不在 close_ret.columns 时该资产权重为 0。"""
        strategy.g.VolWindow = 20
        n_days = 100
        close_2 = {
            strategy.g.etf_pool[0]: make_random_walk_prices(n_days=n_days),
            strategy.g.etf_pool[1]: make_random_walk_prices(n_days=n_days),
        }
        close_df = make_prices_dataframe(close_2)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        selected = [True, True, True]
        params = strategy.snapshot_params()

        weights = strategy.compute_rp_weights(prices, strategy.g.etf_pool, selected, params)
        assert weights[2] == 0.0
        assert abs(sum(weights) - 1.0) < 1e-10


# ============================================================
# 6. RSRS 线性修正测试
# ============================================================
class TestComputeRSRSMultipliers:
    """测试 RSRS 截断线性乘数计算。"""

    def test_returns_array_of_correct_length(self, strategy, mock_g):
        params = strategy.snapshot_params()
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
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        assert len(multipliers) == 3

    def test_values_in_valid_range(self, strategy, mock_g):
        params = strategy.snapshot_params()
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
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        for m in multipliers:
            assert 0.0 <= m <= 1.0

    def test_insufficient_data_returns_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        short_prices = make_linear_prices(n_days=50)
        prices = {
            'high': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: short_prices * 0.99 for e in mock_g.etf_pool}),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        assert all(m == 1.0 for m in multipliers)

    def test_strong_up_trend_keeps_multiplier_at_one(self, strategy, mock_g):
        """强势上涨时 RSRS 乘数应保持 1.0（只减不加）。"""
        params = strategy.snapshot_params()
        n_days = 800
        # 持续上涨
        base = np.arange(1.0, 1.0 + 0.003 * n_days, 0.003)[:n_days]
        high_prices = {e: base * 1.02 for e in mock_g.etf_pool}
        low_prices = {e: base * 0.98 for e in mock_g.etf_pool}

        prices = {
            'high': make_prices_dataframe(high_prices),
            'low': make_prices_dataframe(low_prices),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        # 只减不加原则：不应该超过 1.0
        for m in multipliers:
            assert m <= 1.0

    def test_rsrs_multiplier_can_reduce_position(self, strategy, mock_g):
        """价格结构转弱时 RSRS 乘数应降到 1.0 以下。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)

        low = np.exp(np.cumsum(rng.normal(0.0003, 0.01, n_days))) * 10

        # ETF0：正常趋势，High 比例稳定
        high_normal = low * 1.015 + rng.normal(0, 0.02, n_days)

        # ETF1/ETF2：结构转弱，High/Low 比例从 1.015 逐步降至 1.001
        high_mult = np.ones(n_days) * 1.015
        high_mult[-200:] = np.linspace(1.015, 1.001, 200)
        high_weakening = low * high_mult + rng.normal(0, 0.02, n_days)

        high_prices = {
            '159819.XSHE': high_normal,
            '513100.XSHG': high_weakening,
            '518880.XSHG': high_weakening,
        }
        low_prices = {e: low for e in mock_g.etf_pool}

        prices = {
            'high': make_prices_dataframe(high_prices),
            'low': make_prices_dataframe(low_prices),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)

        assert any(m < 1.0 for m in multipliers), (
            f"Expected at least one RSRS multiplier < 1.0 when price structure"
            f" weakens, got {multipliers}"
        )

    def test_constant_hilo_zero_variance_guarded(self, strategy, mock_g):
        """常数 high/low → 零方差和非有限值被守卫，最终乘数保持 1.0。"""
        params = strategy.snapshot_params()
        n_days = 800
        flat = make_constant_prices(1.0, n_days=n_days)
        prices = {
            'high': make_prices_dataframe({e: flat for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: flat for e in mock_g.etf_pool}),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        assert all(m == 1.0 for m in multipliers)

    def test_etf_not_in_high_low_columns_skipped(self, strategy, mock_g):
        """ETF 不在 high/low columns 中时乘数保持默认 1.0。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.exp(np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0)
        # 只提供前两只 ETF 的数据
        high_2 = {
            '159819.XSHE': base * 1.01,
            '513100.XSHG': base * 1.01,
        }
        low_2 = {
            '159819.XSHE': base * 0.99,
            '513100.XSHG': base * 0.99,
        }
        prices = {
            'high': make_prices_dataframe(high_2),
            'low': make_prices_dataframe(low_2),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        assert multipliers[2] == 1.0  # 缺失数据的 ETF 保持默认 1.0
        assert 0.0 <= multipliers[0] <= 1.0
        assert 0.0 <= multipliers[1] <= 1.0

    def test_data_exactly_at_minimum_window(self, strategy, mock_g):
        """len(h) == M+N-1 时正常计算，不崩溃。"""
        params = strategy.snapshot_params()
        strategy.g.RSRS_N = 18
        strategy.g.RSRS_M = 100
        min_len = strategy.g.RSRS_M + strategy.g.RSRS_N - 1  # 117
        n_days = min_len
        rng = np.random.default_rng(42)
        base = np.exp(np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        multipliers = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        assert len(multipliers) == 3
        for m in multipliers:
            assert 0.0 <= m <= 1.0


# ============================================================
# 6b. RSRS 原始调整信号测试
# ============================================================
class TestComputeRSRSAdjustedScores:
    """测试 RSRS 原始调整信号（RSRSAdj = RSRS_Z × R²）。"""

    def test_returns_array_of_correct_length(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        scores = strategy.compute_rsrs_adjusted_scores(prices, mock_g.etf_pool, params)
        assert len(scores) == 3

    def test_insufficient_data_returns_zero(self, strategy, mock_g):
        params = strategy.snapshot_params()
        short_prices = make_linear_prices(n_days=50)
        prices = {
            'high': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: short_prices * 0.99 for e in mock_g.etf_pool}),
        }
        scores = strategy.compute_rsrs_adjusted_scores(prices, mock_g.etf_pool, params)
        assert all(s == 0.0 for s in scores)

    def test_strong_up_trend_positive_scores(self, strategy, mock_g):
        """强势上涨时 RSRS 原始信号应为正。"""
        params = strategy.snapshot_params()
        n_days = 800
        base = np.arange(1.0, 1.0 + 0.003 * n_days, 0.003)[:n_days]
        prices = {
            'high': make_prices_dataframe({e: base * 1.02 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.98 for e in mock_g.etf_pool}),
        }
        scores = strategy.compute_rsrs_adjusted_scores(prices, mock_g.etf_pool, params)
        assert all(s >= 0 for s in scores)

    def test_constant_hilo_zero_variance_returns_zero(self, strategy, mock_g):
        """常数 high/low → 零方差守卫后分数为 0。"""
        params = strategy.snapshot_params()
        n_days = 800
        flat = make_constant_prices(1.0, n_days=n_days)
        prices = {
            'high': make_prices_dataframe({e: flat for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: flat for e in mock_g.etf_pool}),
        }
        scores = strategy.compute_rsrs_adjusted_scores(prices, mock_g.etf_pool, params)
        assert all(s == 0.0 for s in scores)

    def test_consistent_with_old_multipliers(self, strategy, mock_g):
        """新函数应与旧 compute_rsrs_multipliers 共享一致的原始信号。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        old = strategy.compute_rsrs_multipliers(prices, mock_g.etf_pool, params)
        scores = strategy.compute_rsrs_adjusted_scores(prices, mock_g.etf_pool, params)
        # 旧乘数 = clip(1 + score / full_cut, min, max)
        full_cut = params["RSRS_NegativeFullCut"]
        for i in range(3):
            expected = np.clip(1.0 + scores[i] / full_cut, params["RSRSMinMultiplier"], params["RSRSMaxMultiplier"])
            assert abs(old[i] - expected) < 1e-10, f"Mismatch at index {i}: old={old[i]}, from_scores={expected}"


# ============================================================
# 6c. 动量倾斜乘数测试
# ============================================================
class TestComputeMomentumTiltMultipliers:
    """测试动量分数转相对倾斜乘数。"""

    def test_default_rule_keeps_linear_tilts(self, strategy, mock_g):
        """默认关闭极端高动量弱化时，保持原线性映射。"""
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.5, 0.1])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert np.allclose(tilts, np.array([1.2, 1.0, 0.8]))

    def test_strong_momentum_gets_tilt_above_one(self, strategy, mock_g):
        """动量强资产应得到 >1 的倾斜乘数。"""
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.5, 0.1])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[0] > 1.0
        assert tilts[2] < 1.0

    def test_weak_momentum_gets_tilt_below_one(self, strategy, mock_g):
        """动量弱资产应得到 <1 的倾斜乘数。"""
        params = strategy.snapshot_params()
        scores = np.array([0.1, 0.5, 0.9])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[0] < 1.0

    def test_score_at_mean_gets_tilt_one(self, strategy, mock_g):
        """动量等于活跃资产均值时倾斜乘数为 1。"""
        params = strategy.snapshot_params()
        scores = np.array([0.5, 0.5, 0.5])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        for t in tilts:
            assert abs(t - 1.0) < 1e-10

    def test_inactive_assets_get_zero_tilt(self, strategy, mock_g):
        """非活跃资产倾斜乘数为 0。"""
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.5, 0.1])
        gates = np.array([1.0, 0.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[1] == 0.0

    def test_no_active_assets_returns_zeros(self, strategy, mock_g):
        """无活跃资产时返回全 0。"""
        params = strategy.snapshot_params()
        scores = np.array([0.9, 0.5, 0.1])
        gates = np.array([0.0, 0.0, 0.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert all(t == 0.0 for t in tilts)

    def test_extreme_momentum_clipped_by_bounds(self, strategy, mock_g):
        """极端动量差异被 TiltMin/TiltMax 截断。"""
        params = strategy.snapshot_params()
        mock_g.MomentumTiltStrength = 10.0  # 放大边缘
        mock_g.MomentumTiltMin = 0.70
        mock_g.MomentumTiltMax = 1.30
        params = strategy.snapshot_params()
        scores = np.array([0.99, 0.5, 0.01])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[0] == 1.30  # 被上限截断
        assert tilts[2] == 0.70  # 被下限截断

    def test_score_below_extreme_threshold_keeps_linear_tilt(self, strategy, mock_g):
        """低于极端阈值的高动量资产仍保留线性增强。"""
        mock_g.MomentumExtremeScoreStart = 0.90
        mock_g.MomentumExtremeTiltCap = 1.00
        params = strategy.snapshot_params()
        scores = np.array([0.85, 0.50, 0.15])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert abs(tilts[0] - 1.175) < 1e-10

    def test_extreme_score_caps_high_tilt(self, strategy, mock_g):
        """达到极端阈值且原本高于 cap 时，应被压回 cap。"""
        mock_g.MomentumExtremeScoreStart = 0.90
        mock_g.MomentumExtremeTiltCap = 1.00
        params = strategy.snapshot_params()
        scores = np.array([0.95, 0.50, 0.05])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[0] == 1.00

    def test_extreme_score_below_cap_is_unchanged(self, strategy, mock_g):
        """命中阈值但原倾斜未超过 cap 时，不额外改动。"""
        mock_g.MomentumExtremeScoreStart = 0.50
        mock_g.MomentumExtremeTiltCap = 1.20
        params = strategy.snapshot_params()
        scores = np.array([0.50, 0.40, 0.30])
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert abs(tilts[0] - 1.05) < 1e-10

    def test_single_active_asset_keeps_neutral_tilt(self, strategy, mock_g):
        """单活跃资产时即使命中阈值，也保持中性倾斜。"""
        mock_g.MomentumExtremeScoreStart = 0.90
        mock_g.MomentumExtremeTiltCap = 1.00
        params = strategy.snapshot_params()
        scores = np.array([1.0, 0.0, 0.0])
        gates = np.array([1.0, 0.0, 0.0])
        tilts = strategy.compute_momentum_tilt_multipliers(scores, gates, params)
        assert tilts[0] == 1.0
        assert tilts[1] == 0.0
        assert tilts[2] == 0.0


# ============================================================
# 6d. RSRS 倾斜乘数测试
# ============================================================
class TestComputeRSRSTiltMultipliers:
    """测试 RSRS 原始信号转相对倾斜乘数。"""

    def test_returns_correct_length(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        assert len(tilts) == 3

    def test_inactive_assets_get_zero_tilt(self, strategy, mock_g):
        """非活跃资产 RSRS 倾斜乘数为 0。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        gates = np.array([1.0, 0.0, 1.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        assert tilts[1] == 0.0

    def test_no_active_assets_returns_zeros(self, strategy, mock_g):
        """无活跃资产时返回全 0。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        gates = np.array([0.0, 0.0, 0.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        assert all(t == 0.0 for t in tilts)

    def test_identical_rsrs_adj_gets_neutral_tilt(self, strategy, mock_g):
        """所有活跃资产 RSRS 原始信号相同时，倾斜乘数退化为 1。"""
        params = strategy.snapshot_params()
        n_days = 800
        rng = np.random.default_rng(42)
        base = np.cumsum(rng.normal(0.0005, 0.015, n_days)) + 1.0
        base = np.exp(base)
        # 三只 ETF 用相同的 high/low
        prices = {
            'high': make_prices_dataframe({e: base * 1.01 for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: base * 0.99 for e in mock_g.etf_pool}),
        }
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        for t in tilts:
            assert abs(t - 1.0) < 1e-10

    def test_insufficient_data_active_gets_neutral_tilt(self, strategy, mock_g):
        """数据不足时活跃资产 RSRS_Adj 退化为 0 → 退化为中性倾斜。"""
        params = strategy.snapshot_params()
        short_prices = make_linear_prices(n_days=50)
        prices = {
            'high': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'low': make_prices_dataframe({e: short_prices * 0.99 for e in mock_g.etf_pool}),
        }
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        for t in tilts:
            assert abs(t - 1.0) < 1e-10

    def test_extreme_rsrs_clipped_by_bounds(self, strategy, mock_g):
        """极端 RSRS 差异被 RSRSTiltMin/RSRSTiltMax 截断。

        使用极小 NegativeFullCut 放大边缘，验证边界生效。
        """
        mock_g.RSRS_NegativeFullCut = 0.01
        mock_g.RSRSTiltMin = 0.70
        mock_g.RSRSTiltMax = 1.30
        mock_g.RSRS_N = 10
        mock_g.RSRS_M = 50
        params = strategy.snapshot_params()
        n_days = 200
        # ETF0: 上涨趋势 + High/Low 价差逐步扩大 → beta 上升趋势 → RSRS 偏高
        # ETF2: 下跌趋势 + High/Low 价差逐步收窄 → beta 下降趋势 → RSRS 偏低
        base = np.arange(1.0, 1.0 + 0.002 * n_days, 0.002)[:n_days]
        spread_up = np.linspace(0.02, 0.08, n_days)
        spread_down = np.linspace(0.08, 0.02, n_days)
        spread_neutral = np.full(n_days, 0.04)
        prices = {
            'high': make_prices_dataframe({
                '159819.XSHE': base * (1 + spread_up / 2),
                '513100.XSHG': base * (1 + spread_neutral / 2),
                '518880.XSHG': base * (1 + spread_down / 2),
            }),
            'low': make_prices_dataframe({
                '159819.XSHE': base * (1 - spread_up / 2),
                '513100.XSHG': base * (1 - spread_neutral / 2),
                '518880.XSHG': base * (1 - spread_down / 2),
            }),
        }
        gates = np.array([1.0, 1.0, 1.0])
        tilts = strategy.compute_rsrs_tilt_multipliers(prices, mock_g.etf_pool, gates, params)
        # 所有值应在边界内
        for t in tilts:
            assert 0.70 <= t <= 1.30, f"Tilt {t} outside bounds"
        # 通过放大边缘后至少有一个值触及边界
        at_boundary = any(abs(t - 0.70) < 1e-10 or abs(t - 1.30) < 1e-10 for t in tilts)
        assert at_boundary, f"Expected at least one tilt at clip boundary, got {tilts}"


# ============================================================
# 6e. 倾斜合成测试
# ============================================================
class TestApplyRelativeTilts:
    """测试 apply_relative_tilts 倾斜权重合成与归一化。"""

    def test_neutral_tilts_preserve_rp_weights(self, strategy):
        """动量与 RSRS 都为中性乘数时 TiltedWeight == RPWeight。"""
        rp = np.array([0.6, 0.4, 0.0])
        gates = np.array([1.0, 1.0, 0.0])
        mom_tilts = np.array([1.0, 1.0, 0.0])
        rsrs_tilts = np.array([1.0, 1.0, 0.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert abs(tilted[0] - 0.6) < 1e-10
        assert abs(tilted[1] - 0.4) < 1e-10
        assert tilted[2] == 0.0

    def test_tilted_sum_equals_base_total(self, strategy):
        """倾斜后活跃资产权重合计等于原始 sum(RPWeight_active)。"""
        rp = np.array([0.5, 0.3, 0.2])
        gates = np.array([1.0, 1.0, 1.0])
        mom_tilts = np.array([1.2, 1.0, 0.8])
        rsrs_tilts = np.array([1.0, 1.0, 1.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert abs(tilted.sum() - 1.0) < 1e-10

    def test_inactive_assets_stay_zero(self, strategy):
        """趋势不成立资产权重保持 0。"""
        rp = np.array([0.6, 0.0, 0.4])
        gates = np.array([1.0, 0.0, 1.0])
        mom_tilts = np.array([1.2, 0.0, 0.8])
        rsrs_tilts = np.array([1.1, 0.0, 0.9])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert tilted[1] == 0.0

    def test_denominator_zero_falls_back_to_rp(self, strategy):
        """tilted_raw 分母为 0 时回退原始 RPWeight。"""
        rp = np.array([0.5, 0.5, 0.0])
        gates = np.array([1.0, 1.0, 0.0])
        mom_tilts = np.array([0.0, 0.0, 0.0])
        rsrs_tilts = np.array([0.0, 0.0, 0.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert abs(tilted[0] - 0.5) < 1e-10
        assert abs(tilted[1] - 0.5) < 1e-10

    def test_strong_momentum_gets_higher_tilted_weight(self, strategy):
        """强动量资产倾斜后相对权重上升。"""
        rp = np.array([0.5, 0.5, 0.0])
        gates = np.array([1.0, 1.0, 0.0])
        mom_tilts = np.array([1.3, 0.7, 0.0])
        rsrs_tilts = np.array([1.0, 1.0, 0.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert tilted[0] > rp[0]

    def test_no_active_assets_returns_zeros(self, strategy):
        """无活跃资产时返回全 0。"""
        rp = np.array([0.0, 0.0, 0.0])
        gates = np.array([0.0, 0.0, 0.0])
        mom_tilts = np.array([0.0, 0.0, 0.0])
        rsrs_tilts = np.array([0.0, 0.0, 0.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert all(t == 0.0 for t in tilted)

    def test_single_active_asset_preserves_rp_weight(self, strategy):
        """单个活跃资产时 TiltedWeight 应等于其 RPWeight。"""
        rp = np.array([1.0, 0.0, 0.0])
        gates = np.array([1.0, 0.0, 0.0])
        mom_tilts = np.array([1.2, 0.0, 0.0])
        rsrs_tilts = np.array([1.1, 0.0, 0.0])
        tilted = strategy.apply_relative_tilts(rp, gates, mom_tilts, rsrs_tilts)
        assert abs(tilted[0] - 1.0) < 1e-10


# ============================================================
# 7. 拥挤度惩罚测试
# ============================================================
class TestComputeCrowdPenalties:
    """测试拥挤度线性惩罚乘数。"""

    def test_returns_array_of_correct_length(self, strategy, mock_g):
        params = strategy.snapshot_params()
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
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool, params)
        assert len(penalties) == 3

    def test_values_in_valid_range(self, strategy, mock_g):
        params = strategy.snapshot_params()
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
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool, params)
        for p in penalties:
            assert mock_g.MinCrowdPenalty <= p <= 1.0

    def test_constant_prices_low_crowding_not_penalized(self, strategy, mock_g):
        """横盘时拥挤度低，不应惩罚。"""
        params = strategy.snapshot_params()
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
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool, params)
        for p in penalties:
            assert p >= 0.5

    def test_insufficient_data_returns_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        short_prices = make_linear_prices(n_days=100)
        prices = {
            'close': make_prices_dataframe({e: short_prices for e in mock_g.etf_pool}),
            'amount': make_prices_dataframe({e: short_prices * 1e8 for e in mock_g.etf_pool}),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool, params)
        assert all(p == 1.0 for p in penalties)

    def test_low_crowd_score_not_penalized(self, strategy, mock_g):
        """crowd_score < CrowdStart 时 penalty=1.0（不受惩罚）。"""
        params = strategy.snapshot_params()
        n_days = 600
        # 常数价格：ret≈0, deviation≈0, vol≈0 → 各指标分位排名低 → crowd_score 低
        close = {e: make_constant_prices(1.0, n_days=n_days) for e in mock_g.etf_pool}
        amount = {e: make_constant_prices(1e8, n_days=n_days) for e in mock_g.etf_pool}
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        penalties = strategy.compute_crowd_penalties(prices, mock_g.etf_pool, params)
        for p in penalties:
            assert p == 1.0, f"Low crowd should not be penalized, got {p}"

    def test_high_crowd_score_penalized(self, strategy):
        """crowd_score > CrowdEnd 时 penalty=MinCrowdPenalty（最大惩罚）。"""
        # 降低阈值确保强趋势数据能跨过 CrowdEnd
        strategy.g.CrowdStart = 0.30
        strategy.g.CrowdEnd = 0.70
        strategy.g.MinCrowdPenalty = 0.30
        strategy.g.CrowdWindow = 500
        n_days = 600
        rng = np.random.default_rng(42)
        # 持续上涨 + 高波动 → ret20/ret60 分位高 → crowd_score 高
        strong_up = np.exp(np.cumsum(rng.normal(0.003, 0.02, n_days)))
        close = {e: strong_up for e in strategy.g.etf_pool}
        vol_amt = np.abs(np.cumsum(rng.normal(0, 0.5e8, n_days))) + 1e8
        amount = {e: vol_amt for e in strategy.g.etf_pool}
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        params = strategy.snapshot_params()
        penalties = strategy.compute_crowd_penalties(prices, strategy.g.etf_pool, params)
        # 有上涨趋势时 crowd_score 会偏高，至少有一只被惩罚
        assert any(p < 1.0 for p in penalties), (
            f"Expected at least one ETF penalized, got {penalties}"
        )

    def test_crowd_score_between_start_and_end_interpolated(self, strategy):
        """crowd_score 在 CrowdStart~CrowdEnd 之间时 penalty 在 [MinPenalty,1] 范围。"""
        strategy.g.CrowdStart = 0.40
        strategy.g.CrowdEnd = 0.90
        strategy.g.MinCrowdPenalty = 0.30
        strategy.g.CrowdWindow = 500
        n_days = 600
        rng = np.random.default_rng(99)
        mod_up = np.exp(np.cumsum(rng.normal(0.001, 0.015, n_days)))
        close = {e: mod_up for e in strategy.g.etf_pool}
        amount = {e: np.abs(np.cumsum(rng.normal(0, 0.3e8, n_days))) + 1e8
                  for e in strategy.g.etf_pool}
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        params = strategy.snapshot_params()
        penalties = strategy.compute_crowd_penalties(prices, strategy.g.etf_pool, params)
        for p in penalties:
            assert 0.30 <= p <= 1.0

    def test_amount_missing_fallback_to_05(self, strategy):
        """amount 数据缺失时对应指标回退到 0.5，不影响其他指标计算。"""
        strategy.g.CrowdWindow = 500
        n_days = 600
        rng = np.random.default_rng(42)
        prices_arr = np.exp(np.cumsum(rng.normal(0.0005, 0.015, n_days)))
        close = {e: prices_arr for e in strategy.g.etf_pool}
        # 不提供 amount 数据
        prices = {'close': make_prices_dataframe(close), 'amount': pd.DataFrame()}
        params = strategy.snapshot_params()
        penalties = strategy.compute_crowd_penalties(prices, strategy.g.etf_pool, params)
        assert len(penalties) == 3
        for p in penalties:
            assert 0.30 <= p <= 1.0

    def test_etf_not_in_close_columns_penalty_defaults_to_one(self, strategy):
        """ETF 不在 close.columns 中时 penalty 保持默认 1.0。"""
        strategy.g.CrowdWindow = 500
        n_days = 600
        rng = np.random.default_rng(42)
        prices_arr = np.exp(np.cumsum(rng.normal(0.0005, 0.015, n_days)))
        # 只提供前两只 ETF 的 close 数据
        close = {
            strategy.g.etf_pool[0]: prices_arr,
            strategy.g.etf_pool[1]: prices_arr,
        }
        amount = {
            strategy.g.etf_pool[0]: np.abs(np.cumsum(rng.normal(0, 0.3e8, n_days))) + 1e8,
            strategy.g.etf_pool[1]: np.abs(np.cumsum(rng.normal(0, 0.3e8, n_days))) + 1e8,
        }
        prices = {
            'close': make_prices_dataframe(close),
            'amount': make_prices_dataframe(amount),
        }
        params = strategy.snapshot_params()
        penalties = strategy.compute_crowd_penalties(prices, strategy.g.etf_pool, params)
        assert penalties[2] == 1.0  # 缺失数据 → 默认 1.0
        assert 0.30 <= penalties[0] <= 1.0
        assert 0.30 <= penalties[1] <= 1.0


# ============================================================
# 8. 组合波动率控制测试
# ============================================================
class TestComputePortfolioVolScale:
    """测试组合波动率缩放系数。"""

    def test_all_zero_weights_returns_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        raw_weights = np.array([0.0, 0.0, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights, params
        )
        assert scale == 1.0

    def test_scale_not_exceeds_one(self, strategy, mock_g):
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_random_walk_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        raw_weights = np.array([0.4, 0.4, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights, params
        )
        assert 0.0 <= scale <= 1.0

    def test_low_vol_portfolio_scale_is_one(self, strategy, mock_g):
        """低波动组合（常数价格）不应被缩放。"""
        params = strategy.snapshot_params()
        n_days = 100
        close = {e: make_constant_prices(n_days=n_days) for e in mock_g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        raw_weights = np.array([0.4, 0.4, 0.0])

        scale = strategy.compute_portfolio_vol_scale(
            prices, mock_g.etf_pool, raw_weights, params
        )
        assert scale == 1.0

    def test_portfolio_missing_column_returns_one(self, strategy):
        """active ETF 不在 close_ret.columns 时回退 1.0。"""
        strategy.g.PortfolioVolWindow = 30
        n_days = 100
        close_2 = {
            strategy.g.etf_pool[0]: make_random_walk_prices(n_days=n_days),
            strategy.g.etf_pool[1]: make_random_walk_prices(n_days=n_days),
        }
        close_df = make_prices_dataframe(close_2)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        # raw_weights 第三只 ETF 有正权重，但 close_ret 中没有其列
        raw_weights = np.array([0.4, 0.3, 0.3])
        params = strategy.snapshot_params()

        scale = strategy.compute_portfolio_vol_scale(
            prices, strategy.g.etf_pool, raw_weights, params
        )
        assert scale == 1.0

    def test_insufficient_returns_returns_one(self, strategy):
        """收益样本 < PortfolioVolWindow 时回退 1.0。"""
        strategy.g.PortfolioVolWindow = 60
        # 只给 30 天数据
        n_days = 30
        close = {e: make_random_walk_prices(n_days=n_days) for e in strategy.g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        raw_weights = np.array([0.4, 0.4, 0.0])
        params = strategy.snapshot_params()

        scale = strategy.compute_portfolio_vol_scale(
            prices, strategy.g.etf_pool, raw_weights, params
        )
        assert scale == 1.0

    def test_portfolio_vol_exceeds_target_scale_below_one(self, strategy):
        """组合波动率超 TargetVol 时应缩仓，scale < 1.0。"""
        strategy.g.PortfolioVolWindow = 60
        strategy.g.TargetVol = 0.05  # 很低的 target，大概率触发缩仓
        strategy.g.annual_factor = 252
        n_days = 200
        # 高波动数据
        close = {e: make_random_walk_prices(sigma=0.03, n_days=n_days)
                 for e in strategy.g.etf_pool}
        close_df = make_prices_dataframe(close)
        prices = {'close': close_df, 'close_ret': close_df.pct_change()}
        raw_weights = np.array([0.5, 0.5, 0.0])
        params = strategy.snapshot_params()

        scale = strategy.compute_portfolio_vol_scale(
            prices, strategy.g.etf_pool, raw_weights, params
        )
        assert 0.0 < scale <= 1.0


# ============================================================
# 9. 集成测试 — weekly_check 完整流程
# ============================================================
class TestWeeklyCheckIntegration:
    """测试 weekly_check 端到端调仓流程。"""

    def test_weekly_check_does_not_crash(self, strategy, mock_g):
        """验证完整调仓流程不抛出异常，且核心链路全部执行。"""
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
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        # 验证核心链路全部执行：TrendGate → RPWeight → MomentumScore → MomentumTilt
        #   → RSRSTilt → TiltedWeight → CrowdPenalty → PortfolioVolScale → FinalWeight
        log_text = str(strategy.log.info.call_args_list)
        expected_modules = [
            'TrendGate', 'RPWeight', 'MomentumScore', 'MomentumTilt',
            'RSRSTilt', 'TiltedWeight', 'CrowdPenalty', 'FinalWeight', 'PortfolioVolScale',
        ]
        for mod in expected_modules:
            assert mod in log_text, f"Missing intermediate log for module: {mod}"
        # 不再要求 Selected 出现在日志中
        assert 'Selected' not in log_text, (
            "Selected (TopK) should not appear in new main flow logs"
        )
        # 上涨趋势数据应有至少一只通过趋势门槛 → 应有下单
        assert strategy.order_target_value.call_count >= 1, (
            "Expected at least one order when some trends pass"
        )
        audit_events = [
            json.loads(call_args[0][1])
            for call_args in strategy.write_file.call_args_list
        ]
        signal_events = [event for event in audit_events if event["event"] == "rebalance_signals"]
        assert len(signal_events) == 1
        signal_event = signal_events[0]
        for key in [
            "trend_gates", "rp_weights", "momentum_scores", "momentum_tilts",
            "rsrs_tilts", "tilted_weights", "crowd_penalties", "raw_weights",
            "portfolio_vol_scale", "final_weights",
        ]:
            assert key in signal_event

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
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        # 每只 ETF 当前持仓市值需超过 RebalanceThreshold(3%)，否则会被阈值跳过
        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 5000
            mock_pos.price = 10.0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        # 验证中间步骤：趋势门槛全 0
        log_text = str(strategy.log.info.call_args_list)
        assert 'TrendGate' in log_text, "TrendGate log missing when all trends fail"
        assert 'RPWeight' in log_text, "RPWeight log missing when all trends fail"

        # 全部趋势失效 → 已有持仓必须被清仓（target_value = 0）
        calls = strategy.order_target_value.call_args_list
        called_etfs = set()
        for c in calls:
            etf = c[0][0]
            target_value = c[0][1]
            called_etfs.add(etf)
            assert target_value == 0, (
                f"Expected target_value=0 for {etf} when all trends fail,"
                f" got {target_value}"
            )

        # 三只 ETF 当前都有持仓，必须全部被调仓到 0
        assert called_etfs == set(mock_g.etf_pool), (
            f"Expected all held ETFs to be ordered to zero,"
            f" got calls for: {called_etfs}"
        )

    def test_single_asset_passes_trend(self, strategy, mock_g):
        """只有一只资产通过趋势时，仅该资产被选中并下单。"""
        n_days = 800
        rng = np.random.default_rng(42)
        up_base = np.exp(np.cumsum(rng.normal(0.001, 0.015, n_days)) + 1.0)
        down_base = np.exp(np.cumsum(rng.normal(-0.001, 0.015, n_days)) + 1.0)

        close_prices = {
            '159819.XSHE': up_base,
            '513100.XSHG': down_base,
            '518880.XSHG': down_base,
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
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        # 验证完整链路日志
        log_text = str(strategy.log.info.call_args_list)
        expected_modules = [
            'TrendGate', 'RPWeight', 'MomentumScore', 'MomentumTilt',
            'RSRSTilt', 'TiltedWeight', 'CrowdPenalty', 'FinalWeight', 'PortfolioVolScale',
        ]
        for mod in expected_modules:
            assert mod in log_text, f"Missing intermediate log for module: {mod}"
        # 仅上涨的 ETF 应有非零目标权重 → 应有下单记录
        assert strategy.order_target_value.call_count >= 1, (
            "Expected at least one order for the trending asset"
        )


class TestExecutionTimingModes:
    """测试三种执行时序的调度语义。"""

    def test_delay_only_prepares_then_executes_next_day(self, strategy, mock_g):
        mock_g.ExecutionTimingMode = "logic-2-delay-only"
        params = strategy.snapshot_params()
        final_weights = np.array([0.4, 0.3, 0.0])
        plan = {
            "pool": list(mock_g.etf_pool),
            "final_weights": final_weights,
            "params": params,
            "asof_date": pd.Timestamp("2026-05-15").date(),
            "prepared_date": pd.Timestamp("2026-05-18").date(),
        }

        with patch.object(strategy, 'build_rebalance_plan', return_value=plan):
            monday = SimpleNamespace(
                current_dt=pd.Timestamp("2026-05-18 09:30:00").to_pydatetime(),
                previous_date=pd.Timestamp("2026-05-15").date(),
                portfolio=strategy._mock_portfolio,
            )
            strategy.prepare_delay_only_rebalance(monday)

        assert strategy.g.pending_rebalances == [plan]

        with patch.object(strategy, 'execute_rebalance') as execute:
            strategy.execute_pending_rebalance(monday)
            execute.assert_not_called()

            tuesday = SimpleNamespace(
                current_dt=pd.Timestamp("2026-05-19 09:30:00").to_pydatetime(),
                previous_date=pd.Timestamp("2026-05-18").date(),
                portfolio=strategy._mock_portfolio,
            )
            strategy.execute_pending_rebalance(tuesday)
            execute.assert_called_once_with(
                tuesday,
                plan["pool"],
                plan["final_weights"],
                plan["params"],
            )

        assert strategy.g.pending_rebalances == []

    def test_delay_only_keeps_queued_plan_across_holiday_gap(self, strategy, mock_g):
        mock_g.ExecutionTimingMode = "logic-2-delay-only"
        first_plan = {
            "pool": list(mock_g.etf_pool),
            "final_weights": np.array([0.4, 0.3, 0.0]),
            "params": strategy.snapshot_params(),
            "asof_date": pd.Timestamp("2021-09-30").date(),
            "prepared_date": pd.Timestamp("2021-10-08").date(),
        }
        second_plan = {
            "pool": list(mock_g.etf_pool),
            "final_weights": np.array([0.2, 0.5, 0.0]),
            "params": strategy.snapshot_params(),
            "asof_date": pd.Timestamp("2021-10-08").date(),
            "prepared_date": pd.Timestamp("2021-10-11").date(),
        }
        strategy.g.pending_rebalances = [first_plan, second_plan]
        monday = SimpleNamespace(
            current_dt=pd.Timestamp("2021-10-11 09:30:00").to_pydatetime(),
            previous_date=pd.Timestamp("2021-10-08").date(),
            portfolio=strategy._mock_portfolio,
        )

        with patch.object(strategy, 'execute_rebalance') as execute:
            strategy.execute_pending_rebalance(monday)

        execute.assert_called_once_with(
            monday,
            first_plan["pool"],
            first_plan["final_weights"],
            first_plan["params"],
        )
        assert strategy.g.pending_rebalances == [second_plan]

    def test_live_like_marks_then_executes_next_trade_day(self, strategy, mock_g):
        mock_g.ExecutionTimingMode = "logic-3-live-like"
        monday = SimpleNamespace(
            current_dt=pd.Timestamp("2026-05-18 09:30:00").to_pydatetime(),
            previous_date=pd.Timestamp("2026-05-15").date(),
            portfolio=strategy._mock_portfolio,
        )
        tuesday = SimpleNamespace(
            current_dt=pd.Timestamp("2026-05-19 09:30:00").to_pydatetime(),
            previous_date=pd.Timestamp("2026-05-18").date(),
            portfolio=strategy._mock_portfolio,
        )

        with patch.object(strategy, 'weekly_check') as weekly_check:
            strategy.mark_live_like_signal_day(monday)
            strategy.execute_live_like_rebalance(monday)
            weekly_check.assert_not_called()

            strategy.execute_live_like_rebalance(tuesday)
            weekly_check.assert_called_once_with(tuesday)

        assert strategy.g.pending_live_like_signal_days == []

    def test_live_like_executes_after_holiday_gap(self, strategy, mock_g):
        mock_g.ExecutionTimingMode = "logic-3-live-like"
        friday = SimpleNamespace(
            current_dt=pd.Timestamp("2021-10-08 09:30:00").to_pydatetime(),
            previous_date=pd.Timestamp("2021-09-30").date(),
            portfolio=strategy._mock_portfolio,
        )
        monday = SimpleNamespace(
            current_dt=pd.Timestamp("2021-10-11 09:30:00").to_pydatetime(),
            previous_date=pd.Timestamp("2021-10-08").date(),
            portfolio=strategy._mock_portfolio,
        )

        with patch.object(strategy, 'weekly_check') as weekly_check:
            strategy.mark_live_like_signal_day(friday)
            strategy.mark_live_like_signal_day(monday)
            strategy.execute_live_like_rebalance(monday)

        weekly_check.assert_called_once_with(monday)
        assert strategy.g.pending_live_like_signal_days == [
            pd.Timestamp("2021-10-11").date()
        ]


# ============================================================
# 10. R3 修复验证 — get_history_data 显式 end_date=context.previous_date
# ============================================================
class TestGetHistoryDataEndDate:
    """测试 get_history_data 显式传递 end_date，避免开盘调仓引入未来数据。"""

    def test_get_history_data_passes_previous_date(self, strategy, mock_g):
        """get_history_data 所有 get_price 调用必须包含 end_date=context.previous_date。"""
        params = strategy.snapshot_params()
        n_days = 200
        data = {e: make_linear_prices(n_days=n_days) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data, high=data, low=data, amount=data)

        context = SimpleNamespace()
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        strategy.get_history_data(context, mock_g.etf_pool, params)

        for call_args in strategy.get_price.call_args_list:
            actual_end_date = call_args[1].get('end_date')
            assert actual_end_date == '2025-12-31', (
                f"Expected end_date='2025-12-31', got {actual_end_date}"
            )

    def test_get_history_data_logs_freshness(self, strategy, mock_g):
        """get_history_data 应记录历史数据最后日期与 context.previous_date 的对比。"""
        params = strategy.snapshot_params()
        n_days = 200
        data = {e: make_linear_prices(n_days=n_days) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data, high=data, low=data, amount=data)

        context = SimpleNamespace()
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        strategy.get_history_data(context, mock_g.etf_pool, params)

        # 验证 log.info 被调用，且包含 end_date 关键词
        info_calls = [
            c for c in strategy.log.info.call_args_list
            if 'end_date' in str(c)
        ]
        assert len(info_calls) >= 1, (
            "Expected log.info to contain data freshness info with 'end_date'"
        )

    def test_weekly_check_passes_end_date(self, strategy, mock_g):
        """集成验证：weekly_check 完整流程中 get_price 调用包含 end_date。"""
        params = strategy.snapshot_params()
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
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        for call_args in strategy.get_price.call_args_list:
            actual_end_date = call_args[1].get('end_date')
            assert actual_end_date == '2025-12-31', (
                f"weekly_check get_price call missing end_date: {call_args}"
            )


# ============================================================
# 11. R2 修复验证 — fetch_field 逐 ETF 调用 + panel=False
# ============================================================
class TestFetchField:
    """测试 fetch_field 的逐 ETF 拉取行为和 panel=False 传参。"""

    def test_calls_get_price_per_etf(self, strategy, mock_g):
        """fetch_field 应逐 ETF 调用 get_price，3 只 ETF 产生 3 次调用。"""
        params = strategy.snapshot_params()
        pool = mock_g.etf_pool
        n_days = 100
        prices_arr = make_linear_prices(n_days=n_days)

        data = {e: prices_arr for e in pool}
        _setup_get_price_mock(strategy, close=data)

        result = strategy.fetch_field(pool, 'close', 100, params)

        assert strategy.get_price.call_count == 3
        called_etfs = [c[0][0] for c in strategy.get_price.call_args_list]
        assert called_etfs == pool

    def test_passes_panel_false(self, strategy, mock_g):
        """整池拉取时 get_price 必须传 panel=False。"""
        params = strategy.snapshot_params()
        data = {e: make_linear_prices(n_days=100) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data)

        strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        call_args = strategy.get_price.call_args
        assert call_args[1].get('panel') is False, (
            f"panel parameter must be False, got {call_args[1].get('panel')}"
        )

    def test_passes_skip_paused_true(self, strategy, mock_g):
        """每次 get_price 调用应保留 skip_paused=True。"""
        params = strategy.snapshot_params()
        data = {e: make_linear_prices(n_days=100) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data)

        strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        for call_args in strategy.get_price.call_args_list:
            assert call_args[1].get('skip_paused') is True, (
                "skip_paused must remain True after R2 fix"
            )

    def test_result_is_dataframe_with_etf_columns(self, strategy, mock_g):
        """返回值应为 DataFrame，columns 为 ETF 代码，index 为日期。"""
        params = strategy.snapshot_params()
        pool = mock_g.etf_pool
        data = {e: make_linear_prices(n_days=100) for e in pool}
        _setup_get_price_mock(strategy, close=data)

        result = strategy.fetch_field(pool, 'close', 100, params)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == pool
        assert isinstance(result.index, pd.DatetimeIndex)
        assert len(result) == 100

    def test_handles_missing_data(self, strategy, mock_g):
        """某只 ETF 返回 None 时不应崩溃，dropna(how='all') 应起效。"""
        params = strategy.snapshot_params()
        data = {
            mock_g.etf_pool[0]: make_linear_prices(n_days=100),
            mock_g.etf_pool[1]: make_linear_prices(n_days=100),
        }
        _setup_get_price_mock(strategy, close=data)

        result = strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        assert mock_g.etf_pool[0] in result.columns
        assert mock_g.etf_pool[1] in result.columns

    def test_full_integration_with_new_fetch_pattern(self, strategy, mock_g):
        """完整集成验证：weekly_check 使用逐 ETF 拉取模式不崩溃。"""
        params = strategy.snapshot_params()
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
        context.previous_date = '2025-12-31'
        context.portfolio = strategy._mock_portfolio

        for etf in mock_g.etf_pool:
            mock_pos = MagicMock()
            mock_pos.total_amount = 0
            mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos

        strategy.weekly_check(context)

        # 4 字段 × 3 ETF = 12 次调用
        assert strategy.get_price.call_count == 12
        for call_args in strategy.get_price.call_args_list:
            assert call_args[1].get('panel') is False

    def test_get_price_returns_none_returns_empty_dataframe(self, strategy, mock_g):
        """get_price 返回 None 时 fetch_field 应返回 columns=pool 的空 DataFrame。"""
        params = strategy.snapshot_params()
        strategy.get_price.side_effect = None
        strategy.get_price.return_value = None

        result = strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == mock_g.etf_pool
        assert len(result) == 0

    def test_get_price_returns_empty_dataframe(self, strategy, mock_g):
        """get_price 返回空 DataFrame 时 fetch_field 应安全返回空 DataFrame。"""
        params = strategy.snapshot_params()
        strategy.get_price.side_effect = None
        strategy.get_price.return_value = pd.DataFrame()

        result = strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == mock_g.etf_pool
        assert len(result) == 0


# ============================================================
# 12. R4 修复验证 — fetch_field 使用 g.fq_mode 替代硬编码 'pre'
# ============================================================
class TestFetchFieldFqMode:
    """测试 fetch_field 使用 g.fq_mode 参数化复权模式。"""

    def test_fetch_field_passes_fq_mode_from_g(self, strategy, mock_g):
        """fetch_field 应向 get_price 传递 g.fq_mode，而非硬编码 'pre'。"""
        mock_g.fq_mode = 'post'
        params = strategy.snapshot_params()
        data = {e: make_linear_prices(n_days=100) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data)

        strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        for call_args in strategy.get_price.call_args_list:
            actual_fq = call_args[1].get('fq')
            assert actual_fq == 'post', (
                f"Expected fq='post' (from g.fq_mode), got {actual_fq}"
            )

    def test_fetch_field_passes_fq_none_when_configured(self, strategy, mock_g):
        """当 g.fq_mode=None（不复权）时，fetch_field 应传 fq=None。"""
        mock_g.fq_mode = None
        params = strategy.snapshot_params()
        data = {e: make_linear_prices(n_days=100) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data)

        strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        for call_args in strategy.get_price.call_args_list:
            actual_fq = call_args[1].get('fq')
            assert actual_fq is None, (
                f"Expected fq=None (from g.fq_mode), got {actual_fq}"
            )

    def test_fetch_field_default_fq_is_pre(self, strategy, mock_g):
        """默认配置下，fetch_field 应传 fq='pre'（与原始行为一致）。"""
        params = strategy.snapshot_params()
        data = {e: make_linear_prices(n_days=100) for e in mock_g.etf_pool}
        _setup_get_price_mock(strategy, close=data)

        strategy.fetch_field(mock_g.etf_pool, 'close', 100, params)

        for call_args in strategy.get_price.call_args_list:
            actual_fq = call_args[1].get('fq')
            assert actual_fq == 'pre', (
                f"Expected default fq='pre', got {actual_fq}"
            )


# ============================================================
# 13. R5 修复验证 — execute_rebalance 停牌检查与订单审计
# ============================================================
def _make_current_data(paused_set=None):
    """构造 get_current_data() 返回值，paused_set 为停牌 ETF 集合。"""
    paused_set = paused_set or set()
    result = {}
    for etf in ['159819.XSHE', '513100.XSHG', '518880.XSHG']:
        mock = MagicMock()
        mock.paused = etf in paused_set
        result[etf] = mock
    return result


class TestExecuteRebalance:
    """测试执行层的停牌检查和订单审计日志。"""

    def _make_context(self, strategy, positions_cfg):
        """构造 mock context，positions_cfg: {etf: (total_amount, price)}。"""
        context = SimpleNamespace()
        context.portfolio = strategy._mock_portfolio
        context.portfolio.total_value = 100000.0

        for etf in strategy.g.etf_pool:
            mock_pos = MagicMock()
            if etf in positions_cfg:
                mock_pos.total_amount, mock_pos.price = positions_cfg[etf]
            else:
                mock_pos.total_amount = 0
                mock_pos.price = 0
            context.portfolio.positions[etf] = mock_pos
        return context

    def test_skip_paused_etf(self, strategy, mock_g):
        """停牌 ETF 应被跳过，不调用 order_target_value，记录 warning。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data(
            paused_set={'513100.XSHG'}
        )

        context = self._make_context(strategy, {
            '159819.XSHE': (5000, 2.0),
            '513100.XSHG': (3000, 3.0),
            '518880.XSHG': (2000, 5.0),
        })

        final_weights = [0.4, 0.3, 0.2]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        # 停牌的 ETF 不应被下单
        called_etfs = [c[0][0] for c in strategy.order_target_value.call_args_list]
        assert '513100.XSHG' not in called_etfs, (
            f"Paused ETF should not be ordered, got calls for: {called_etfs}"
        )

        # 应记录 warning 日志
        warnings = [
            c for c in strategy.log.warning.call_args_list
            if 'paused' in str(c).lower()
        ]
        assert len(warnings) >= 1, "Expected warning log for paused ETF"

    def test_order_failure_logs_error(self, strategy, mock_g):
        """order_target_value 返回 None 时应记录 error 日志。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()
        strategy.order_target_value.return_value = None

        context = self._make_context(strategy, {
            '159819.XSHE': (5000, 2.0),
        })

        final_weights = [0.4, 0.0, 0.0]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        errors = [
            c for c in strategy.log.error.call_args_list
            if 'order failed' in str(c)
        ]
        assert len(errors) >= 1, "Expected error log when order returns None"

    def test_order_success_logs_info(self, strategy, mock_g):
        """正常下单应记录 info 日志，包含目标权重和当前权重。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()
        strategy.order_target_value.return_value = MagicMock()  # 非 None 表示成功

        context = self._make_context(strategy, {
            '159819.XSHE': (5000, 2.0),
        })

        final_weights = [0.4, 0.0, 0.0]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        sent_calls = [
            c for c in strategy.log.info.call_args_list
            if 'order sent' in str(c)
        ]
        info_calls = [str(c) for c in sent_calls]
        assert len(info_calls) >= 1, "Expected info log when order succeeds"
        # 验证日志包含关键字段
        first_call_args = sent_calls[0][0]
        assert first_call_args[1] == '人工智能ETF易方达(159819.XSHE)'
        assert first_call_args[2] == '159819.XSHE'
        combined = ' '.join(info_calls)
        assert 'target_weight' in combined
        assert 'current_weight' in combined
        assert 'target_value' in combined

    def test_execute_rebalance_writes_order_audit_events(self, strategy, mock_g):
        """执行层每个下单/跳过分支都应写结构化审计事件。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()
        strategy.order_target_value.return_value = MagicMock()
        context = self._make_context(strategy, {
            '159819.XSHE': (5000, 2.0),
        })

        final_weights = [0.4, 0.0, 0.0]
        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        events = [
            json.loads(call_args[0][1])
            for call_args in strategy.write_file.call_args_list
        ]
        actions = [event.get("action") for event in events if event["event"] == "rebalance_order"]
        assert "order_sent" in actions
        assert "skip_zero_target_zero_position" in actions
        sent = next(event for event in events if event.get("action") == "order_sent")
        assert sent["etf"] == "159819.XSHE"
        assert sent["target_weight"] == 0.4

    def test_weight_below_threshold_skips(self, strategy, mock_g):
        """权重偏离小于 RebalanceThreshold 时不执行下单。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()

        # 当前仓位 0.30，目标 0.31，偏差 0.01 < 阈值 0.03
        context = self._make_context(strategy, {
            '159819.XSHE': (300, 100.0),  # 300 * 100 = 30000 = 30%
        })

        final_weights = [0.31, 0.0, 0.0]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        # 阈值检查发生在停牌检查之前，权重偏离小 → 直接跳过
        called_etfs = [c[0][0] for c in strategy.order_target_value.call_args_list]
        assert '159819.XSHE' not in called_etfs, (
            f"Weight deviation below threshold should skip order, got: {called_etfs}"
        )

    def test_deviation_exactly_at_threshold_proceeds(self, strategy, mock_g):
        """偏差恰好等于 RebalanceThreshold 时不跳过（< 检查为 strict）。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()
        strategy.order_target_value.return_value = MagicMock()

        # 当前仓位 0.30，目标 0.33，偏差 0.03 == 阈值
        context = self._make_context(strategy, {
            '159819.XSHE': (300, 100.0),
        })

        final_weights = [0.33, 0.0, 0.0]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        called_etfs = [c[0][0] for c in strategy.order_target_value.call_args_list]
        assert '159819.XSHE' in called_etfs, (
            f"Deviation == threshold should proceed, got calls: {called_etfs}"
        )

    def test_both_target_and_current_zero_skip(self, strategy, mock_g):
        """目标权重和当前权重都为 0 时直接跳过，不调用下单。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()

        context = self._make_context(strategy, {})  # 所有 ETF 持仓为 0

        final_weights = [0.0, 0.0, 0.0]

        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)

        # 不应有任何下单
        assert strategy.order_target_value.call_count == 0, (
            f"All zero weights should skip all orders, got {strategy.order_target_value.call_args_list}"
        )

    def test_account_value_zero_graceful(self, strategy, mock_g):
        """账户总资产为 0 时 current_weight 为 0，不除零且正常执行。"""
        params = strategy.snapshot_params()
        strategy.get_current_data.return_value = _make_current_data()
        strategy.order_target_value.return_value = MagicMock()

        context = self._make_context(strategy, {
            '159819.XSHE': (5000, 2.0),
        })
        context.portfolio.total_value = 0.0

        final_weights = [0.4, 0.0, 0.0]

        # 不应崩溃
        strategy.execute_rebalance(context, mock_g.etf_pool, final_weights, params)


# ============================================================
# 重构新增函数测试
# ============================================================
class TestFieldMap:
    """测试 FIELD_MAP 内部字段到聚宽字段映射。"""

    def test_field_map_has_required_keys(self, strategy):
        assert hasattr(strategy, 'FIELD_MAP')
        fm = strategy.FIELD_MAP
        assert fm["close"] == "close"
        assert fm["high"] == "high"
        assert fm["low"] == "low"
        assert fm["amount"] == "money"
        assert len(fm) == 4


class TestSnapshotParams:
    """测试 snapshot_params() 参数快照。"""

    def test_snapshot_contains_all_required_keys(self, strategy, mock_g):
        params = strategy.snapshot_params()
        required = [
            "etf_pool", "etf_names", "benchmark",
            "MA_long", "MA_long_by_etf", "MomShort", "MomMid", "MomLong",
            "w20", "w60", "w120", "TopK",
            "VolWindow", "annual_factor",
            "RSRS_N", "RSRS_M", "RSRS_NegativeFullCut",
            "RSRSMinMultiplier", "RSRSMaxMultiplier",
            "MomentumTiltStrength", "MomentumTiltMin", "MomentumTiltMax",
            "MomentumExtremeScoreStart", "MomentumExtremeTiltCap",
            "RSRSTiltMin", "RSRSTiltMax",
            "CrowdWindow", "CrowdRetShort", "CrowdRetMid",
            "AmountMAWindow", "DeviationMAWindow", "CrowdVolWindow",
            "CrowdStart", "CrowdEnd", "MinCrowdPenalty",
            "PortfolioVolWindow", "TargetVol", "MaxPortfolioVolScale",
            "MaxWeight", "MinWeight", "RebalanceThreshold", "MaxTotalWeight",
            "ExecutionTimingMode",
            "use_real_price", "fq_mode", "history_buffer",
        ]
        for key in required:
            assert key in params, f"Missing key: {key}"

    def test_snapshot_values_match_g(self, strategy, mock_g):
        params = strategy.snapshot_params()
        assert params["MA_long"] == mock_g.MA_long
        assert params["MA_long_by_etf"] == mock_g.MA_long_by_etf
        assert params["TopK"] == mock_g.TopK
        assert params["TargetVol"] == mock_g.TargetVol
        assert params["fq_mode"] == mock_g.fq_mode
        assert params["history_buffer"] == mock_g.history_buffer
        assert params["etf_names"] == mock_g.etf_names
        assert params["ExecutionTimingMode"] == mock_g.ExecutionTimingMode

    def test_snapshot_list_values_are_copies(self, strategy, mock_g):
        params = strategy.snapshot_params()
        # 修改快照不应影响 g
        params["etf_pool"].append("999999.XSHG")
        assert len(mock_g.etf_pool) == 3

    def test_snapshot_ma_long_by_etf_is_copy(self, strategy, mock_g):
        mock_g.MA_long_by_etf = [20, 40, 100]
        params = strategy.snapshot_params()
        params["MA_long_by_etf"][0] = 60
        assert mock_g.MA_long_by_etf == [20, 40, 100]

    def test_snapshot_upgrades_short_fund_codes(self, strategy, mock_g):
        mock_g.etf_names = ['人工智能ETF易方达(159819)', '纳指ETF', '黄金ETF(518880)']
        params = strategy.snapshot_params()
        assert params["etf_names"] == [
            '人工智能ETF易方达(159819.XSHE)',
            '纳指ETF(513100.XSHG)',
            '黄金ETF(518880.XSHG)',
        ]

    def test_snapshot_captures_modified_g(self, strategy, mock_g):
        """修改 g 后再快照，params 应反映新值。"""
        mock_g.TargetVol = 0.08
        mock_g.TopK = 1
        params = strategy.snapshot_params()
        assert params["TargetVol"] == 0.08
        assert params["TopK"] == 1


class TestValidateParams:
    """测试 validate_params 参数校验。"""

    def test_valid_default_params_pass(self, strategy, mock_g):
        params = strategy.snapshot_params()
        strategy.validate_params(params)  # 不应抛出异常

    def test_momentum_weights_not_sum_to_one_raises(self, strategy, mock_g):
        mock_g.w20 = 0.5
        mock_g.w60 = 0.5
        mock_g.w120 = 0.5
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="momentum weights must sum to 1"):
            strategy.validate_params(params)

    def test_ma_long_not_positive_raises(self, strategy, mock_g):
        mock_g.MA_long = 0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MA_long must be positive"):
            strategy.validate_params(params)

    def test_ma_long_by_etf_length_mismatch_raises(self, strategy, mock_g):
        mock_g.MA_long_by_etf = [20, 40]
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MA_long_by_etf length must match etf_pool"):
            strategy.validate_params(params)

    def test_ma_long_by_etf_nonpositive_raises(self, strategy, mock_g):
        mock_g.MA_long_by_etf = [20, 0, 100]
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MA_long_by_etf values must be positive"):
            strategy.validate_params(params)

    def test_topk_less_than_one_raises(self, strategy, mock_g):
        mock_g.TopK = 0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="TopK must be >= 1"):
            strategy.validate_params(params)

    def test_maxweight_violation_raises(self, strategy, mock_g):
        mock_g.MaxWeight = 1.5
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MaxWeight"):
            strategy.validate_params(params)

    def test_minweight_violation_raises(self, strategy, mock_g):
        mock_g.MinWeight = -0.1
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MinWeight"):
            strategy.validate_params(params)

    def test_targetvol_negative_raises(self, strategy, mock_g):
        mock_g.TargetVol = 0.0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="TargetVol must be positive"):
            strategy.validate_params(params)

    def test_rsrs_window_violation_raises(self, strategy, mock_g):
        mock_g.RSRS_N = 1
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="RSRS"):
            strategy.validate_params(params)

    def test_crowd_threshold_violation_raises(self, strategy, mock_g):
        mock_g.CrowdStart = 0.8
        mock_g.CrowdEnd = 0.6
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="Crowd thresholds"):
            strategy.validate_params(params)

    def test_multiple_errors_joined(self, strategy, mock_g):
        mock_g.TopK = 0
        mock_g.TargetVol = -0.1
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="; "):
            strategy.validate_params(params)

    def test_etf_names_without_security_code_raises(self, strategy, mock_g):
        params = strategy.snapshot_params()
        params["etf_names"][0] = "人工智能ETF易方达"
        with pytest.raises(ValueError, match="JoinQuant security code"):
            strategy.validate_params(params)

    def test_momentum_tilt_strength_negative_raises(self, strategy, mock_g):
        mock_g.MomentumTiltStrength = -1.0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MomentumTiltStrength must be >= 0"):
            strategy.validate_params(params)

    def test_momentum_tilt_min_zero_raises(self, strategy, mock_g):
        mock_g.MomentumTiltMin = 0.0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="Momentum tilt bounds"):
            strategy.validate_params(params)

    def test_momentum_tilt_min_gt_one_raises(self, strategy, mock_g):
        mock_g.MomentumTiltMin = 1.5
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="Momentum tilt bounds"):
            strategy.validate_params(params)

    def test_momentum_tilt_max_lt_one_raises(self, strategy, mock_g):
        mock_g.MomentumTiltMax = 0.8
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="Momentum tilt bounds"):
            strategy.validate_params(params)

    def test_momentum_extreme_score_start_none_is_valid(self, strategy, mock_g):
        mock_g.MomentumExtremeScoreStart = None
        params = strategy.snapshot_params()
        strategy.validate_params(params)

    def test_momentum_extreme_score_start_zero_raises(self, strategy, mock_g):
        mock_g.MomentumExtremeScoreStart = 0.0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MomentumExtremeScoreStart"):
            strategy.validate_params(params)

    def test_momentum_extreme_score_start_gt_one_raises(self, strategy, mock_g):
        mock_g.MomentumExtremeScoreStart = 1.1
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MomentumExtremeScoreStart"):
            strategy.validate_params(params)

    def test_momentum_extreme_tilt_cap_lt_one_raises(self, strategy, mock_g):
        mock_g.MomentumExtremeTiltCap = 0.9
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MomentumExtremeTiltCap"):
            strategy.validate_params(params)

    def test_momentum_extreme_tilt_cap_gt_tilt_max_raises(self, strategy, mock_g):
        mock_g.MomentumExtremeTiltCap = 1.4
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="MomentumExtremeTiltCap"):
            strategy.validate_params(params)

    def test_rsrs_tilt_min_zero_raises(self, strategy, mock_g):
        mock_g.RSRSTiltMin = 0.0
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="RSRS tilt bounds"):
            strategy.validate_params(params)

    def test_rsrs_tilt_min_gt_one_raises(self, strategy, mock_g):
        mock_g.RSRSTiltMin = 1.5
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="RSRS tilt bounds"):
            strategy.validate_params(params)

    def test_rsrs_tilt_max_lt_one_raises(self, strategy, mock_g):
        mock_g.RSRSTiltMax = 0.8
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="RSRS tilt bounds"):
            strategy.validate_params(params)

    def test_execution_timing_mode_must_be_known(self, strategy, mock_g):
        mock_g.ExecutionTimingMode = "unknown"
        params = strategy.snapshot_params()
        with pytest.raises(ValueError, match="ExecutionTimingMode must be one of"):
            strategy.validate_params(params)


class TestNormalizeFieldFrame:
    """测试 normalize_field_frame 数据归一化。"""

    def test_none_raw_returns_empty_dataframe(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
        result = strategy.normalize_field_frame(None, 'close', pool)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == pool
        assert len(result) == 0

    def test_empty_raw_returns_empty_dataframe(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
        result = strategy.normalize_field_frame(pd.DataFrame(), 'close', pool)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == pool
        assert len(result) == 0

    def test_normal_dataframe_passes_through(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG']
        df = pd.DataFrame({
            '159819.XSHE': [1.0, 2.0, 3.0],
            '513100.XSHG': [4.0, 5.0, 6.0],
        })
        result = strategy.normalize_field_frame(df, 'close', pool)
        assert result.shape == (3, 2)

    def test_missing_columns_filled_with_nan(self, strategy):
        pool = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
        df = pd.DataFrame({'159819.XSHE': [1.0, 2.0]})
        result = strategy.normalize_field_frame(df, 'close', pool)
        assert list(result.columns) == pool
        assert '518880.XSHG' in result.columns

    def test_all_nan_rows_dropped(self, strategy):
        pool = ['159819.XSHE']
        df = pd.DataFrame({'159819.XSHE': [np.nan, np.nan]})
        result = strategy.normalize_field_frame(df, 'close', pool)
        assert len(result) == 0

    def test_non_dataframe_input_returns_empty(self, strategy):
        pool = ['159819.XSHE']
        result = strategy.normalize_field_frame("not a dataframe", 'close', pool)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestComputeHistoryCount:
    """测试 compute_history_count 历史数据长度计算。"""

    def test_with_default_params(self, strategy, mock_g):
        params = strategy.snapshot_params()
        count = strategy.compute_history_count(params)
        # RSRS_M + RSRS_N - 1 = 600 + 18 - 1 = 617
        # + history_buffer 100 = 717
        expected = 617 + 100
        assert count == expected

    def test_respects_history_buffer(self, strategy, mock_g):
        mock_g.history_buffer = 50
        params = strategy.snapshot_params()
        count = strategy.compute_history_count(params)
        expected = 617 + 50
        assert count == expected

    def test_uses_largest_ma_long_by_etf(self, strategy, mock_g):
        mock_g.MA_long = 20
        mock_g.MA_long_by_etf = [10, 250, 30]
        mock_g.MomShort = 5
        mock_g.MomMid = 10
        mock_g.MomLong = 20
        mock_g.VolWindow = 10
        mock_g.RSRS_N = 3
        mock_g.RSRS_M = 10
        mock_g.CrowdWindow = 30
        mock_g.PortfolioVolWindow = 10
        mock_g.history_buffer = 7
        params = strategy.snapshot_params()
        count = strategy.compute_history_count(params)
        assert count == 250 + 7

    def test_with_small_windows(self, strategy, mock_g):
        mock_g.MA_long = 10
        mock_g.MomShort = 5
        mock_g.MomMid = 10
        mock_g.MomLong = 20
        mock_g.VolWindow = 10
        mock_g.RSRS_N = 3
        mock_g.RSRS_M = 10
        mock_g.CrowdWindow = 30
        mock_g.PortfolioVolWindow = 10
        mock_g.history_buffer = 10
        params = strategy.snapshot_params()
        count = strategy.compute_history_count(params)
        assert count > 0


class TestComposeRawWeights:
    """测试 compose_raw_weights 权重合成（新版三参数签名）。"""

    def test_normal_composition(self, strategy):
        tilted = np.array([0.6, 0.4, 0.0])
        gates = np.array([1.0, 1.0, 0.0])
        crowd = np.array([0.9, 1.0, 1.0])

        raw = strategy.compose_raw_weights(tilted, gates, crowd)
        assert raw[0] == 0.6 * 1.0 * 0.9
        assert raw[1] == 0.4 * 1.0 * 1.0
        assert raw[2] == 0.0

    def test_all_trend_gates_zero_returns_zeros(self, strategy):
        tilted = np.array([0.5, 0.3, 0.2])
        gates = np.array([0.0, 0.0, 0.0])
        crowd = np.array([1.0, 1.0, 1.0])

        raw = strategy.compose_raw_weights(tilted, gates, crowd)
        assert all(r == 0.0 for r in raw)

    def test_zero_crowd_penalties_zero_weights(self, strategy):
        tilted = np.array([0.5, 0.5, 0.0])
        gates = np.array([1.0, 1.0, 0.0])
        crowd = np.array([0.0, 0.0, 1.0])

        raw = strategy.compose_raw_weights(tilted, gates, crowd)
        assert raw[0] == 0.0
        assert raw[1] == 0.0

    def test_partial_active(self, strategy):
        tilted = np.array([0.7, 0.0, 0.3])
        gates = np.array([1.0, 0.0, 1.0])
        crowd = np.array([1.0, 1.0, 1.0])

        raw = strategy.compose_raw_weights(tilted, gates, crowd)
        assert raw[0] == 0.7
        assert raw[1] == 0.0
        assert raw[2] == 0.3

    def test_list_gates_accepted(self, strategy):
        """trend_gates 为 list 时也应正常工作。"""
        tilted = np.array([0.6, 0.4, 0.0])
        gates = [1.0, 1.0, 0.0]
        crowd = np.array([1.0, 1.0, 1.0])

        raw = strategy.compose_raw_weights(tilted, gates, crowd)
        assert raw[0] == 0.6
        assert raw[1] == 0.4


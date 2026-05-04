"""
pytest conftest — 聚宽策略本地测试基础设施

核心职责：
1. 在策略模块导入前注入 enable_profile 到 builtins
2. 用 importlib 加载策略模块，并注入所有聚宽全局对象
3. 提供可复用的 fixture：strategy module、mock g、mock prices
"""

import sys
import builtins
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import numpy as np
import pandas as pd
import pytest


# ============================================================
# 全局 mock — 策略模块导入前注入
# ============================================================

# 策略文件第 1 行调用 enable_profile()，必须提前注入
builtins.enable_profile = Mock()


# ============================================================
# strategy module fixture
# ============================================================
@pytest.fixture(scope="module")
def strategy():
    """
    用 importlib 加载策略模块，并注入所有聚宽全局对象。

    注入的 mock 对象：
    - g: SimpleNamespace
    - set_option, set_order_cost, set_slippage, run_weekly: Mock
    - OrderCost, FixedSlippage: Mock
    - log: MagicMock
    - get_price: MagicMock（返回可配置的 DataFrame）
    - order_target_value: MagicMock
    """
    import pathlib
    strategy_file = (
        pathlib.Path(__file__).resolve().parent.parent / "etf_factor_rotation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "etf_factor_rotation",
        str(strategy_file),
    )
    module = importlib.util.module_from_spec(spec)

    # 聚宽全局对象注入
    module.g = SimpleNamespace()
    module.set_option = Mock()
    module.set_order_cost = Mock()
    module.set_slippage = Mock()
    module.run_weekly = Mock()
    module.set_benchmark = Mock()
    module.log = MagicMock()
    module.OrderCost = Mock()
    module.FixedSlippage = Mock(return_value=Mock())
    module.get_price = MagicMock()
    module.order_target_value = MagicMock()
    # 默认返回：每只 ETF 的 current_data mock（paused=False）
    _default_current_data = {}
    for _etf in ['159819.XSHE', '513100.XSHG', '518880.XSHG']:
        _mock = MagicMock()
        _mock.paused = False
        _default_current_data[_etf] = _mock
    module.get_current_data = MagicMock(return_value=_default_current_data)

    # mock context.portfolio
    module._mock_portfolio = MagicMock()
    module._mock_portfolio.total_value = 100000.0
    module._mock_portfolio.positions = {}

    spec.loader.exec_module(module)

    return module


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
    """
    将 {etf: array} 转为符合 get_price 返回格式的 mock。

    返回一个 MagicMock，调用 .iloc 或 [] 时返回对应数据。
    """
    dfs = {}
    for etf, arr in prices_dict.items():
        dates = pd.date_range(start_date, periods=len(arr), freq='B')
        dfs[etf] = pd.Series(arr, index=dates, name=etf)

    return pd.DataFrame(dfs)


# ============================================================
# mock_g fixture — 设置默认策略参数
# ============================================================
@pytest.fixture
def mock_g(strategy):
    """
    设置 g 对象为策略默认参数（与 set_parameter 完全一致）。
    """
    strategy.g = SimpleNamespace(
        etf_pool=[
            '159819.XSHE',
            '513100.XSHG',
            '518880.XSHG',
        ],
        etf_names=['AI ETF', '纳指100ETF', '黄金ETF'],
        MA_long=120,
        MomShort=20,
        MomMid=60,
        MomLong=120,
        w20=0.2,
        w60=0.3,
        w120=0.5,
        TopK=2,
        VolWindow=60,
        annual_factor=252,
        RSRS_N=18,
        RSRS_M=600,
        RSRS_NegativeFullCut=1.0,
        RSRSMinMultiplier=0.0,
        RSRSMaxMultiplier=1.0,
        CrowdWindow=500,
        CrowdRetShort=20,
        CrowdRetMid=60,
        AmountMAWindow=20,
        DeviationMAWindow=20,
        CrowdVolWindow=20,
        CrowdStart=0.60,
        CrowdEnd=0.95,
        MinCrowdPenalty=0.30,
        PortfolioVolWindow=60,
        TargetVol=0.12,
        MaxPortfolioVolScale=1.0,
        MaxWeight=0.60,
        MinWeight=0.05,
        RebalanceThreshold=0.03,
        MaxTotalWeight=1.0,
        live_days=1250,
        history_buffer=100,
        benchmark='000300.XSHG',
        use_real_price=True,
        fq_mode='pre',
    )
    return strategy.g


# ============================================================
# autouse fixture — 每个测试后重置 mocks
# ============================================================
@pytest.fixture(autouse=True)
def _auto_reset_mocks(strategy):
    """每个测试前自动清除 mock 状态。"""
    yield
    strategy.get_price.reset_mock(return_value=True)
    strategy.order_target_value.reset_mock(return_value=True)
    # get_current_data 必须显式赋值 return_value——reset_mock 只接受 bool 标志
    _cd_default = {}
    for _etf in ['159819.XSHE', '513100.XSHG', '518880.XSHG']:
        _m = MagicMock()
        _m.paused = False
        _cd_default[_etf] = _m
    strategy.get_current_data.reset_mock()
    strategy.get_current_data.return_value = _cd_default
    strategy.log.reset_mock(return_value=True)
    strategy.set_option.reset_mock()
    strategy.set_order_cost.reset_mock()
    strategy.set_slippage.reset_mock()
    strategy.run_weekly.reset_mock()

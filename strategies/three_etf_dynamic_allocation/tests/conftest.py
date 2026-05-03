"""
pytest conftest — 聚宽策略本地测试基础设施

核心职责：
1. 在策略模块导入前注入 jqlib mock（通过 sys.modules）
2. 注入 enable_profile 到 builtins（策略第 1 行就调用）
3. 用 importlib 加载策略模块，并注入所有聚宽全局对象
4. 提供可复用的 fixture：strategy module、mock g、mock BIAS/ROC
"""

import sys
import builtins
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


# ============================================================
# 全局 mock 对象 — 在策略模块导入前注册到 sys.modules
# ============================================================

MOCK_BIAS = MagicMock(return_value=({}, {}, {}))
MOCK_ROC = MagicMock(return_value={})

_mock_jqlib_ta = MagicMock()
_mock_jqlib_ta.BIAS = MOCK_BIAS
_mock_jqlib_ta.ROC = MOCK_ROC

_mock_jqlib = MagicMock()
_mock_jqlib.technical_analysis = _mock_jqlib_ta

sys.modules['jqlib'] = _mock_jqlib
sys.modules['jqlib.technical_analysis'] = _mock_jqlib_ta

# 策略文件第 1 行调用 enable_profile()，必须提前注入
builtins.enable_profile = Mock()


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


def make_v_shape_prices(n_days=100):
    """生成先跌后涨的 V 形价格序列。"""
    half = n_days // 2
    down = np.arange(1.0, 0.5, -0.5 / half)[:half]
    up = np.arange(0.5, 1.0, 0.5 / (n_days - half))[:n_days - half]
    return np.concatenate([down, up])


# ============================================================
# strategy module fixture
# ============================================================

@pytest.fixture(scope="module")
def strategy():
    """
    用 importlib 加载策略模块，并注入所有聚宽全局对象。

    注入的 mock 对象：
    - g: SimpleNamespace（由各测试通过 setup_g fixture 或直接赋值配置）
    - set_option, set_order_cost, set_slippage, run_weekly, set_benchmark: Mock
    - OrderCost, FixedSlippage: Mock
    - log: MagicMock（支持 .info(), .error(), .warning()）
    - get_price, order_target_value: MagicMock（可配置返回值）
    """
    import pathlib
    strategy_file = pathlib.Path(__file__).resolve().parent.parent / "three_etf_dynamic_allocation.py"
    spec = importlib.util.spec_from_file_location(
        "three_etf_dynamic_allocation",
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

    # 执行模块（此时 enable_profile 和 jqlib imports 会命中我们的 mock）
    spec.loader.exec_module(module)

    # 重置 BIAS/ROC mock 状态（清除 import 时的调用记录）
    MOCK_BIAS.reset_mock()
    MOCK_ROC.reset_mock()

    return module


# ============================================================
# 参数化 fixtures
# ============================================================

@pytest.fixture
def mock_g(strategy):
    """
    设置 g 对象为策略默认参数（与 set_parameter 完全一致）。

    每个测试函数调用此 fixture 后，strategy.g 已被重置为默认值。
    """
    strategy.g = SimpleNamespace(
        etf_pool=[
            '518880.XSHG',
            '159819.XSHE',
            '513100.XSHG',
        ],
        etf_names=['黄金ETF', 'AI ETF', '纳指100ETF'],
        volatility_window=60,
        annual_factor=252,
        # 黄金因子权重
        gold_trend_w=0.5,
        gold_rs_w=0.3,
        gold_riskoff_w=0.2,
        # AI 因子权重
        ai_momentum_w=0.45,
        ai_trend_w=0.25,
        ai_volpenalty_w=0.20,
        ai_drawdown_w=0.10,
        # 纳指因子权重
        nasdaq_momentum_w=0.40,
        nasdaq_trend_w=0.20,
        nasdaq_riskon_w=0.20,
        nasdaq_volpenalty_w=0.20,
        # 因子计算窗口
        trend_ma_window=20,
        momentum_window_short=20,
        momentum_window_long=60,
        vol_window_short=20,
        vol_window_long=60,
        drawdown_window=60,
        # 核心公式参数
        k=0.3,
        # 权重约束
        weight_bounds=[
            (0.10, 0.60),
            (0.10, 0.50),
            (0.10, 0.60),
        ],
        max_weight_change=0.10,
        live_days=100,
        benchmark='000300.XSHG',
    )
    return strategy.g


@pytest.fixture(autouse=True)
def _auto_reset_bias_roc():
    """
    autouse fixture：每个测试前自动清除 BIAS/ROC mock 的 side_effect 和 return_value。

    关键点：MagicMock.reset_mock() 默认不清除 side_effect 和 return_value，
    需要通过参数显式指定 reset_mock(side_effect=True, return_value=True)。
    """
    MOCK_BIAS.reset_mock(side_effect=True, return_value=True)
    MOCK_ROC.reset_mock(side_effect=True, return_value=True)
    # 重置调用的默认返回值
    MOCK_BIAS.return_value = ({}, {}, {})
    MOCK_ROC.return_value = {}


@pytest.fixture
def reset_mocks(strategy):
    """在每个测试前重置所有 mock 对象的状态（包括 side_effect 清除）。"""
    MOCK_BIAS.reset_mock(side_effect=True, return_value=True)
    MOCK_ROC.reset_mock(side_effect=True, return_value=True)
    MOCK_BIAS.return_value = ({}, {}, {})
    MOCK_ROC.return_value = {}
    strategy.get_price.reset_mock(side_effect=True, return_value=True)
    strategy.order_target_value.reset_mock(side_effect=True, return_value=True)
    strategy.log.reset_mock(side_effect=True, return_value=True)
    strategy.set_option.reset_mock(side_effect=True, return_value=True)
    strategy.set_order_cost.reset_mock(side_effect=True, return_value=True)
    strategy.set_slippage.reset_mock(side_effect=True, return_value=True)
    strategy.run_weekly.reset_mock(side_effect=True, return_value=True)
    return strategy

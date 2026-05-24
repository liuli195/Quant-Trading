import builtins
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def strategy(monkeypatch):
    monkeypatch.setattr(builtins, "enable_profile", Mock(), raising=False)
    monkeypatch.setitem(sys.modules, "FeishuRelayTools", MagicMock())

    strategy_file = Path(__file__).resolve().parents[1] / "feishu_relay_smoke.py"
    spec = importlib.util.spec_from_file_location("feishu_relay_smoke_under_test", strategy_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.g = SimpleNamespace(feishu_smoke_ordered=False)
    module.log = MagicMock()
    module.order_target_value = MagicMock()
    return module


def test_smoke_order_retries_when_order_submission_fails(strategy):
    strategy.order_target_value.return_value = None

    strategy.smoke_order(SimpleNamespace())

    strategy.order_target_value.assert_called_once_with("510300.XSHG", 10000)
    assert strategy.g.feishu_smoke_ordered is False


def test_smoke_order_marks_ordered_after_success(strategy):
    strategy.order_target_value.return_value = object()

    strategy.smoke_order(SimpleNamespace())

    assert strategy.g.feishu_smoke_ordered is True

    strategy.order_target_value.reset_mock()
    strategy.smoke_order(SimpleNamespace())
    strategy.order_target_value.assert_not_called()

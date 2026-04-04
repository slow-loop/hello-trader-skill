from types import SimpleNamespace

from backend2.models import AnalysisSettings, MarketConfig, Quote, WorkspaceConfig, WorkspaceRuntimeConfig
from backend2.policies import get_market_profile
from backend2.screener import run_screener


def _runtime_config() -> WorkspaceRuntimeConfig:
    return WorkspaceRuntimeConfig(
        id="test-workspace",
        name="Test Workspace",
        market=MarketConfig(profile="tw_equity"),
        workspace=WorkspaceConfig(root_dir="/tmp/test-workspace"),
        analysis=AnalysisSettings(),
    )


def test_run_screener_dispatches_tw_momentum(monkeypatch):
    snapshot = [
        {"Code": "2330", "Name": "TSMC", "TradeValue": 2_500_000_000, "Change": 20, "ClosingPrice": 1000},
        {"Code": "2454", "Name": "MTK", "TradeValue": 900_000_000, "Change": 10, "ClosingPrice": 800},
        {"Code": "0050", "Name": "ETF", "TradeValue": 5_000_000_000, "Change": 5, "ClosingPrice": 100},
    ]

    monkeypatch.setattr("backend2.screener._fetch_twse_snapshot", lambda: snapshot)
    monkeypatch.setattr("backend2.screener._enrich_tw_result", lambda *args, **kwargs: None)

    response = run_screener(_runtime_config(), get_market_profile("tw_equity"), strategy="momentum", enrich=False)

    assert response.strategy == "momentum"
    assert response.market_profile == "tw_equity"
    assert [item.symbol for item in response.items] == ["2330"]


def test_run_screener_enriches_analysis(monkeypatch):
    snapshot = [{"Code": "2330", "Name": "TSMC", "TradeValue": 2_500_000_000, "Change": 20, "ClosingPrice": 1000}]

    monkeypatch.setattr("backend2.screener._fetch_twse_snapshot", lambda: snapshot)
    monkeypatch.setattr("backend2.screener._try_fetch_tw_chips", lambda symbol: {"foreign_net_days": 3})
    monkeypatch.setattr(
        "backend2.screener.analyze_symbol",
        lambda *args, **kwargs: SimpleNamespace(
            symbol="2330.TW",
            quote=Quote(symbol="2330.TW", market_profile="tw_equity", price=1000, source="test"),
            technical_config=SimpleNamespace(outputs=["close", "volume_ratio_20"]),
            technical_analysis=SimpleNamespace(
                values={"close": 1000.0, "volume_ratio_20": 1.8},
                triggers={"momentum": ["volume_breakout_1_5x"]},
                warnings=[],
            ),
        ),
    )

    response = run_screener(_runtime_config(), get_market_profile("tw_equity"), strategy="momentum", enrich=True)

    item = response.items[0]
    assert item.analysis is not None
    assert item.analysis.metrics["volume_ratio_20"] == 1.8
    assert item.chips["foreign_net_days"] == 3


def test_run_screener_rejects_unsupported_market():
    config = WorkspaceRuntimeConfig(
        id="test-workspace",
        name="Test Workspace",
        market=MarketConfig(profile="us_equity"),
        workspace=WorkspaceConfig(root_dir="/tmp/test-workspace"),
        analysis=AnalysisSettings(),
    )

    try:
        run_screener(config, get_market_profile("us_equity"), strategy="momentum")
    except ValueError as exc:
        assert "unsupported screener strategy" in str(exc)
    else:
        raise AssertionError("expected ValueError")

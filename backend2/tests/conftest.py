import pytest
from backend2.models import (
    WorkspaceRuntimeConfig,
    MarketConfig,
    WorkspaceConfig,
    AgentConfig,
    NewsConfig,
    AnalysisSettings,
    RiskConfig,
    WatchlistConfig,
    ScheduleConfig,
)

@pytest.fixture
def mock_runtime_config():
    return WorkspaceRuntimeConfig(
        id="test-workspace",
        name="Test Workspace",
        market=MarketConfig(profile="tw_equity", benchmark_symbol="TWSE"),
        workspace=WorkspaceConfig(),
        agent=AgentConfig(),
        news=NewsConfig(),
        analysis=AnalysisSettings(),
        risk=RiskConfig(),
        watchlist=WatchlistConfig(),
        schedule=ScheduleConfig(),
    )

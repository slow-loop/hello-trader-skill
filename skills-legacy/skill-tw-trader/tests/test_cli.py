from __future__ import annotations

from unittest.mock import patch

from skill_tw_trader.cli import main


def test_market_command_uses_report_and_saves_briefing(capsys):
    report = {"date": "2026-03-26", "session": "pre_market", "market": {}, "headlines": []}
    with (
        patch("skill_tw_trader.cli.build_market_report", return_value=report) as mock_report,
        patch("skill_tw_trader.cli.save_briefing") as mock_save,
    ):
        code = main(["market", "2330"])

    captured = capsys.readouterr()
    assert code == 0
    assert "date: '2026-03-26'" in captured.out or "date: 2026-03-26" in captured.out
    mock_report.assert_called_once_with(["2330"])
    mock_save.assert_called_once_with(report, symbols=["2330"])


def test_account_command_outputs_status_yaml(capsys):
    status = {"cash": 1000000, "positions": [], "orders": [], "summary": {"account_value": 1000000}}
    with patch("skill_tw_trader.cli.build_status", return_value=status) as mock_status:
        code = main(["account"])

    captured = capsys.readouterr()
    assert code == 0
    assert "cash: 1000000" in captured.out
    mock_status.assert_called_once_with()


def test_set_exit_command_updates_order(capsys):
    with patch("skill_tw_trader.cli.update_orders", return_value="Updated 2330.TW") as mock_update:
        code = main(["set-exit", "2330.TW", "--stop-loss", "900", "--take-profit", "1050"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Updated 2330.TW" in captured.out
    mock_update.assert_called_once_with("2330.TW", stop_loss=900.0, take_profit=1050.0)

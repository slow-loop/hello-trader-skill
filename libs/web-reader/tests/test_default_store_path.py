from pathlib import Path

from web_reader.store import ReadStore, resolve_default_db_file


def test_default_store_path_is_repo_local(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WEB_READER_DB_PATH", raising=False)

    store = ReadStore()

    assert store.db_path == (tmp_path / ".web-reader" / "store.db").resolve()


def test_default_store_path_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    configured = tmp_path / "custom-cache" / "reader.db"
    monkeypatch.setenv("WEB_READER_DB_PATH", str(configured))

    assert resolve_default_db_file() == configured.resolve()

    store = ReadStore()

    assert store.db_path == configured.resolve()

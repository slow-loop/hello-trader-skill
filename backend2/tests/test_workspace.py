import pytest
import yaml
from pathlib import Path
from backend2.models import (
    WorkspaceRuntimeConfig, 
    MarketConfig, 
    WorkspaceConfig,
    WatchlistConfig,
    WatchlistItem,
    JournalEntry,
    LessonsDocument
)
from backend2.workspace import (
    load_watchlist, 
    save_watchlist, 
    upsert_watchlist_item,
    load_journal,
    append_journal_entry,
    load_lessons,
    save_lessons
)

@pytest.fixture
def temp_workspace(tmp_path: Path):
    root = tmp_path / "test_workspace"
    root.mkdir()
    
    # Create required directory structure
    (root / "data/config").mkdir(parents=True)
    (root / "data/account/journals").mkdir(parents=True)
    
    # Create minimal workspace.yaml
    workspace_yaml = {
        "id": "test-ws",
        "name": "Test Local Workspace",
        "market": {"profile": "tw_equity", "benchmark_symbol": "TWSE"},
        "workspace": {
            "root_dir": str(root),
            "account_dir": "data/account"
        }
    }
    (root / "data/config/workspace.yaml").write_text(yaml.dump(workspace_yaml))
    
    return root, WorkspaceRuntimeConfig.model_validate(workspace_yaml)

def test_watchlist_roundtrip(temp_workspace):
    root, config = temp_workspace
    
    # Initial empty watchlist
    wl = load_watchlist(config)
    assert len(wl.items) == 0
    
    # Save some items
    new_wl = WatchlistConfig(items=[
        WatchlistItem(symbol="2330", thesis="TSMC 1nm success", status="watch")
    ])
    save_watchlist(config, new_wl)
    
    # Reload and check
    wl_reloaded = load_watchlist(config)
    assert len(wl_reloaded.items) == 1
    assert wl_reloaded.items[0].symbol == "2330"
    assert wl_reloaded.items[0].thesis == "TSMC 1nm success"

def test_upsert_watchlist_item(temp_workspace):
    root, config = temp_workspace
    
    # Upsert new item
    item1 = WatchlistItem(symbol="2330", thesis="Wait", status="watch")
    upsert_watchlist_item(config, item1)
    
    wl = load_watchlist(config)
    assert len(wl.items) == 1
    assert wl.items[0].thesis == "Wait"
    
    # Update existing item (case-insensitive symbol)
    item1_v2 = WatchlistItem(symbol="2330", thesis="Go", status="watch")
    upsert_watchlist_item(config, item1_v2)
    
    wl_v2 = load_watchlist(config)
    assert len(wl_v2.items) == 1
    assert wl_v2.items[0].thesis == "Go"

def test_journal_persistence(temp_workspace):
    root, config = temp_workspace
    date_str = "2026-04-03"
    
    # Initial empty journal
    doc = load_journal(config, date_str)
    assert len(doc.entries) == 0
    
    # Append an entry
    entry = JournalEntry(type="note", notes=["Test note"])
    append_journal_entry(config, date_str, entry)
    
    # Reload and check
    doc_reloaded = load_journal(config, date_str)
    assert len(doc_reloaded.entries) == 1
    assert doc_reloaded.entries[0].notes == ["Test note"]

def test_lessons_persistence(temp_workspace):
    root, config = temp_workspace
    
    # Initial empty lessons
    doc = load_lessons(config)
    assert doc.content == ""
    
    # Save lessons
    new_doc = LessonsDocument(content="# Trade Lessons\n\n1. Be patient.")
    save_lessons(config, new_doc)
    
    # Reload and check
    doc_reloaded = load_lessons(config)
    assert doc_reloaded.content == "# Trade Lessons\n\n1. Be patient."

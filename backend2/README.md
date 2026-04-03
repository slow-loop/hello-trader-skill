# backend2

Local-first single-workspace trading backend.

## Structure

- `BACKEND2_WORKSPACE_ROOT`: selects the local workspace root
- `skills/<skill>/data/config/workspace.yaml`: workspace-owned runtime config
- `skills/<skill>/data/config/*.yaml`: strategy-owned config files
- `skills/<skill>/data/account/*`: file-backed watchlist / journals / lessons
- `data/backend2.sqlite`: mutable trading runtime state

## Run

```bash
cd backend2
uv run uvicorn backend2.main:app --reload
```

## Example endpoints

- `GET /workspace`
- `GET /account`
- `GET /overview`
- `GET /analysis/2330`
- `POST /orders`
- `GET /workspace/watchlist`
- `POST /workspace/journals/2026-04-03/entries`
- `PUT /workspace/lessons`

## Notes

- Trading state is stored in SQLite.
- Runtime and strategy config remain file-based under `skills/...`.
- Workspace state can stay file-based and be accessed through typed backend APIs.
- API is single-workspace; there is no room layer anymore.
- `tw_equity`, `us_equity`, `xstocks`, and `crypto` profiles exist.
- `xstocks` currently uses underlying equity prices for analysis, not venue-native CCXT pricing.

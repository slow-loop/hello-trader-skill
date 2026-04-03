# TW Trader Backend

A FastAPI-based backend for the TW Trader project, utilizing Supabase, APScheduler, and various financial data providers (FinMind, Fugle, yfinance).

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
cd backend
uv sync
```

## Running the Development Server

Due to the `FinMind` library's use of `nest_asyncio`, you must explicitly use the standard `asyncio` loop instead of `uvloop`.

Use the following command to start the server:

```bash
uv run uvicorn backend.main:app --reload --loop asyncio
```

## Testing

Tests are located in the root `tests/` directory (following Python best practices for `src`-layout projects).

Run the full test suite using:

```bash
uv run pytest
```

## Project Structure

- `src/backend/`: Core application package.
  - `main.py`: Entry point for the FastAPI application.
  - `core/`: Business logic, engines, and data providers.
  - `routes.py`: API endpoints.
  - `tasks.py`: Background job definitions.
- `tests/`: Unit and integration tests (organized by module).
- `pyproject.toml`: Project metadata and dependencies.

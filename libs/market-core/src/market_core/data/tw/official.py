from __future__ import annotations

import csv
import io
import json
import math
import re
import ssl
from functools import lru_cache
from statistics import median
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


TWSE_BASE_URL = "https://openapi.twse.com.tw/v1"
TPEX_BASE_URL = "https://www.tpex.org.tw/openapi/v1"
# www.twse.com.tw updates with today's data post-close; openapi.twse.com.tw lags by ~1 day
_TWSE_DAILY_ALL_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data"

_TWSE_DAILY_ALL_FIELD_MAP = {
    "日期": "Date",
    "證券代號": "Code",
    "證券名稱": "Name",
    "成交股數": "TradeVolume",
    "成交金額": "TradeValue",
    "開盤價": "OpeningPrice",
    "最高價": "HighestPrice",
    "最低價": "LowestPrice",
    "收盤價": "ClosingPrice",
    "漲跌價差": "Change",
    "成交筆數": "Transaction",
}
REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_HEADERS = {
    "User-Agent": "hello-note/0.1",
    "Accept": "application/json",
}


@lru_cache(maxsize=1)
def get_tw_daily_all() -> list[dict[str, Any]]:
    """Fetch today's full TWSE daily snapshot (all stocks, post-close).

    Uses www.twse.com.tw which updates with the current trading day's data
    after market close (~14:00–15:00 TST), unlike openapi.twse.com.tw which
    lags by one trading day.

    Returns rows with English field names matching the OpenAPI JSON schema:
    Date, Code, Name, TradeVolume, TradeValue, OpeningPrice, HighestPrice,
    LowestPrice, ClosingPrice, Change, Transaction.
    """
    request = Request(_TWSE_DAILY_ALL_URL, headers=DEFAULT_HEADERS)
    try:
        payload = _read_url(request)
    except Exception:
        return []
    reader = csv.DictReader(io.StringIO(payload))
    rows = []
    for row in reader:
        normalized = {
            _TWSE_DAILY_ALL_FIELD_MAP.get(k.strip(), k.strip()): v.strip()
            for k, v in row.items()
            if k is not None
        }
        rows.append(normalized)
    return rows


def get_tw_daily_all_date() -> str | None:
    """Return the trading date of the current get_tw_daily_all() snapshot as ISO YYYY-MM-DD."""
    rows = get_tw_daily_all()
    if not rows:
        return None
    roc = rows[0].get("Date", "").strip()
    if len(roc) == 7 and roc.isdigit():
        year = int(roc[:3]) + 1911
        return f"{year:04d}-{roc[3:5]}-{roc[5:7]}"
    return None


def build_tw_company_context(symbol: str, latest_price: float | None = None) -> dict[str, Any]:
    stock_id = normalize_tw_stock_id(symbol)
    exchange = detect_tw_exchange(stock_id)
    if exchange is None:
        return {}

    company_profile = get_tw_company_profile(stock_id, exchange)
    monthly_revenue = get_tw_monthly_revenue(stock_id, exchange)
    valuation = get_tw_valuation(stock_id, exchange, latest_price=latest_price, company_profile=company_profile)
    financial_ratios = get_tw_financial_ratios(stock_id, exchange, valuation=valuation)
    peers_comparison = get_tw_peers_comparison(stock_id, exchange, company_profile=company_profile)
    insider_actions = get_tw_insider_actions(stock_id, exchange)
    chips_flow = get_tw_chips_flow(stock_id, exchange)

    return {
        "stock_id": stock_id,
        "exchange": exchange,
        "company_profile": company_profile,
        "monthly_revenue": monthly_revenue,
        "valuation": valuation,
        "financial_ratios": financial_ratios,
        "peers_comparison": peers_comparison,
        "insider_actions": insider_actions,
        "chips_flow": chips_flow,
    }


def normalize_tw_stock_id(symbol: str) -> str:
    return symbol.strip().upper().removesuffix(".TW").removesuffix(".TWO")


def detect_tw_exchange(stock_id: str) -> str | None:
    if stock_id in _twse_company_basics():
        return "twse"
    if stock_id in _tpex_company_basics():
        return "tpex"
    return None


def get_tw_company_profile(stock_id: str, exchange: str) -> dict[str, Any] | None:
    row = _get_company_row(stock_id, exchange)
    if row is None:
        return None

    return {
        "stock_id": stock_id,
        "exchange": exchange,
        "company_name": _pick_text(row, "公司名稱", "CompanyName"),
        "company_short_name": _pick_text(row, "公司簡稱", "CompanyAbbreviation"),
        "industry_code": _pick_text(row, "產業別", "SecuritiesIndustryCode"),
        "listed_at": _pick_text(row, "上市日期", "DateOfListing"),
        "address": _pick_text(row, "住址", "Address"),
        "chairman": _pick_text(row, "董事長", "Chairman"),
        "capital": _pick_float(row, "實收資本額", "Paidin.Capital.NTDollars"),
        "par_value": _pick_par_value(row),
    }


def get_tw_monthly_revenue(stock_id: str, exchange: str) -> dict[str, Any] | None:
    row = _find_row(_monthly_revenue_rows(exchange), stock_id)
    if row is None:
        return None

    return {
        "latest_month": _pick_text(row, "資料年月"),
        "latest_month_revenue": _pick_float(row, "營業收入-當月營收"),
        "mom_percent": _pick_float(row, "營業收入-上月比較增減(%)"),
        "yoy_percent": _pick_float(row, "營業收入-去年同月增減(%)"),
        "ytd_revenue": _pick_float(row, "累計營業收入-當月累計營收"),
        "ytd_yoy_percent": _pick_float(row, "累計營業收入-前期比較增減(%)"),
        "industry": _pick_text(row, "產業別"),
        "history_table": [],
    }


def get_tw_valuation(
    stock_id: str,
    exchange: str,
    *,
    latest_price: float | None,
    company_profile: dict[str, Any] | None,
) -> dict[str, Any] | None:
    valuation_row = _find_row(_peratio_rows(exchange), stock_id)
    if valuation_row is None:
        return None

    pe_ratio = _pick_float(valuation_row, "PEratio", "PriceEarningRatio")
    pbr_ratio = _pick_float(valuation_row, "PBratio", "PriceBookRatio")
    dividend_yield = _pick_float(valuation_row, "DividendYield", "YieldRatio")
    price = latest_price if latest_price not in (None, 0) else _quote_close_price(stock_id, exchange)

    capital = (company_profile or {}).get("capital")
    par_value = (company_profile or {}).get("par_value") or 10.0
    shares_outstanding = None
    if capital not in (None, 0) and par_value not in (None, 0):
        shares_outstanding = capital / par_value

    market_cap = price * shares_outstanding if price not in (None, 0) and shares_outstanding not in (None, 0) else None

    peer_rows = get_tw_peers_comparison(stock_id, exchange, company_profile=company_profile)
    peer_pes = [row["pe_ratio"] for row in peer_rows if isinstance(row.get("pe_ratio"), (int, float)) and row["pe_ratio"] > 0]
    fair_value = None
    discount_premium = None
    if price not in (None, 0) and pe_ratio not in (None, 0) and peer_pes:
        eps = price / pe_ratio
        fair_value = round(median(peer_pes) * eps, 2)
        if fair_value not in (None, 0):
            discount_premium = round((price / fair_value - 1) * 100, 2)

    return {
        "market_cap": _round_or_none(market_cap),
        "pe_ratio": _round_or_none(pe_ratio),
        "pbr_ratio": _round_or_none(pbr_ratio),
        "dividend_yield": _round_or_none(dividend_yield),
        "fair_value": fair_value,
        "discount_premium": discount_premium,
    }


def get_tw_financial_ratios(
    stock_id: str,
    exchange: str,
    *,
    valuation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    row = _latest_profitability_row(stock_id, exchange)
    if row is None and valuation is None:
        return None

    pe_ratio = None if valuation is None else valuation.get("pe_ratio")
    pbr_ratio = None if valuation is None else valuation.get("pbr_ratio")
    dividend_yield = None if valuation is None else valuation.get("dividend_yield")
    roe = None
    if isinstance(pe_ratio, (int, float)) and isinstance(pbr_ratio, (int, float)) and pe_ratio > 0:
        roe = round(pbr_ratio / pe_ratio * 100, 2)

    return {
        "operating_margin": _pick_float(row, "營業利益率(%)(營業利益)/(營業收入)", "營業利益率") if row else None,
        "net_margin": _pick_float(row, "稅後純益率(%)(稅後純益)/(營業收入)", "稅後純益率") if row else None,
        "roe": roe,
        "dividend_yield": _round_or_none(dividend_yield) if isinstance(dividend_yield, (int, float)) else None,
    }


def get_tw_peers_comparison(
    stock_id: str,
    exchange: str,
    *,
    company_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    profile = company_profile or get_tw_company_profile(stock_id, exchange)
    if not profile:
        return []

    industry_code = profile.get("industry_code")
    if not industry_code:
        return []

    peer_rows = _twse_company_basics().values() if exchange == "twse" else _tpex_company_basics().values()
    valuation_index = _peratio_index(exchange)
    quotes_index = _quote_index(exchange)

    peers: list[dict[str, Any]] = []
    for row in peer_rows:
        candidate_code = _pick_text(row, "公司代號", "SecuritiesCompanyCode")
        if not candidate_code or candidate_code == stock_id:
            continue
        if _pick_text(row, "產業別", "SecuritiesIndustryCode") != industry_code:
            continue

        valuation_row = valuation_index.get(candidate_code)
        quote_row = quotes_index.get(candidate_code)
        if valuation_row is None or quote_row is None:
            continue

        peers.append(
            {
                "stock_id": candidate_code,
                "company_name": _pick_text(row, "公司簡稱", "CompanyAbbreviation", "公司名稱", "CompanyName"),
                "close": _quote_close(candidate_code, exchange, row=quote_row),
                "change": _pick_float(quote_row, "Change"),
                "pe_ratio": _pick_float(valuation_row, "PEratio", "PriceEarningRatio"),
                "dividend_yield": _pick_float(valuation_row, "DividendYield", "YieldRatio"),
                "pbr_ratio": _pick_float(valuation_row, "PBratio", "PriceBookRatio"),
            }
        )

    peers = [peer for peer in peers if peer["close"] is not None]
    peers.sort(key=lambda item: (item["pe_ratio"] is None, item["stock_id"]))
    return peers[:6]


def get_tw_insider_actions(stock_id: str, exchange: str) -> dict[str, Any]:
    recent_transfers = [
        {
            "date": _pick_text(row, "出表日期", "Date"),
            "person": _pick_text(row, "姓名", "姓名"),
            "identity": _pick_text(row, "申報人身分", "申請人身分"),
            "method": _pick_text(row, "預定轉讓方式及股數-轉讓方式"),
            "shares": _pick_float(row, "預定轉讓方式及股數-轉讓股數", "預定轉讓總股數-自有持股"),
            "period": _pick_text(row, "有效轉讓期間"),
        }
        for row in _filter_rows(_recent_transfer_rows(exchange), stock_id)[:5]
    ]
    pending_non_transfer = [
        {
            "date": _pick_text(row, "出表日期"),
            "person": _pick_text(row, "姓名"),
            "identity": _pick_text(row, "申報人身分"),
            "shares_not_transferred": _pick_float(row, "未轉讓股數-自有持股"),
            "reason": _pick_text(row, "未轉讓理由"),
        }
        for row in _filter_rows(_pending_transfer_rows(exchange), stock_id)[:3]
    ]
    director_holdings = [
        {
            "title": _pick_text(row, "職稱"),
            "name": _pick_text(row, "姓名"),
            "current_holding": _pick_float(row, "目前持股"),
            "pledged_shares": _pick_float(row, "設質股數"),
            "pledge_ratio": _pick_float(row, "設質股數佔持股比例"),
        }
        for row in _filter_rows(_director_holdings_rows(exchange), stock_id)[:6]
    ]
    major_shareholders = [
        _pick_text(row, "大股東名稱")
        for row in _filter_rows(_major_shareholder_rows(exchange), stock_id)[:8]
        if _pick_text(row, "大股東名稱")
    ]

    return {
        "recent_transfers": recent_transfers,
        "pending_non_transfers": pending_non_transfer,
        "director_holdings": director_holdings,
        "major_shareholders": major_shareholders,
    }


def get_tw_chips_flow(stock_id: str, exchange: str) -> dict[str, Any] | None:
    if exchange != "tpex":
        return None

    trading_row = _find_row(_tpex_3insti_rows(), stock_id)
    margin_row = _find_row(_tpex_margin_balance_rows(), stock_id)
    if trading_row is None and margin_row is None:
        return None

    return {
        "institutional": {
            "foreign_difference": _pick_float(
                trading_row,
                "ForeignInvestorsInclude MainlandAreaInvestors-Difference",
                "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference",
            ) if trading_row else None,
            "investment_trust_difference": _pick_float(trading_row, "SecuritiesInvestmentTrustCompanies-Difference") if trading_row else None,
            "dealer_difference": _pick_float(trading_row, "Dealers-Difference") if trading_row else None,
            "total_difference": _pick_float(trading_row, "TotalDifference") if trading_row else None,
        },
        "margin_balance": {
            "margin_balance": _pick_float(margin_row, "MarginPurchaseBalance", "融資今日餘額"),
            "short_balance": _pick_float(margin_row, "ShortSaleBalance", "融券今日餘額"),
        },
    }


@lru_cache(maxsize=1)
def _twse_company_basics() -> dict[str, dict[str, Any]]:
    return _index_rows(_fetch_rows(TWSE_BASE_URL, "opendata/t187ap03_L"), "公司代號")


@lru_cache(maxsize=1)
def _tpex_company_basics() -> dict[str, dict[str, Any]]:
    return _index_rows(_fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap03_O", insecure=True), "公司代號", "SecuritiesCompanyCode")


def _get_company_row(stock_id: str, exchange: str) -> dict[str, Any] | None:
    return (_twse_company_basics() if exchange == "twse" else _tpex_company_basics()).get(stock_id)


@lru_cache(maxsize=2)
def _monthly_revenue_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap05_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap05_O", insecure=True)


@lru_cache(maxsize=2)
def _peratio_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "exchangeReport/BWIBBU_ALL")
    return _fetch_rows(TPEX_BASE_URL, "tpex_mainboard_peratio_analysis", insecure=True)


def _peratio_index(exchange: str) -> dict[str, dict[str, Any]]:
    key = "Code" if exchange == "twse" else "SecuritiesCompanyCode"
    return _index_rows(_peratio_rows(exchange), key)


@lru_cache(maxsize=2)
def _quote_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "exchangeReport/STOCK_DAY_AVG_ALL")
    return _fetch_rows(TPEX_BASE_URL, "tpex_mainboard_quotes", insecure=True)


def _quote_index(exchange: str) -> dict[str, dict[str, Any]]:
    key = "Code" if exchange == "twse" else "SecuritiesCompanyCode"
    return _index_rows(_quote_rows(exchange), key)


def _quote_close_price(stock_id: str, exchange: str) -> float | None:
    return _quote_close(stock_id, exchange, row=_quote_index(exchange).get(stock_id))


def _quote_close(stock_id: str, exchange: str, *, row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    return _pick_float(row, "ClosingPrice", "Close")


@lru_cache(maxsize=2)
def _profitability_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap17_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_187ap17_O", insecure=True)


def _latest_profitability_row(stock_id: str, exchange: str) -> dict[str, Any] | None:
    return _latest_row(
        _filter_rows(_profitability_rows(exchange), stock_id),
        year_keys=("年度", "Year"),
        quarter_keys=("季別",),
    )


@lru_cache(maxsize=2)
def _director_holdings_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap11_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap11_O", insecure=True)


@lru_cache(maxsize=2)
def _recent_transfer_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap12_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap12_O", insecure=True)


@lru_cache(maxsize=2)
def _pending_transfer_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap13_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap13_O", insecure=True)


@lru_cache(maxsize=2)
def _major_shareholder_rows(exchange: str) -> list[dict[str, Any]]:
    if exchange == "twse":
        return _fetch_rows(TWSE_BASE_URL, "opendata/t187ap02_L")
    return _fetch_rows(TPEX_BASE_URL, "mopsfin_t187ap02_O", insecure=True)


@lru_cache(maxsize=1)
def _tpex_3insti_rows() -> list[dict[str, Any]]:
    return _fetch_rows(TPEX_BASE_URL, "tpex_3insti_daily_trading", insecure=True)


@lru_cache(maxsize=1)
def _tpex_margin_balance_rows() -> list[dict[str, Any]]:
    return _fetch_rows(TPEX_BASE_URL, "tpex_mainboard_margin_balance", insecure=True)


def _filter_rows(rows: list[dict[str, Any]], stock_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if _row_stock_id(row) == stock_id]


def _find_row(rows: list[dict[str, Any]], stock_id: str) -> dict[str, Any] | None:
    for row in rows:
        if _row_stock_id(row) == stock_id:
            return row
    return None


def _row_stock_id(row: dict[str, Any]) -> str:
    return _pick_text(row, "公司代號", "SecuritiesCompanyCode", "Code", "stock_id")


def _latest_row(
    rows: list[dict[str, Any]],
    *,
    year_keys: tuple[str, ...],
    quarter_keys: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if not rows:
        return None

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        year = 0
        for key in year_keys:
            value = _pick_float(row, key)
            if value is not None:
                year = int(value)
                break
        quarter = 0
        for key in quarter_keys:
            value = _pick_float(row, key)
            if value is not None:
                quarter = int(value)
                break
        return year, quarter

    return max(rows, key=sort_key)


def _pick_text(row: dict[str, Any] | None, *keys: str) -> str:
    if row is None:
        return ""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _pick_float(row: dict[str, Any] | None, *keys: str) -> float | None:
    if row is None:
        return None
    for key in keys:
        if key not in row:
            continue
        parsed = _to_float(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _pick_par_value(row: dict[str, Any]) -> float | None:
    raw = _pick_text(row, "普通股每股面額", "ParValueOfCommonStock")
    if not raw:
        return 10.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw.replace(",", ""))
    return float(match.group(1)) if match else 10.0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    text = str(value).strip()
    if not text or text in {"-", "--", "—", "－"}:
        return None

    text = text.replace(",", "").replace("%", "").replace("元", "").replace("股", "").strip()
    if text in {"", "-", "--", "—", "－"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _index_rows(rows: list[dict[str, Any]], *keys: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = _pick_text(row, *keys)
        if code:
            indexed[code] = row
    return indexed


@lru_cache(maxsize=32)
def _fetch_rows(base_url: str, path: str, insecure: bool = False) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = Request(url, headers=DEFAULT_HEADERS)
    payload = _read_url(request, insecure=insecure)
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError(f"Expected list payload from {url}")
    return [row for row in data if isinstance(row, dict)]


def _read_url(request: Request, *, insecure: bool = False) -> str:
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=context) as response:
            return response.read().decode("utf-8-sig")
    except (ssl.SSLError, ssl.SSLCertVerificationError, URLError):
        if insecure:
            raise
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
            context=ssl._create_unverified_context(),
        ) as response:
            return response.read().decode("utf-8-sig")

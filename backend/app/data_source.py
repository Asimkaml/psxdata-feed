"""Data access layer.

Two interchangeable sources that return the same pandas DataFrames:

* live  - the ``psxdata`` package (scrapes dps.psx.com.pk)
* mock  - deterministic demo data, enabled with ``PSX_MOCK=1``. Used for
          offline development and tests. API responses are tagged with
          ``source: "mock"`` so the UI can show a "Demo data" badge.
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

USE_MOCK = os.getenv("PSX_MOCK", "").lower() in {"1", "true", "yes"}
SOURCE = "mock" if USE_MOCK else "live"

# --------------------------------------------------------------------------
# Demo universe (only used in mock mode)
# --------------------------------------------------------------------------
_MOCK_COMPANIES = {
    # symbol: (name, sector, base price, pe, div yield %, mcap (PKR m))
    "ENGRO": ("Engro Corporation Limited", "FERTILIZER", 330.0, 7.1, 6.8, 190_000),
    "LUCK": ("Lucky Cement Limited", "CEMENT", 1450.0, 9.4, 3.2, 420_000),
    "HBL": ("Habib Bank Limited", "COMMERCIAL BANKS", 240.0, 4.6, 11.0, 350_000),
    "OGDC": ("Oil & Gas Development Co. Ltd.", "OIL & GAS EXPLORATION COMPANIES", 215.0, 5.2, 9.5, 920_000),
    "PPL": ("Pakistan Petroleum Limited", "OIL & GAS EXPLORATION COMPANIES", 185.0, 5.9, 8.1, 480_000),
    "MARI": ("Mari Energies Limited", "OIL & GAS EXPLORATION COMPANIES", 640.0, 7.7, 5.4, 780_000),
    "UBL": ("United Bank Limited", "COMMERCIAL BANKS", 390.0, 5.0, 10.2, 480_000),
    "FFC": ("Fauji Fertilizer Company Ltd.", "FERTILIZER", 450.0, 7.8, 9.9, 570_000),
    "HUBC": ("The Hub Power Company Ltd.", "POWER GENERATION & DISTRIBUTION", 205.0, 6.3, 7.4, 260_000),
    "MEBL": ("Meezan Bank Limited", "ISLAMIC COMMERCIAL BANKS", 380.0, 6.1, 8.8, 680_000),
    "SYS": ("Systems Limited", "TECHNOLOGY & COMMUNICATION", 140.0, 14.0, 1.9, 40_000),
    "EFERT": ("Engro Fertilizers Limited", "FERTILIZER", 240.0, 8.3, 10.4, 320_000),
    # Listed, has price history, but is absent from the screener table (like some real tickers)
    "PSO": ("Pakistan State Oil Company Ltd.", "OIL & GAS MARKETING COMPANIES", 410.0, 4.0, 6.0, 190_000),
}
_MOCK_NOT_IN_SCREENER = {"PSO"}


def _seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)


def _mock_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    if symbol not in _MOCK_COMPANIES:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "is_anomaly"])
    base = _MOCK_COMPANIES.get(symbol, ("", "", 100.0, 0, 0, 0))[2]
    rng = np.random.default_rng(_seed(symbol))
    days = pd.bdate_range(start, end)
    steps = rng.normal(0.0004, 0.017, len(days))
    close = base * np.exp(np.cumsum(steps))
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1 + rng.normal(0, 0.003, len(days)))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, len(days))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, len(days))))
    volume = rng.integers(200_000, 6_000_000, len(days))
    return pd.DataFrame(
        {
            "date": days,
            "open": open_.round(2),
            "high": high.round(2),
            "low": low.round(2),
            "close": close.round(2),
            "volume": volume,
            "is_anomaly": False,
        }
    )


# --------------------------------------------------------------------------
# Public functions - same shapes as psxdata
# --------------------------------------------------------------------------
def screener() -> pd.DataFrame:
    if not USE_MOCK:
        import psxdata

        return psxdata.screener()
    rows = []
    start, end = default_history_window(60)
    for sym, (_, sector, _price, pe, dy, mcap) in _MOCK_COMPANIES.items():
        if sym in _MOCK_NOT_IN_SCREENER:
            continue
        rng = np.random.default_rng(_seed(sym) + 1)
        # Use the latest mock close so the headline price matches the chart.
        last_close = float(_mock_history(sym, start, end)["close"].iloc[-1])
        rows.append(
            {
                "symbol": sym,
                "sector": sector,
                "listed_in": "KSE100",
                "market_cap": mcap * 1_000_000.0,
                "price": last_close,
                "pe_ratio": pe,
                "dividend_yield": dy,
                "free_float": float(rng.integers(20, 60)),
                "volume_avg_30d": float(rng.integers(500_000, 5_000_000)),
                "change_1y_pct": round(float(rng.normal(25, 30)), 2),
            }
        )
    return pd.DataFrame(rows)


def symbols() -> pd.DataFrame:
    if not USE_MOCK:
        import psxdata

        return psxdata.symbols()
    return pd.DataFrame(
        [
            {"symbol": s, "name": v[0], "sector_name": v[1], "is_etf": False, "is_debt": False, "is_gem": False}
            for s, v in _MOCK_COMPANIES.items()
        ]
    )


def history(symbol: str, start: date, end: date) -> pd.DataFrame:
    if not USE_MOCK:
        import psxdata

        return psxdata.stocks(symbol, start=start.isoformat(), end=end.isoformat())
    return _mock_history(symbol, start, end)


def kse100_weights() -> pd.DataFrame:
    if not USE_MOCK:
        import psxdata

        return psxdata.indices("KSE100")
    total = sum(v[5] for v in _MOCK_COMPANIES.values())
    return pd.DataFrame(
        [{"symbol": s, "idx_weight": round(v[5] / total * 40, 2)} for s, v in _MOCK_COMPANIES.items()]
    )


def default_history_window(days: int = 60) -> tuple[date, date]:
    end = date.today()
    return end - timedelta(days=days), end

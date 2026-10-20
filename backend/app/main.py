"""PSX Dashboard API - a thin FastAPI layer over the `psxdata` package."""
from __future__ import annotations

import logging
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import data_source as ds

log = logging.getLogger("psx-dashboard")

DEFAULT_WATCHLIST = [
    "ENGRO", "LUCK", "HBL", "OGDC", "PPL", "MARI",
    "UBL", "FFC", "HUBC", "MEBL", "SYS", "EFERT",
]
MAX_SYMBOLS = 30
SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,12}$")
CARD_TTL = 300  # seconds; psxdata itself also caches screener data for 15 min

app = FastAPI(title="PSX Dashboard API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

_card_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = Lock()


# ---------------------------------------------------------------- helpers
def _num(v: Any) -> float | None:
    """Convert numpy/pandas scalars to JSON-safe floats (NaN -> None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, 4)


def _clean_symbols(raw: list[str]) -> list[str]:
    out: list[str] = []
    for s in raw:
        s = s.strip().upper()
        if not SYMBOL_RE.match(s):
            raise HTTPException(422, f"Invalid symbol: {s!r}")
        if s not in out:
            out.append(s)
    if not out:
        raise HTTPException(422, "No symbols given")
    if len(out) > MAX_SYMBOLS:
        raise HTTPException(422, f"At most {MAX_SYMBOLS} symbols per request")
    return out


def _load_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Screener / symbols / KSE-100 weights. psxdata caches these on disk,
    so calling them for every request is cheap after the first fetch."""
    def indexed(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "symbol" not in df.columns:
            return pd.DataFrame()
        df = df.copy()
        df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
        return df.drop_duplicates("symbol").set_index("symbol")

    screener = indexed(ds.screener())
    names = indexed(ds.symbols())
    try:
        kse = indexed(ds.kse100_weights())
    except Exception as exc:  # index data is a nice-to-have, not essential
        log.warning("KSE100 weights unavailable: %s", exc)
        kse = pd.DataFrame()
    return screener, names, kse


def _build_card(symbol: str, screener: pd.DataFrame, names: pd.DataFrame, kse: pd.DataFrame) -> dict[str, Any]:
    # The screener table does not list every PSX ticker, so a miss there is not
    # an error by itself: fall back to price history and leave fundamentals blank.
    in_screener = symbol in screener.index
    row = screener.loc[symbol] if in_screener else pd.Series(dtype=object)
    start, end = ds.default_history_window(60)
    hist = ds.history(symbol, start, end)

    if not in_screener and hist.empty and symbol not in names.index:
        return {"symbol": symbol, "error": "Not a listed PSX ticker (no screener, symbol list or price data found)"}
    if not in_screener and hist.empty:
        return {"symbol": symbol, "error": "Listed on PSX but no recent price data (illiquid, suspended or debt/ETF instrument)"}

    last = prev = None
    spark: list[dict[str, Any]] = []
    if not hist.empty:
        hist = hist.sort_values("date").tail(30)
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else None
        spark = [
            {"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "close": _num(c)}
            for d, c in zip(hist["date"], hist["close"])
        ]

    price = _num(row.get("price"))
    if price is None and last is not None:
        price = _num(last["close"])

    change = change_pct = None
    if last is not None and prev is not None and prev["close"]:
        change = _num(last["close"] - prev["close"])
        change_pct = _num((last["close"] - prev["close"]) / prev["close"] * 100)

    return {
        "symbol": symbol,
        "name": names.loc[symbol, "name"] if symbol in names.index else symbol,
        # screener's "sector" is a numeric code; the readable name lives in symbols()
        "sector": (names.loc[symbol, "sector_name"] if symbol in names.index and "sector_name" in names.columns else None),
        "has_fundamentals": in_screener,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "day_high": _num(last["high"]) if last is not None else None,
        "day_low": _num(last["low"]) if last is not None else None,
        "volume": _num(last["volume"]) if last is not None else None,
        "market_cap": _num(row.get("market_cap")),
        "pe_ratio": _num(row.get("pe_ratio")),
        "dividend_yield": _num(row.get("dividend_yield")),
        "free_float": _num(row.get("free_float")),
        "avg_volume_30d": _num(row.get("volume_avg_30d")),
        "change_1y_pct": _num(row.get("change_1y_pct")),
        "kse100_weight": _num(kse.loc[symbol, "idx_weight"]) if symbol in kse.index else None,
        "sparkline": spark,
        "error": None,
    }


def _cards(symbols: list[str]) -> list[dict[str, Any]]:
    now = time.time()
    result: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    with _cache_lock:
        for s in symbols:
            hit = _card_cache.get(s)
            if hit and now - hit[0] < CARD_TTL:
                result[s] = hit[1]
            else:
                missing.append(s)

    if missing:
        try:
            screener, names, kse = _load_tables()
        except Exception as exc:
            log.exception("Failed to load PSX tables")
            raise HTTPException(503, f"PSX data source unavailable: {exc}") from exc

        def work(sym: str) -> dict[str, Any]:
            try:
                return _build_card(sym, screener, names, kse)
            except Exception as exc:  # one bad symbol must not break the dashboard
                log.warning("Card failed for %s: %s", sym, exc)
                return {"symbol": sym, "error": f"{type(exc).__name__}: {exc}"}

        with ThreadPoolExecutor(max_workers=4) as pool:
            built = list(pool.map(work, missing))
        with _cache_lock:
            for card in built:
                result[card["symbol"]] = card
                if not card.get("error"):
                    _card_cache[card["symbol"]] = (now, card)

    return [result[s] for s in symbols]


# ---------------------------------------------------------------- routes
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "source": ds.SOURCE}


@app.get("/api/watchlist")
def watchlist() -> dict[str, Any]:
    return {"symbols": DEFAULT_WATCHLIST}


@app.get("/api/stocks")
def stocks(symbols: str | None = Query(None, description="Comma-separated tickers, e.g. ENGRO,LUCK")) -> dict[str, Any]:
    wanted = _clean_symbols(symbols.split(",") if symbols else DEFAULT_WATCHLIST)
    return {"source": ds.SOURCE, "updated_at": int(time.time()), "stocks": _cards(wanted)}


@app.get("/api/stocks/{symbol}/history")
def stock_history(symbol: str, days: int = Query(90, ge=5, le=365)) -> dict[str, Any]:
    sym = _clean_symbols([symbol])[0]
    start, end = ds.default_history_window(days)
    try:
        df = ds.history(sym, start, end)
    except Exception as exc:
        raise HTTPException(503, f"PSX data source unavailable: {exc}") from exc
    if df.empty:
        raise HTTPException(404, f"No history for {sym}")
    df = df.sort_values("date")
    bars = [
        {
            "date": pd.Timestamp(r.date).strftime("%Y-%m-%d"),
            "open": _num(r.open), "high": _num(r.high),
            "low": _num(r.low), "close": _num(r.close), "volume": _num(r.volume),
        }
        for r in df.itertuples()
    ]
    return {"symbol": sym, "source": ds.SOURCE, "bars": bars}

import os

os.environ["PSX_MOCK"] = "1"  # must be set before the app imports data_source

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "source": "mock"}


def test_default_watchlist_cards():
    r = client.get("/api/stocks")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mock"
    assert len(body["stocks"]) == 12
    assert all(c["error"] is None for c in body["stocks"])
    card = body["stocks"][0]
    for key in ("symbol", "name", "sector", "price", "change_pct", "market_cap",
                "pe_ratio", "dividend_yield", "sparkline"):
        assert key in card
    assert len(card["sparkline"]) > 5


def test_custom_symbols_and_unknown_symbol():
    r = client.get("/api/stocks", params={"symbols": "luck,NOPE"})
    assert r.status_code == 200
    cards = r.json()["stocks"]
    assert [c["symbol"] for c in cards] == ["LUCK", "NOPE"]
    assert cards[0]["error"] is None
    assert cards[1]["error"]


def test_invalid_symbol_rejected():
    assert client.get("/api/stocks", params={"symbols": "BAD SYMBOL!"}).status_code == 422


def test_history():
    r = client.get("/api/stocks/ENGRO/history", params={"days": 30})
    assert r.status_code == 200
    bars = r.json()["bars"]
    assert bars and {"date", "open", "high", "low", "close", "volume"} <= bars[0].keys()


def test_symbol_missing_from_screener_falls_back_to_price_data():
    card = client.get("/api/stocks", params={"symbols": "PSO"}).json()["stocks"][0]
    assert card["error"] is None
    assert card["has_fundamentals"] is False
    assert card["price"] is not None and len(card["sparkline"]) > 5
    assert card["pe_ratio"] is None
    assert card["sector"] == "OIL & GAS MARKETING COMPANIES"


def test_sector_is_a_readable_name():
    card = client.get("/api/stocks", params={"symbols": "LUCK"}).json()["stocks"][0]
    assert card["sector"] == "CEMENT" and card["has_fundamentals"] is True

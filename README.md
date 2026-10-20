# PSX Dashboard

A small dashboard that lists selected Pakistan Stock Exchange companies as cards.
Backend: **FastAPI** on top of the [`psxdata`](https://github.com/psxdata/psxdata) package.
Frontend: **React** (Vite).

Each card shows a ticker monogram icon, company name, sector, price, day change,
a 30-day sparkline, market cap, P/E, dividend yield, 1-year change, volume,
30-day average volume, day range and KSE-100 index weight.

## How `psxdata` is used

| Card data | psxdata call |
| --- | --- |
| Price, sector, market cap, P/E, dividend yield, 1Y change, avg volume | `psxdata.screener()` |
| Company name | `psxdata.symbols()` |
| Sparkline, day change, day range, volume | `psxdata.stocks(symbol, start, end)` |
| KSE-100 weight | `psxdata.indices("KSE100")` |

`psxdata` caches on disk (`~/.psxdata/cache`), so the screener is fetched once per 15 minutes
no matter how many cards you show. The API adds a 5-minute in-memory cache per card.

## Run it

Requires Python 3.11+ and Node 18+.

```bash
# 1. Backend (terminal 1)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 2. Frontend (terminal 2)
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api to :8000)
```

No network access to PSX (or want to try the UI offline)? Start the backend with demo data:

```bash
PSX_MOCK=1 uvicorn app.main:app --port 8000      # Windows PowerShell: $env:PSX_MOCK=1
```

The UI then shows a **Demo data** badge instead of **Live PSX data**.

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/health` | Status and data source (`live` or `mock`) |
| `GET /api/watchlist` | Default tickers |
| `GET /api/stocks?symbols=ENGRO,LUCK` | Card data; omit `symbols` for the default list (max 30) |
| `GET /api/stocks/{symbol}/history?days=90` | Daily OHLCV bars |

Interactive docs at `http://localhost:8000/docs`.

## Configuration

- `CORS_ORIGINS` - comma-separated allowed origins (default: the Vite dev server).
- `API_URL` - where the Vite dev proxy forwards `/api` (default `http://127.0.0.1:8000`).
- Edit `DEFAULT_WATCHLIST` in `backend/app/main.py` to change the default companies.
  In the browser, tickers can be added or removed and are remembered in local storage.

## Tests

```bash
cd backend && python -m pytest
```

## Notes

- `psxdata` is alpha software and scrapes PSX's public pages, so columns or availability can change.
- Prices are informational only, not investment advice.

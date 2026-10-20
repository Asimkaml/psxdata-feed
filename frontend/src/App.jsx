import { useCallback, useEffect, useMemo, useState } from "react";
import StockCard from "./StockCard.jsx";

const STORAGE_KEY = "psx-dashboard:symbols";

const SORTS = {
  symbol: { label: "Symbol", fn: (a, b) => a.symbol.localeCompare(b.symbol) },
  change: { label: "Day change", fn: (a, b) => (b.change_pct ?? -Infinity) - (a.change_pct ?? -Infinity) },
  price: { label: "Price", fn: (a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity) },
  mcap: { label: "Market cap", fn: (a, b) => (b.market_cap ?? -Infinity) - (a.market_cap ?? -Infinity) },
};

function loadSaved() {
  try {
    const v = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(v) && v.length ? v : null;
  } catch {
    return null;
  }
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch { /* body wasn't JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export default function App() {
  const [symbols, setSymbols] = useState(null); // null until the default list is known
  const [data, setData] = useState({ stocks: [], source: null, updated_at: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState("symbol");
  const [draft, setDraft] = useState("");

  // 1. Decide which symbols to show: saved list, else server default.
  useEffect(() => {
    const saved = loadSaved();
    if (saved) return setSymbols(saved);
    getJson("/api/watchlist")
      .then((r) => setSymbols(r.symbols))
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  // 2. Fetch cards whenever the list changes.
  const load = useCallback(async (list) => {
    if (!list || list.length === 0) {
      setData((d) => ({ ...d, stocks: [] }));
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getJson(`/api/stocks?symbols=${encodeURIComponent(list.join(","))}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!symbols) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols)); } catch { /* storage unavailable */ }
    load(symbols);
  }, [symbols, load]);

  const add = (e) => {
    e.preventDefault();
    const sym = draft.trim().toUpperCase();
    if (!/^[A-Z0-9]{1,12}$/.test(sym)) return;
    setDraft("");
    setSymbols((cur) => (cur.includes(sym) ? cur : [...cur, sym]));
  };
  const remove = (sym) => setSymbols((cur) => cur.filter((s) => s !== sym));

  const sorted = useMemo(() => [...data.stocks].sort(SORTS[sort].fn), [data.stocks, sort]);
  const updated = data.updated_at ? new Date(data.updated_at * 1000).toLocaleTimeString() : null;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>PSX Dashboard</h1>
          <p className="subtitle">
            Selected Pakistan Stock Exchange companies, powered by the{" "}
            <a href="https://github.com/psxdata/psxdata" target="_blank" rel="noreferrer">psxdata</a> package
          </p>
        </div>
        <div className="meta">
          {data.source && (
            <span className={`source ${data.source}`}>{data.source === "mock" ? "Demo data" : "Live PSX data"}</span>
          )}
          {updated && <span className="updated">Updated {updated}</span>}
          <button onClick={() => load(symbols)} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
        </div>
      </header>

      <section className="toolbar">
        <form onSubmit={add} className="add">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a ticker, e.g. PSO"
            aria-label="Add a ticker"
            maxLength={12}
          />
          <button type="submit">Add</button>
        </form>
        <label className="sort">
          Sort by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
      </section>

      {error && (
        <div className="banner" role="alert">
          <strong>Couldn't load stocks.</strong> {error}
          <button onClick={() => load(symbols)}>Retry</button>
        </div>
      )}

      {loading && data.stocks.length === 0 && !error ? (
        <div className="grid">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="card skeleton" />)}
        </div>
      ) : (
        <main className="grid">
          {sorted.map((s) => <StockCard key={s.symbol} stock={s} onRemove={remove} />)}
          {!loading && !error && sorted.length === 0 && (
            <p className="empty">Your watchlist is empty. Add a ticker above.</p>
          )}
        </main>
      )}

      <footer className="foot">Prices are for information only.</footer>
    </div>
  );
}

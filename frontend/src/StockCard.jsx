import Sparkline from "./Sparkline.jsx";
import { fmtCompact, fmtNum, fmtPct, fmtPrice, titleCase } from "./format.js";

// PSX companies have no official logo feed, so each card gets a deterministic
// colored monogram derived from the ticker (same ticker -> same color).
function hueFor(symbol) {
  let h = 0;
  for (const ch of symbol) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export function Icon({ symbol }) {
  const hue = hueFor(symbol);
  return (
    <div className="icon" style={{ background: `hsl(${hue} 55% 42%)` }} aria-hidden="true">
      {symbol.slice(0, 2)}
    </div>
  );
}

function Stat({ label, value, wide }) {
  return (
    <div className={`stat${wide ? " wide" : ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

export default function StockCard({ stock, onRemove }) {
  if (stock.error) {
    return (
      <article className="card card-error">
        <header className="card-head">
          <Icon symbol={stock.symbol} />
          <div className="card-title">
            <h2>{stock.symbol}</h2>
            <p>Unavailable</p>
          </div>
          <button className="remove" onClick={() => onRemove(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>×</button>
        </header>
        <p className="error-text">{stock.error}</p>
      </article>
    );
  }

  const up = (stock.change_pct ?? 0) >= 0;
  const range =
    stock.day_low != null && stock.day_high != null
      ? `${fmtPrice(stock.day_low)} – ${fmtPrice(stock.day_high)}`
      : "—";

  return (
    <article className="card">
      <header className="card-head">
        <Icon symbol={stock.symbol} />
        <div className="card-title">
          <h2>{stock.symbol}</h2>
          <p title={stock.name}>{stock.name}</p>
        </div>
        <button className="remove" onClick={() => onRemove(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>×</button>
      </header>

      <div className="price-row">
        <div className="price">
          <span className="currency">PKR</span> {fmtPrice(stock.price)}
        </div>
        <div className={`badge ${up ? "up" : "down"}`}>
          {up ? "▲" : "▼"} {fmtPct(stock.change_pct, true)}
        </div>
      </div>
      <div className="sector">
        {titleCase(stock.sector)}
        {stock.has_fundamentals === false && (
          <span className="chip" title="This ticker is not in PSX's screener table, so only price data is shown">Price data only</span>
        )}
        {stock.kse100_weight != null && (
          <span className="chip" title="Weight in the KSE-100 index">KSE-100 · {stock.kse100_weight.toFixed(2)}%</span>
        )}
      </div>

      <Sparkline points={stock.sparkline} up={up} />

      <div className="stats">
        <Stat label="Market cap" value={fmtCompact(stock.market_cap)} />
        <Stat label="P/E" value={fmtNum(stock.pe_ratio)} />
        <Stat label="Div. yield" value={fmtPct(stock.dividend_yield)} />
        <Stat label="1Y change" value={fmtPct(stock.change_1y_pct, true)} />
        <Stat label="Volume" value={fmtCompact(stock.volume)} />
        <Stat label="Avg vol (30d)" value={fmtCompact(stock.avg_volume_30d)} />
        <Stat label="Day range" value={range} wide />
      </div>
    </article>
  );
}

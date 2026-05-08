#!/usr/bin/env python3
"""
Portfolio backtest v2: Two strategies compared to GLUX benchmark.

Strategy 1 (Long-only timing):
  - Entry signal → LONG (equal weight among active longs)
  - No signal → CASH (flat)
  - Exit signal → close position, go to cash

Strategy 2 (Long/Short):
  - Entry signal → LONG
  - Exit signal (3Q decline) → SHORT
  - Equal weight among all active positions (long + short)
  - Cover short when re-entry triggers

Entry rules:
  - Score >= 0.3 → enter long
  - 3Q on list + improving → confirm (same as long, just stronger conviction)

Exit rules:
  - Score 3 consecutive quarters decline → exit (Strategy 1: flat, Strategy 2: short)
  - Brand falls off (score <= 0) → exit

Re-entry:
  - Score 3 consecutive quarters rise AND score >= 0.3 → re-enter long

Universe: Prada (1913.HK), Tapestry (TPR), Ralph Lauren (RL)
  - Only companies with empirically validated positive signal (r > 0, Section 4.1)
  - Excluded: Burberry (reverse signal), Kering (confirmation only, cumulative -32%),
    LVMH/Capri (low coverage), Moncler (not validated)

Benchmark: GLUX.PA (Amundi S&P Global Luxury UCITS ETF, EUR→USD)
"""
import sys, math, statistics
sys.stdout.reconfigure(encoding='utf-8')
from datetime import date, timedelta

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance"); exit(1)

# ══════════════════════════════════════════
# Company Score Data (from company_scores.py)
# ══════════════════════════════════════════

SCORES = {
    "Prada Group": [
        ("Q4 2018", 0), ("Q1 2019", 0.426), ("Q2 2019", 0.369), ("Q3 2019", 0.635),
        ("Q4 2019", 0.344), ("Q1 2020", 0.425), ("Q2 2020", 0.446), ("Q3 2020", 0.559),
        ("Q4 2020", 0.486), ("Q1 2021", 0.436), ("Q2 2021", 0.456), ("Q3 2021", 0.524),
        ("Q4 2021", 0.608), ("Q1 2022", 0.648), ("Q2 2022", 0.690), ("Q3 2022", 0.726),
        ("Q4 2022", 0.777), ("Q1 2023", 0.764), ("Q2 2023", 0.663), ("Q3 2023", 0.642),
        ("Q4 2023", 0.694), ("Q1 2024", 0.710), ("Q2 2024", 0.648), ("Q3 2024", 0.632),
        ("Q4 2024", 0.644), ("Q1 2025", 0.591), ("Q2 2025", 0.635), ("Q3 2025", 0.546),
        ("Q4 2025", 0.629), ("Q1 2026", 0.494),
    ],
    "Tapestry": [
        ("Q4 2018", 0), ("Q1 2019", 0), ("Q2 2019", 0), ("Q3 2019", 0),
        ("Q4 2019", 0), ("Q1 2020", 0), ("Q2 2020", 0), ("Q3 2020", 0),
        ("Q4 2020", 0), ("Q1 2021", 0), ("Q2 2021", 0), ("Q3 2021", 0),
        ("Q4 2021", 0), ("Q1 2022", 0), ("Q2 2022", 0), ("Q3 2022", 0),
        ("Q4 2022", 0.101), ("Q1 2023", 0), ("Q2 2023", 0), ("Q3 2023", -0.045),
        ("Q4 2023", 0), ("Q1 2024", 0), ("Q2 2024", 0.060), ("Q3 2024", 0.285),
        ("Q4 2024", 0.581), ("Q1 2025", 0.619), ("Q2 2025", 0.619), ("Q3 2025", 0.413),
        ("Q4 2025", 0.367), ("Q1 2026", 0.326),
    ],
    "Ralph Lauren": [
        ("Q4 2018", 0), ("Q1 2019", 0), ("Q2 2019", 0), ("Q3 2019", 0),
        ("Q4 2019", 0), ("Q1 2020", 0), ("Q2 2020", 0), ("Q3 2020", 0),
        ("Q4 2020", 0), ("Q1 2021", 0), ("Q2 2021", 0), ("Q3 2021", 0),
        ("Q4 2021", 0), ("Q1 2022", 0), ("Q2 2022", 0), ("Q3 2022", 0),
        ("Q4 2022", 0), ("Q1 2023", 0), ("Q2 2023", 0), ("Q3 2023", 0),
        ("Q4 2023", 0), ("Q1 2024", 0), ("Q2 2024", 0), ("Q3 2024", 0.410),
        ("Q4 2024", 0.215), ("Q1 2025", 0.570), ("Q2 2025", 0.440), ("Q3 2025", 0.695),
        ("Q4 2025", 0.815), ("Q1 2026", 0.700),
    ],
}

TICKER_MAP = {"Prada Group": "1913.HK", "Tapestry": "TPR", "Ralph Lauren": "RL"}
FX_MAP = {"1913.HK": "HKDUSD=X"}

# ══════════════════════════════════════════
# Signal engine: determine position for each company each quarter
# ══════════════════════════════════════════

def generate_signals():
    """Returns dict: quarter → {company: signal}
    signal: 'LONG', 'EXIT', 'FLAT'
    LONG = entry triggered, EXIT = exit triggered, FLAT = no signal
    """
    companies = list(SCORES.keys())
    quarters = [q for q, _ in SCORES[companies[0]]]

    state = {}
    for co in companies:
        state[co] = {
            "position": "FLAT",
            "prev_score": None,
            "consecutive_decline": 0,
            "consecutive_rise": 0,
            "entered_ever": False,
            "exited": False,
        }

    signals = {}
    for qi, quarter in enumerate(quarters):
        signals[quarter] = {}
        for co in companies:
            s = state[co]
            score = SCORES[co][qi][1]
            prev = s["prev_score"]

            # Track consecutive decline / rise
            if prev is not None and prev > 0 and score > 0:
                if score < prev:
                    s["consecutive_decline"] += 1
                    s["consecutive_rise"] = 0
                elif score > prev:
                    s["consecutive_rise"] += 1
                    s["consecutive_decline"] = 0
                else:
                    s["consecutive_decline"] = 0
                    s["consecutive_rise"] = 0
            elif score <= 0:
                s["consecutive_decline"] = 0
                s["consecutive_rise"] = 0

            # Position logic
            if s["position"] == "LONG":
                if score <= 0:
                    s["position"] = "EXIT"
                    s["exited"] = True
                    s["consecutive_decline"] = 0
                elif s["consecutive_decline"] >= 3:
                    s["position"] = "EXIT"
                    s["exited"] = True
                # else stay LONG

            elif s["position"] == "EXIT":
                # Stay in EXIT until re-entry
                if s["consecutive_rise"] >= 3 and score >= 0.3:
                    s["position"] = "LONG"
                    s["exited"] = False
                # else stay EXIT

            elif s["position"] == "FLAT":
                if s["exited"]:
                    # Was exited before, need 3Q rise to re-enter
                    if s["consecutive_rise"] >= 3 and score >= 0.3:
                        s["position"] = "LONG"
                        s["exited"] = False
                else:
                    # Never entered: score >= 0.3 → enter
                    if score >= 0.3:
                        s["position"] = "LONG"
                        s["entered_ever"] = True

            signals[quarter][co] = s["position"]
            s["prev_score"] = score

    return signals

# ══════════════════════════════════════════
# Price data
# ══════════════════════════════════════════

def parse_q(s):
    parts = s.strip().split()
    return int(parts[1]), int(parts[0][1:])

def next_q(y, q):
    return (y + 1, 1) if q == 4 else (y, q + 1)

def publish_date(y, q):
    if q == 4:
        return date(y + 1, 1, 25)
    return date(y, [4, 7, 10][q - 1], 25)

def get_price(prices, target, window=10):
    for delta in range(window):
        d = (target + timedelta(days=delta)).strftime("%Y-%m-%d")
        if d in prices:
            return prices[d]
    for delta in range(1, window):
        d = (target - timedelta(days=delta)).strftime("%Y-%m-%d")
        if d in prices:
            return prices[d]
    return None

def fetch_prices():
    tickers = list(TICKER_MAP.values()) + list(FX_MAP.values()) + ["GLUX.PA", "EURUSD=X"]
    tickers = list(set(tickers))
    price_data = {}
    print("Fetching price data...")
    for t in tickers:
        df = yf.download(t, start="2018-10-01", end=date.today().strftime("%Y-%m-%d"),
                         auto_adjust=True, progress=False)
        if df.empty:
            print(f"  WARNING: no data for {t}")
            continue
        prices = {}
        for idx, row in df.iterrows():
            ds = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            val = row["Close"]
            prices[ds] = float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
        price_data[t] = prices
        print(f"  {t}: {len(prices)} days")
    return price_data

def quarterly_stock_returns(price_data, quarters):
    """Calculate forward quarterly USD return for each stock and GLUX."""
    stock_ret = {}  # quarter → {company: return}
    glux_ret = {}   # quarter → return

    for q in quarters:
        y, qn = parse_q(q)
        pub = publish_date(y, qn)
        ny, nq = next_q(y, qn)
        npub = publish_date(ny, nq)

        # GLUX (EUR → USD)
        gp = price_data.get("GLUX.PA", {})
        ep = price_data.get("EURUSD=X", {})
        g0, g1 = get_price(gp, pub), get_price(gp, npub)
        e0, e1 = get_price(ep, pub), get_price(ep, npub)
        if g0 and g1 and e0 and e1 and g0 > 0 and e0 > 0:
            glux_ret[q] = (g1 * e1) / (g0 * e0) - 1
        else:
            glux_ret[q] = None

        # Stock returns
        stock_ret[q] = {}
        for co, ticker in TICKER_MAP.items():
            sp = price_data.get(ticker, {})
            p0, p1 = get_price(sp, pub), get_price(sp, npub)
            if p0 and p1 and p0 > 0:
                ret = (p1 / p0) - 1
                if ticker in FX_MAP:
                    fx = price_data.get(FX_MAP[ticker], {})
                    f0, f1 = get_price(fx, pub), get_price(fx, npub)
                    if f0 and f1 and f0 > 0:
                        ret = (p1 * f1) / (p0 * f0) - 1
                stock_ret[q][co] = ret

    return stock_ret, glux_ret

# ══════════════════════════════════════════
# Portfolio construction & metrics
# ══════════════════════════════════════════

def cumulative(returns):
    c = 1.0
    for r in returns:
        c *= (1 + r)
    return c - 1

def max_drawdown(returns):
    c, peak, mdd = 1.0, 1.0, 0
    for r in returns:
        c *= (1 + r)
        peak = max(peak, c)
        mdd = max(mdd, (peak - c) / peak)
    return mdd

def cum_series(returns):
    s = [1.0]
    for r in returns:
        s.append(s[-1] * (1 + r))
    return s

def run_strategy(name, signals, stock_ret, glux_ret, quarters, use_short=False):
    """
    Strategy 1 (use_short=False): LONG when signal=LONG, CASH otherwise
    Strategy 2 (use_short=True):  LONG when signal=LONG, SHORT when signal=EXIT, CASH when FLAT
    """
    port_rets = []
    glux_rets = []
    details = []
    companies = list(SCORES.keys())

    for q in quarters:
        sig = signals.get(q, {})
        sret = stock_ret.get(q, {})
        gr = glux_ret.get(q)

        if gr is None:
            continue

        longs = [co for co in companies if sig.get(co) == "LONG"]
        shorts = [co for co in companies if sig.get(co) == "EXIT"] if use_short else []
        n_positions = len(longs) + len(shorts)

        if n_positions == 0:
            port_r = 0.0  # all cash
        else:
            weight = 1.0 / n_positions
            port_r = 0.0
            for co in longs:
                r = sret.get(co, 0)
                if r is not None:
                    port_r += weight * r
            for co in shorts:
                r = sret.get(co, 0)
                if r is not None:
                    port_r += weight * (-r)  # short = negative of return

        port_rets.append(port_r)
        glux_rets.append(gr)

        long_str = ", ".join([f"{TICKER_MAP[c]}" for c in longs]) if longs else ""
        short_str = ", ".join([f"{TICKER_MAP[c]}" for c in shorts]) if shorts else ""
        details.append((q, port_r, gr, long_str, short_str))

    return port_rets, glux_rets, details

def print_results(name, port_rets, glux_rets, details):
    n = len(port_rets)
    if n == 0:
        print(f"\n{name}: No data")
        return

    years = n / 4
    excess_rets = [p - g for p, g in zip(port_rets, glux_rets)]

    pc = cumulative(port_rets)
    gc = cumulative(glux_rets)
    ec = cumulative(excess_rets)

    pa = (1 + pc) ** (1 / years) - 1 if years > 0 else 0
    ga = (1 + gc) ** (1 / years) - 1 if years > 0 else 0

    pv = statistics.stdev(port_rets) * 2 if n > 1 else 0
    gv = statistics.stdev(glux_rets) * 2 if n > 1 else 0
    ev = statistics.stdev(excess_rets) * 2 if n > 1 else 0

    ps = pa / pv if pv > 0 else 0
    gs = ga / gv if gv > 0 else 0

    pmdd = max_drawdown(port_rets)
    gmdd = max_drawdown(glux_rets)

    pw = sum(1 for r in port_rets if r > 0) / n
    ew = sum(1 for e in excess_rets if e > 0) / n

    ir = (statistics.mean(excess_rets) * 4) / ev if ev > 0 else 0

    # Header
    print()
    print("=" * 110)
    print(f"  {name}")
    print("=" * 110)

    # Quarterly details
    print(f"\n{'Quarter':<10} | {'Portfolio':>10} | {'GLUX':>10} | {'Excess':>10} | {'Long':>20} | {'Short':>20}")
    print("-" * 110)
    pseries = cum_series(port_rets)
    gseries = cum_series(glux_rets)

    for i, (q, pr, gr, ls, ss) in enumerate(details):
        ex = pr - gr
        pos_str = ls if ls else "CASH"
        short_str = ss if ss else ""
        print(f"{q:<10} | {pr:>+9.2%} | {gr:>+9.2%} | {ex:>+9.2%} | {pos_str:<20} | {short_str:<20}")

    # Summary
    print()
    print("-" * 70)
    print(f"{'Metric':<35} | {'Strategy':>15} | {'GLUX':>15}")
    print("-" * 70)
    print(f"{'Cumulative Return':<35} | {pc:>+14.1%} | {gc:>+14.1%}")
    print(f"{'Annualized Return':<35} | {pa:>+14.1%} | {ga:>+14.1%}")
    print(f"{'Avg Quarterly Return':<35} | {statistics.mean(port_rets):>+14.2%} | {statistics.mean(glux_rets):>+14.2%}")
    print(f"{'Annualized Volatility':<35} | {pv:>14.1%} | {gv:>14.1%}")
    print(f"{'Sharpe Ratio (no Rf)':<35} | {ps:>14.2f} | {gs:>14.2f}")
    print(f"{'Max Drawdown':<35} | {pmdd:>14.1%} | {gmdd:>14.1%}")
    print(f"{'Win Rate (Q > 0)':<35} | {pw:>14.1%} | {sum(1 for r in glux_rets if r>0)/n:>14.1%}")
    print()
    print(f"{'--- vs GLUX ---':<35}")
    print(f"{'Cumulative Excess':<35} | {pc - gc:>+14.1%}")
    print(f"{'Avg Quarterly Excess':<35} | {statistics.mean(excess_rets):>+14.2%}")
    print(f"{'Excess Win Rate':<35} | {ew:>14.1%}")
    print(f"{'Information Ratio':<35} | {ir:>14.2f}")
    print(f"{'Max Drawdown':<35} | {max_drawdown(excess_rets):>14.1%}")
    print(f"{'Tracking Error (ann.)':<35} | {ev:>14.1%}")

    # Cumulative series
    print()
    print(f"{'Quarter':<10} | {'Strategy Cum':>14} | {'GLUX Cum':>14} | {'Excess Cum':>14}")
    print("-" * 60)
    eseries = cum_series(excess_rets)
    for i, (q, _, _, _, _) in enumerate(details):
        print(f"{q:<10} | {pseries[i+1]-1:>+13.1%} | {gseries[i+1]-1:>+13.1%} | {eseries[i+1]-1:>+13.1%}")

    # Drawdowns > 5%
    print()
    print(f"Drawdown periods (> 5%):")
    ppeak, cum = 1.0, 1.0
    dd_start = None
    for i, (q, pr, gr, _, _) in enumerate(details):
        cum *= (1 + pr)
        if cum > ppeak:
            if dd_start:
                print(f"  {dd_start} to {details[i-1][0]}: {-(ppeak_at_start - cum_at_trough)/ppeak_at_start:.1%}")
                dd_start = None
            ppeak = cum
        dd = (ppeak - cum) / ppeak
        if dd > 0.05 and dd_start is None:
            dd_start = q
            ppeak_at_start = ppeak
            cum_at_trough = cum
        elif dd > 0.05 and cum < cum_at_trough:
            cum_at_trough = cum

    if dd_start:
        print(f"  {dd_start} to {details[-1][0]}: {-(ppeak_at_start - cum_at_trough)/ppeak_at_start:.1%}")


def main():
    # Generate signals
    signals = generate_signals()
    companies = list(SCORES.keys())
    quarters = [q for q, _ in SCORES[companies[0]]]

    # Print signal timeline
    print("=" * 90)
    print("SIGNAL TIMELINE")
    print("Rules: Score>=0.3 enter, 3Q decline exit, 3Q rise re-enter")
    print(f"Universe: {', '.join(TICKER_MAP[c] for c in companies)}")
    print("=" * 90)
    print(f"\n{'Quarter':<10} | ", end="")
    for co in companies:
        print(f"{TICKER_MAP[co]:<18} | ", end="")
    print()
    print("-" * 80)

    for q in quarters:
        scores = {co: dict(SCORES[co]).get(q, 0) for co in companies}
        print(f"{q:<10} | ", end="")
        for co in companies:
            sig = signals[q][co]
            sc = scores[co]
            if sig == "LONG":
                label = f"LONG  ({sc:.3f})"
            elif sig == "EXIT":
                label = f"EXIT  ({sc:.3f})"
            else:
                label = f"---   ({sc:.3f})"
            print(f"{label:<18} | ", end="")
        print()

    # Fetch prices
    price_data = fetch_prices()
    stock_ret, glux_ret = quarterly_stock_returns(price_data, quarters)

    # Run Strategy 1: Long-only timing
    p1, g1, d1 = run_strategy("Strategy 1", signals, stock_ret, glux_ret, quarters, use_short=False)
    print_results("Strategy 1: Long-Only Timing (LONG or CASH)", p1, g1, d1)

    # Run Strategy 2: Long/Short
    p2, g2, d2 = run_strategy("Strategy 2", signals, stock_ret, glux_ret, quarters, use_short=True)
    print_results("Strategy 2: Long/Short (LONG, SHORT, or CASH)", p2, g2, d2)

    # Also run buy-and-hold equal weight as additional benchmark
    bh_rets = []
    bh_glux = []
    bh_details = []
    for q in quarters:
        gr = glux_ret.get(q)
        if gr is None:
            continue
        sret = stock_ret.get(q, {})
        valid = [(co, sret[co]) for co in companies if co in sret and sret[co] is not None]
        if valid:
            bhr = sum(r for _, r in valid) / len(valid)
        else:
            bhr = 0
        bh_rets.append(bhr)
        bh_glux.append(gr)
        hold_str = ", ".join(TICKER_MAP[co] for co, _ in valid)
        bh_details.append((q, bhr, gr, hold_str, ""))
    print_results("Benchmark: Buy & Hold Equal Weight (always hold all 3)", bh_rets, bh_glux, bh_details)

    # Comparison table
    print()
    print("=" * 90)
    print("STRATEGY COMPARISON")
    print("=" * 90)

    n1, n2, nb = len(p1), len(p2), len(bh_rets)
    metrics = [
        ("Cumulative Return", cumulative(p1), cumulative(p2), cumulative(bh_rets), cumulative(g1)),
        ("Annualized Return",
         (1+cumulative(p1))**(1/(n1/4))-1 if n1>0 else 0,
         (1+cumulative(p2))**(1/(n2/4))-1 if n2>0 else 0,
         (1+cumulative(bh_rets))**(1/(nb/4))-1 if nb>0 else 0,
         (1+cumulative(g1))**(1/(n1/4))-1 if n1>0 else 0),
        ("Avg Q Return",
         statistics.mean(p1), statistics.mean(p2), statistics.mean(bh_rets), statistics.mean(g1)),
        ("Volatility (ann.)",
         statistics.stdev(p1)*2, statistics.stdev(p2)*2, statistics.stdev(bh_rets)*2, statistics.stdev(g1)*2),
        ("Sharpe",
         ((1+cumulative(p1))**(1/(n1/4))-1)/(statistics.stdev(p1)*2) if statistics.stdev(p1)>0 else 0,
         ((1+cumulative(p2))**(1/(n2/4))-1)/(statistics.stdev(p2)*2) if statistics.stdev(p2)>0 else 0,
         ((1+cumulative(bh_rets))**(1/(nb/4))-1)/(statistics.stdev(bh_rets)*2) if statistics.stdev(bh_rets)>0 else 0,
         ((1+cumulative(g1))**(1/(n1/4))-1)/(statistics.stdev(g1)*2) if statistics.stdev(g1)>0 else 0),
        ("Max Drawdown", max_drawdown(p1), max_drawdown(p2), max_drawdown(bh_rets), max_drawdown(g1)),
        ("Win Rate",
         sum(1 for r in p1 if r>0)/n1, sum(1 for r in p2 if r>0)/n2,
         sum(1 for r in bh_rets if r>0)/nb, sum(1 for r in g1 if r>0)/n1),
    ]

    print(f"\n{'Metric':<22} | {'S1:Long-Only':>14} | {'S2:Long/Short':>14} | {'Buy&Hold 3':>14} | {'GLUX':>14}")
    print("-" * 90)
    for label, v1, v2, v3, v4 in metrics:
        if label == "Sharpe":
            print(f"{label:<22} | {v1:>14.2f} | {v2:>14.2f} | {v3:>14.2f} | {v4:>14.2f}")
        else:
            print(f"{label:<22} | {v1:>+13.1%} | {v2:>+13.1%} | {v3:>+13.1%} | {v4:>+13.1%}")

    # Excess vs GLUX
    e1 = [a-b for a,b in zip(p1,g1)]
    e2 = [a-b for a,b in zip(p2,g2)]
    eb = [a-b for a,b in zip(bh_rets,bh_glux)]
    print(f"\n{'--- vs GLUX ---':<22}")
    print(f"{'Cumulative Excess':<22} | {cumulative(p1)-cumulative(g1):>+13.1%} | {cumulative(p2)-cumulative(g2):>+13.1%} | {cumulative(bh_rets)-cumulative(bh_glux):>+13.1%} |")
    print(f"{'Excess Win Rate':<22} | {sum(1 for e in e1 if e>0)/len(e1):>13.1%} | {sum(1 for e in e2 if e>0)/len(e2):>13.1%} | {sum(1 for e in eb if e>0)/len(eb):>13.1%} |")

if __name__ == "__main__":
    main()

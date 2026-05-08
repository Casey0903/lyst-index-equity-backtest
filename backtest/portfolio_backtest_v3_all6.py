#!/usr/bin/env python3
"""
Portfolio backtest v3: ALL 6 high-coverage companies (no selection bias).

Purpose: Test what happens when you apply the SAME mechanical rules to ALL
high-coverage companies, without ex-post knowledge of which ones have
positive vs negative signal correlation.

Compares:
  A) All 6 companies (Prada, Tapestry, RL, Burberry, Kering, Moncler)
  B) Original 3 companies (Prada, Tapestry, RL) — for comparison

Same rules for both:
  - Entry: Score >= 0.3 → LONG
  - Exit: 3Q consecutive decline OR score <= 0 → flat
  - Re-entry: 3Q consecutive rise + score >= 0.3
  - Position sizing: equal weight among active longs, cash when no signal
"""
import sys, math, statistics
sys.stdout.reconfigure(encoding='utf-8')
from datetime import date, timedelta

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance"); exit(1)

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
    "Burberry": [
        ("Q4 2018", 0.600), ("Q1 2019", 0.545), ("Q2 2019", 0.570), ("Q3 2019", 0.485),
        ("Q4 2019", 0.460), ("Q1 2020", 0.430), ("Q2 2020", 0.500), ("Q3 2020", 0.365),
        ("Q4 2020", 0.395), ("Q1 2021", 0.305), ("Q2 2021", 0.425), ("Q3 2021", 0.425),
        ("Q4 2021", 0.425), ("Q1 2022", 0.425), ("Q2 2022", 0.535), ("Q3 2022", 0.535),
        ("Q4 2022", 0.095), ("Q1 2023", 0.255), ("Q2 2023", 0.310), ("Q3 2023", 0.715),
        ("Q4 2023", 0.650), ("Q1 2024", 0.455), ("Q2 2024", 0.310), ("Q3 2024", -0.300),
        ("Q4 2024", -0.270), ("Q1 2025", -0.240), ("Q2 2025", 0.245), ("Q3 2025", 0.490),
        ("Q4 2025", 0.700), ("Q1 2026", 0.640),
    ],
    "Kering": [
        ("Q4 2018", 0.503), ("Q1 2019", 0.603), ("Q2 2019", 0.697), ("Q3 2019", 0.643),
        ("Q4 2019", 0.700), ("Q1 2020", 0.589), ("Q2 2020", 0.700), ("Q3 2020", 0.763),
        ("Q4 2020", 0.848), ("Q1 2021", 0.790), ("Q2 2021", 0.741), ("Q3 2021", 0.695),
        ("Q4 2021", 0.724), ("Q1 2022", 0.595), ("Q2 2022", 0.619), ("Q3 2022", 0.646),
        ("Q4 2022", 0.651), ("Q1 2023", 0.234), ("Q2 2023", 0.361), ("Q3 2023", 0.326),
        ("Q4 2023", 0.543), ("Q1 2024", 0.522), ("Q2 2024", 0.597), ("Q3 2024", 0.611),
        ("Q4 2024", 0.475), ("Q1 2025", 0.280), ("Q2 2025", 0.235), ("Q3 2025", 0.449),
        ("Q4 2025", 0.690), ("Q1 2026", 0.765),
    ],
    "Moncler": [
        ("Q4 2018", 0.506), ("Q1 2019", 0.521), ("Q2 2019", 0.356), ("Q3 2019", 0.013),
        ("Q4 2019", 0.735), ("Q1 2020", 0.739), ("Q2 2020", 0.295), ("Q3 2020", 0.066),
        ("Q4 2020", 0.609), ("Q1 2021", 0.746), ("Q2 2021", 0.620), ("Q3 2021", 0.169),
        ("Q4 2021", 0.506), ("Q1 2022", 0.468), ("Q2 2022", 0.055), ("Q3 2022", 0),
        ("Q4 2022", 0.654), ("Q1 2023", 0.807), ("Q2 2023", 0.676), ("Q3 2023", 0.365),
        ("Q4 2023", 0.459), ("Q1 2024", 0.540), ("Q2 2024", 0.374), ("Q3 2024", 0.136),
        ("Q4 2024", 0.395), ("Q1 2025", 0.332), ("Q2 2025", 0.480), ("Q3 2025", 0.326),
        ("Q4 2025", 0.486), ("Q1 2026", 0.308),
    ],
}

TICKER_MAP = {
    "Prada Group": "1913.HK",
    "Tapestry": "TPR",
    "Ralph Lauren": "RL",
    "Burberry": "BRBY.L",
    "Kering": "KER.PA",
    "Moncler": "MONC.MI",
}

FX_MAP = {
    "1913.HK": "HKDUSD=X",
    "BRBY.L": "GBPUSD=X",
    "KER.PA": "EURUSD=X",
    "MONC.MI": "EURUSD=X",
}

def generate_signals(company_list):
    companies = company_list
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

            if s["position"] == "LONG":
                if score <= 0:
                    s["position"] = "EXIT"
                    s["exited"] = True
                    s["consecutive_decline"] = 0
                elif s["consecutive_decline"] >= 3:
                    s["position"] = "EXIT"
                    s["exited"] = True
            elif s["position"] == "EXIT":
                if s["consecutive_rise"] >= 3 and score >= 0.3:
                    s["position"] = "LONG"
                    s["exited"] = False
            elif s["position"] == "FLAT":
                if s["exited"]:
                    if s["consecutive_rise"] >= 3 and score >= 0.3:
                        s["position"] = "LONG"
                        s["exited"] = False
                else:
                    if score >= 0.3:
                        s["position"] = "LONG"
                        s["entered_ever"] = True

            signals[quarter][co] = s["position"]
            s["prev_score"] = score

    return signals

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
    tickers = list(set(list(TICKER_MAP.values()) + list(FX_MAP.values()) + ["GLUX.PA", "EURUSD=X"]))
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

def quarterly_returns(price_data, quarters, company_list):
    stock_ret = {}
    glux_ret = {}

    for q in quarters:
        y, qn = parse_q(q)
        pub = publish_date(y, qn)
        ny, nq = next_q(y, qn)
        npub = publish_date(ny, nq)

        gp = price_data.get("GLUX.PA", {})
        ep = price_data.get("EURUSD=X", {})
        g0, g1 = get_price(gp, pub), get_price(gp, npub)
        e0, e1 = get_price(ep, pub), get_price(ep, npub)
        if g0 and g1 and e0 and e1 and g0 > 0 and e0 > 0:
            glux_ret[q] = (g1 * e1) / (g0 * e0) - 1
        else:
            glux_ret[q] = None

        stock_ret[q] = {}
        for co in company_list:
            ticker = TICKER_MAP[co]
            sp = price_data.get(ticker, {})
            p0, p1 = get_price(sp, pub), get_price(sp, npub)
            if p0 and p1 and p0 > 0:
                ret = (p1 / p0) - 1
                if ticker in FX_MAP:
                    fx_ticker = FX_MAP[ticker]
                    if fx_ticker == "EURUSD=X":
                        fx = price_data.get("EURUSD=X", {})
                    else:
                        fx = price_data.get(fx_ticker, {})
                    f0, f1 = get_price(fx, pub), get_price(fx, npub)
                    if f0 and f1 and f0 > 0:
                        ret = (p1 * f1) / (p0 * f0) - 1
                stock_ret[q][co] = ret

    return stock_ret, glux_ret

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

def run_strategy(signals, stock_ret, glux_ret, quarters, company_list):
    port_rets = []
    glux_rets = []
    details = []

    for q in quarters:
        sig = signals.get(q, {})
        sret = stock_ret.get(q, {})
        gr = glux_ret.get(q)
        if gr is None:
            continue

        longs = [co for co in company_list if sig.get(co) == "LONG"]
        n_positions = len(longs)

        if n_positions == 0:
            port_r = 0.0
        else:
            weight = 1.0 / n_positions
            port_r = 0.0
            for co in longs:
                r = sret.get(co, 0)
                if r is not None:
                    port_r += weight * r

        port_rets.append(port_r)
        glux_rets.append(gr)
        long_tickers = [TICKER_MAP[c] for c in longs]
        details.append((q, port_r, gr, long_tickers))

    return port_rets, glux_rets, details

def compute_metrics(port_rets, glux_rets):
    n = len(port_rets)
    if n == 0:
        return {}
    years = n / 4
    excess_rets = [p - g for p, g in zip(port_rets, glux_rets)]

    pc = cumulative(port_rets)
    gc = cumulative(glux_rets)
    pa = (1 + pc) ** (1 / years) - 1 if years > 0 else 0
    pv = statistics.stdev(port_rets) * 2 if n > 1 else 0
    ps = pa / pv if pv > 0 else 0
    pmdd = max_drawdown(port_rets)
    pw = sum(1 for r in port_rets if r > 0) / n
    ew = sum(1 for e in excess_rets if e > 0) / n
    ev = statistics.stdev(excess_rets) * 2 if n > 1 else 0
    ir = (statistics.mean(excess_rets) * 4) / ev if ev > 0 else 0

    return {
        "cum": pc, "ann": pa, "vol": pv, "sharpe": ps,
        "mdd": pmdd, "win": pw, "excess_cum": pc - gc,
        "excess_win": ew, "ir": ir, "n": n,
    }

def main():
    all6 = ["Prada Group", "Tapestry", "Ralph Lauren", "Burberry", "Kering", "Moncler"]
    orig3 = ["Prada Group", "Tapestry", "Ralph Lauren"]
    quarters = [q for q, _ in SCORES["Prada Group"]]

    sig_all6 = generate_signals(all6)
    sig_orig3 = generate_signals(orig3)

    # Print signal timeline for all 6
    print("=" * 140)
    print("SIGNAL TIMELINE — ALL 6 HIGH-COVERAGE COMPANIES")
    print("Same mechanical rules: Score>=0.3 enter, 3Q decline exit, 3Q rise re-enter")
    print("=" * 140)
    print(f"\n{'Quarter':<10}", end="")
    for co in all6:
        print(f" | {TICKER_MAP[co]:<18}", end="")
    print()
    print("-" * 140)

    for q in quarters:
        scores = {co: dict(SCORES[co]).get(q, 0) for co in all6}
        print(f"{q:<10}", end="")
        for co in all6:
            sig = sig_all6[q][co]
            sc = scores[co]
            if sig == "LONG":
                label = f"LONG  ({sc:+.3f})"
            elif sig == "EXIT":
                label = f"EXIT  ({sc:+.3f})"
            else:
                label = f"---   ({sc:+.3f})"
            print(f" | {label:<18}", end="")
        print()

    # Fetch prices
    price_data = fetch_prices()
    stock_ret_all, glux_ret = quarterly_returns(price_data, quarters, all6)

    # Run strategies
    p_all6, g_all6, d_all6 = run_strategy(sig_all6, stock_ret_all, glux_ret, quarters, all6)
    p_orig3, g_orig3, d_orig3 = run_strategy(sig_orig3, stock_ret_all, glux_ret, quarters, orig3)

    # Also buy-and-hold all 6
    bh6_rets, bh6_glux, bh6_details = [], [], []
    for q in quarters:
        gr = glux_ret.get(q)
        if gr is None:
            continue
        sret = stock_ret_all.get(q, {})
        valid = [(co, sret[co]) for co in all6 if co in sret and sret[co] is not None]
        if valid:
            bhr = sum(r for _, r in valid) / len(valid)
        else:
            bhr = 0
        bh6_rets.append(bhr)
        bh6_glux.append(gr)

    m_all6 = compute_metrics(p_all6, g_all6)
    m_orig3 = compute_metrics(p_orig3, g_orig3)
    m_glux = compute_metrics(g_all6, g_all6)  # GLUX vs itself
    m_bh6 = compute_metrics(bh6_rets, bh6_glux)

    # Print quarterly details for all 6
    print()
    print("=" * 120)
    print("QUARTERLY DETAILS — ALL 6 COMPANIES (Long-Only Timing)")
    print("=" * 120)
    print(f"{'Quarter':<10} | {'Portfolio':>10} | {'GLUX':>10} | {'Excess':>10} | {'Holdings':<50}")
    print("-" * 120)

    for q, pr, gr, longs in d_all6:
        ex = pr - gr
        hold_str = ", ".join(longs) if longs else "CASH"
        print(f"{q:<10} | {pr:>+9.2%} | {gr:>+9.2%} | {ex:>+9.2%} | {hold_str:<50}")

    # Print quarterly details for orig 3
    print()
    print("=" * 120)
    print("QUARTERLY DETAILS — ORIGINAL 3 COMPANIES (Long-Only Timing)")
    print("=" * 120)
    print(f"{'Quarter':<10} | {'Portfolio':>10} | {'GLUX':>10} | {'Excess':>10} | {'Holdings':<50}")
    print("-" * 120)

    for q, pr, gr, longs in d_orig3:
        ex = pr - gr
        hold_str = ", ".join(longs) if longs else "CASH"
        print(f"{q:<10} | {pr:>+9.2%} | {gr:>+9.2%} | {ex:>+9.2%} | {hold_str:<50}")

    # ═══════════════════════════════════
    # COMPARISON TABLE
    # ═══════════════════════════════════
    print()
    print("=" * 100)
    print("STRATEGY COMPARISON — SELECTION BIAS TEST")
    print("=" * 100)

    gc = cumulative(g_all6)
    ga = (1 + gc) ** (1 / (len(g_all6)/4)) - 1
    gv = statistics.stdev(g_all6) * 2
    gs = ga / gv if gv > 0 else 0
    gmdd = max_drawdown(g_all6)
    gwin = sum(1 for r in g_all6 if r > 0) / len(g_all6)

    print(f"\n{'Metric':<28} | {'All 6 (unfiltered)':>18} | {'Orig 3 (filtered)':>18} | {'B&H 6 stocks':>18} | {'GLUX':>14}")
    print("-" * 105)

    rows = [
        ("Cumulative Return", m_all6["cum"], m_orig3["cum"], m_bh6["cum"], gc),
        ("Annualized Return", m_all6["ann"], m_orig3["ann"], m_bh6["ann"], ga),
        ("Annualized Volatility", m_all6["vol"], m_orig3["vol"], m_bh6["vol"], gv),
        ("Sharpe (no Rf)", m_all6["sharpe"], m_orig3["sharpe"], m_bh6["sharpe"], gs),
        ("Max Drawdown", m_all6["mdd"], m_orig3["mdd"], m_bh6["mdd"], gmdd),
        ("Win Rate (Q > 0)", m_all6["win"], m_orig3["win"], m_bh6["win"], gwin),
    ]
    for label, v1, v2, v3, v4 in rows:
        if "Sharpe" in label:
            print(f"{label:<28} | {v1:>18.2f} | {v2:>18.2f} | {v3:>18.2f} | {v4:>14.2f}")
        else:
            print(f"{label:<28} | {v1:>+17.1%} | {v2:>+17.1%} | {v3:>+17.1%} | {v4:>+13.1%}")

    print(f"\n{'--- vs GLUX ---':<28}")
    e_all6 = [a-b for a,b in zip(p_all6, g_all6)]
    e_orig3 = [a-b for a,b in zip(p_orig3, g_orig3)]
    e_bh6 = [a-b for a,b in zip(bh6_rets, bh6_glux)]
    print(f"{'Cumulative Excess':<28} | {m_all6['excess_cum']:>+17.1%} | {m_orig3['excess_cum']:>+17.1%} | {m_bh6['excess_cum']:>+17.1%} |")
    print(f"{'Excess Win Rate':<28} | {m_all6['excess_win']:>17.1%} | {m_orig3['excess_win']:>17.1%} | {m_bh6['excess_win']:>17.1%} |")
    print(f"{'Information Ratio':<28} | {m_all6['ir']:>18.2f} | {m_orig3['ir']:>18.2f} | {m_bh6['ir']:>18.2f} |")

    # Selection bias quantification
    print()
    print("=" * 80)
    print("SELECTION BIAS QUANTIFICATION")
    print("=" * 80)
    bias = m_orig3["cum"] - m_all6["cum"]
    bias_ann = m_orig3["ann"] - m_all6["ann"]
    bias_sharpe = m_orig3["sharpe"] - m_all6["sharpe"]
    print(f"  Cumulative return gap (filtered - unfiltered): {bias:+.1%}")
    print(f"  Annualized return gap:                         {bias_ann:+.1%}")
    print(f"  Sharpe ratio gap:                              {bias_sharpe:+.2f}")
    print()
    if m_all6["cum"] > 0 and m_all6["cum"] > gc:
        print(f"  Even WITHOUT filtering, the strategy beats GLUX:")
        print(f"    Unfiltered: {m_all6['cum']:+.1%} vs GLUX {gc:+.1%} (excess {m_all6['excess_cum']:+.1%})")
        print(f"    Filtered:   {m_orig3['cum']:+.1%} vs GLUX {gc:+.1%} (excess {m_orig3['excess_cum']:+.1%})")
    else:
        print(f"  WARNING: Unfiltered strategy does NOT beat GLUX")
        print(f"    Unfiltered: {m_all6['cum']:+.1%} vs GLUX {gc:+.1%}")
        print(f"    The alpha in the filtered version may be entirely due to selection bias")

    # Per-company contribution analysis
    print()
    print("=" * 80)
    print("PER-COMPANY CONTRIBUTION (when LONG signal active)")
    print("=" * 80)
    print(f"{'Company':<15} | {'Quarters LONG':>13} | {'Avg Q Return':>13} | {'Avg Excess':>13} | {'Win Rate':>10}")
    print("-" * 75)

    for co in all6:
        co_rets = []
        co_excess = []
        for q, pr, gr, longs in d_all6:
            ticker = TICKER_MAP[co]
            if ticker in longs:
                sret = stock_ret_all.get(q, {}).get(co, 0)
                if sret is not None:
                    co_rets.append(sret)
                    co_excess.append(sret - gr)
        if co_rets:
            avg_r = statistics.mean(co_rets)
            avg_e = statistics.mean(co_excess)
            win = sum(1 for e in co_excess if e > 0) / len(co_excess)
            print(f"{TICKER_MAP[co]:<15} | {len(co_rets):>13} | {avg_r:>+12.2%} | {avg_e:>+12.2%} | {win:>9.0%}")
        else:
            print(f"{TICKER_MAP[co]:<15} | {'0':>13} | {'N/A':>13} | {'N/A':>13} | {'N/A':>10}")

if __name__ == "__main__":
    main()

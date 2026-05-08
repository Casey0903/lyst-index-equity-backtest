#!/usr/bin/env python3
"""
Grid search: test 12 entry/exit rule combinations on ALL 6 high-coverage companies.
No company filtering — pure mechanical rules applied equally to all.

Entry variants:
  E1: Score >= 0.3 (original)
  E2: Score >= 0.3 AND score > prev_score (momentum)
  E3: Score >= 0.5 (high threshold)

Exit variants:
  X1: 3Q consecutive decline (original)
  X2: 2Q consecutive decline (fast)
  X3: Score drops below 0.3 (absolute floor)
  X4: 2Q consecutive decline OR score < 0.3 (combined)

Re-entry: aligned with entry — requires 3Q consecutive rise + entry threshold met.
For momentum entry, 3Q rise naturally satisfies the "rising" condition.
"""
import sys, statistics
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
    "Prada Group": "1913.HK", "Tapestry": "TPR", "Ralph Lauren": "RL",
    "Burberry": "BRBY.L", "Kering": "KER.PA", "Moncler": "MONC.MI",
}
FX_MAP = {
    "1913.HK": "HKDUSD=X", "BRBY.L": "GBPUSD=X",
    "KER.PA": "EURUSD=X", "MONC.MI": "EURUSD=X",
}

ALL6 = ["Prada Group", "Tapestry", "Ralph Lauren", "Burberry", "Kering", "Moncler"]
QUARTERS = [q for q, _ in SCORES["Prada Group"]]


def generate_signals(companies, entry_threshold, require_momentum, exit_decline_q, exit_floor):
    """
    Parameterized signal engine.

    entry_threshold: float (0.3 or 0.5)
    require_momentum: bool — if True, score must be > prev_score to enter (no prev = no entry)
    exit_decline_q: int (2 or 3) — consecutive decline quarters to trigger exit
    exit_floor: float or None — if score drops below this, exit immediately

    Re-entry: exit_decline_q consecutive rises + score >= entry_threshold
    """
    state = {}
    for co in companies:
        state[co] = {
            "position": "FLAT",
            "prev_score": None,
            "consecutive_decline": 0,
            "consecutive_rise": 0,
            "exited": False,
        }

    signals = {}
    for qi, quarter in enumerate(QUARTERS):
        signals[quarter] = {}
        for co in companies:
            s = state[co]
            score = SCORES[co][qi][1]
            prev = s["prev_score"]

            # Track consecutive decline / rise (only when both scores > 0)
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
                # Check exit conditions
                exited = False
                if score <= 0:
                    exited = True
                elif s["consecutive_decline"] >= exit_decline_q:
                    exited = True
                elif exit_floor is not None and score < exit_floor:
                    exited = True

                if exited:
                    s["position"] = "EXIT"
                    s["exited"] = True

            elif s["position"] in ("EXIT", "FLAT"):
                if s["exited"]:
                    # Re-entry: need exit_decline_q consecutive rises + threshold
                    if s["consecutive_rise"] >= exit_decline_q and score >= entry_threshold:
                        if require_momentum:
                            if prev is not None and score > prev:
                                s["position"] = "LONG"
                                s["exited"] = False
                        else:
                            s["position"] = "LONG"
                            s["exited"] = False
                else:
                    # First entry
                    if score >= entry_threshold:
                        if require_momentum:
                            if prev is not None and score > prev:
                                s["position"] = "LONG"
                        else:
                            s["position"] = "LONG"

            signals[quarter][co] = s["position"]
            s["prev_score"] = score

    return signals


# ═══════════════════════════════════════
# Price data (same as v3)
# ═══════════════════════════════════════

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

def quarterly_returns(price_data):
    stock_ret = {}
    glux_ret = {}

    for q in QUARTERS:
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
        for co in ALL6:
            ticker = TICKER_MAP[co]
            sp = price_data.get(ticker, {})
            p0, p1 = get_price(sp, pub), get_price(sp, npub)
            if p0 and p1 and p0 > 0:
                ret = (p1 / p0) - 1
                if ticker in FX_MAP:
                    fx_ticker = FX_MAP[ticker]
                    fx = price_data.get(fx_ticker, {})
                    f0, f1 = get_price(fx, pub), get_price(fx, npub)
                    if f0 and f1 and f0 > 0:
                        ret = (p1 * f1) / (p0 * f0) - 1
                stock_ret[q][co] = ret

    return stock_ret, glux_ret


def run_backtest(signals, stock_ret, glux_ret, companies):
    port_rets = []
    glux_rets = []
    details = []

    for q in QUARTERS:
        gr = glux_ret.get(q)
        if gr is None:
            continue
        sig = signals.get(q, {})
        sret = stock_ret.get(q, {})

        longs = [co for co in companies if sig.get(co) == "LONG"]
        if not longs:
            port_r = 0.0
        else:
            weight = 1.0 / len(longs)
            port_r = sum(weight * sret.get(co, 0) for co in longs)

        port_rets.append(port_r)
        glux_rets.append(gr)
        details.append((q, port_r, gr, [TICKER_MAP[c] for c in longs]))

    return port_rets, glux_rets, details


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


def main():
    price_data = fetch_prices()
    stock_ret, glux_ret = quarterly_returns(price_data)

    # GLUX baseline metrics
    glux_list = [glux_ret[q] for q in QUARTERS if glux_ret.get(q) is not None]
    glux_cum = cumulative(glux_list)

    # Define grid
    entry_configs = [
        ("E1: Score>=0.3",        0.3, False),
        ("E2: Score>=0.3+动量",    0.3, True),
        ("E3: Score>=0.5",        0.5, False),
    ]
    exit_configs = [
        ("X1: 3Q下滑",           3, None),
        ("X2: 2Q下滑",           2, None),
        ("X3: 跌破0.3",          99, 0.3),   # 99 = never trigger pure decline exit, only floor
        ("X4: 2Q下滑或跌破0.3",   2, 0.3),
    ]

    results = []

    for e_name, e_thresh, e_momentum in entry_configs:
        for x_name, x_decline, x_floor in exit_configs:
            label = f"{e_name} + {x_name}"
            signals = generate_signals(ALL6, e_thresh, e_momentum, x_decline, x_floor)
            p_rets, g_rets, details = run_backtest(signals, stock_ret, glux_ret, ALL6)

            n = len(p_rets)
            if n == 0:
                continue

            years = n / 4
            pc = cumulative(p_rets)
            pa = (1 + pc) ** (1 / years) - 1 if years > 0 else 0
            pv = statistics.stdev(p_rets) * 2 if n > 1 else 0
            ps = pa / pv if pv > 0 else 0
            pmdd = max_drawdown(p_rets)
            pw = sum(1 for r in p_rets if r > 0) / n

            excess = [a - b for a, b in zip(p_rets, g_rets)]
            ew = sum(1 for e in excess if e > 0) / n
            excess_cum = pc - glux_cum

            # Count active quarters (not cash)
            active_q = sum(1 for _, _, _, longs in details if longs)

            results.append({
                "label": label,
                "cum": pc, "ann": pa, "vol": pv, "sharpe": ps,
                "mdd": pmdd, "win": pw, "excess_cum": excess_cum,
                "excess_win": ew, "active_q": active_q,
                "details": details,
            })

    # Also run original 3-company filtered strategy for reference
    orig3 = ["Prada Group", "Tapestry", "Ralph Lauren"]
    sig_orig = generate_signals(orig3, 0.3, False, 3, None)
    p_orig, g_orig, d_orig = run_backtest(sig_orig, stock_ret, glux_ret, orig3)
    n_orig = len(p_orig)
    pc_orig = cumulative(p_orig)
    pa_orig = (1 + pc_orig) ** (1 / (n_orig / 4)) - 1
    pv_orig = statistics.stdev(p_orig) * 2
    ps_orig = pa_orig / pv_orig if pv_orig > 0 else 0
    pmdd_orig = max_drawdown(p_orig)

    # ═══════════════════════════════════
    # Print results
    # ═══════════════════════════════════
    print()
    print("=" * 150)
    print("GRID SEARCH: 12 ENTRY/EXIT RULE COMBINATIONS — ALL 6 COMPANIES")
    print("=" * 150)

    # Sort by cumulative return
    results.sort(key=lambda x: x["cum"], reverse=True)

    print(f"\n{'#':>2} | {'Strategy':<35} | {'Cumulative':>11} | {'Ann.Return':>11} | {'Sharpe':>7} | {'MaxDD':>8} | {'ExcessCum':>11} | {'ExWin%':>7} | {'ActiveQ':>8}")
    print("-" * 150)

    # Reference rows
    print(f"{'R1':>2} | {'[REF] 原版3家筛选后':<35} | {pc_orig:>+10.1%} | {pa_orig:>+10.1%} | {ps_orig:>7.2f} | {pmdd_orig:>7.1%} | {pc_orig-glux_cum:>+10.1%} | {'':>7} | {'':>8}")
    print(f"{'R2':>2} | {'[REF] GLUX基准':<35} | {glux_cum:>+10.1%} | {'':>11} | {'':>7} | {'':>8} | {'':>11} | {'':>7} | {'':>8}")
    print("-" * 150)

    for i, r in enumerate(results, 1):
        beat_glux = "✓" if r["excess_cum"] > 0 else "✗"
        print(f"{i:>2} | {r['label']:<35} | {r['cum']:>+10.1%} | {r['ann']:>+10.1%} | {r['sharpe']:>7.2f} | {r['mdd']:>7.1%} | {r['excess_cum']:>+10.1%} | {r['excess_win']:>6.0%} | {r['active_q']:>5}/{n_orig}")

    # ═══════════════════════════════════
    # Top 3 strategies: print quarterly details
    # ═══════════════════════════════════
    for rank, r in enumerate(results[:3], 1):
        print()
        print("=" * 120)
        print(f"TOP {rank}: {r['label']}")
        print(f"累计: {r['cum']:+.1%} | 年化: {r['ann']:+.1%} | Sharpe: {r['sharpe']:.2f} | 最大回撤: {r['mdd']:.1%} | 超额: {r['excess_cum']:+.1%}")
        print("=" * 120)
        print(f"{'Quarter':<10} | {'Portfolio':>10} | {'GLUX':>10} | {'Excess':>10} | {'Holdings':<55}")
        print("-" * 120)
        for q, pr, gr, longs in r["details"]:
            ex = pr - gr
            hold_str = ", ".join(longs) if longs else "CASH"
            print(f"{q:<10} | {pr:>+9.2%} | {gr:>+9.2%} | {ex:>+9.2%} | {hold_str:<55}")

    # ═══════════════════════════════════
    # Per-company breakdown for top strategy
    # ═══════════════════════════════════
    best = results[0]
    print()
    print("=" * 80)
    print(f"TOP 1 PER-COMPANY BREAKDOWN: {best['label']}")
    print("=" * 80)
    print(f"{'Company':<15} | {'Q LONG':>7} | {'Avg Return':>11} | {'Avg Excess':>11} | {'Win%':>6}")
    print("-" * 60)
    for co in ALL6:
        ticker = TICKER_MAP[co]
        co_rets, co_ex = [], []
        for q, pr, gr, longs in best["details"]:
            if ticker in longs:
                sr = stock_ret.get(q, {}).get(co, 0)
                if sr is not None:
                    co_rets.append(sr)
                    co_ex.append(sr - gr)
        if co_rets:
            print(f"{ticker:<15} | {len(co_rets):>7} | {statistics.mean(co_rets):>+10.2%} | {statistics.mean(co_ex):>+10.2%} | {sum(1 for e in co_ex if e>0)/len(co_ex):>5.0%}")
        else:
            print(f"{ticker:<15} | {'0':>7} | {'N/A':>11} | {'N/A':>11} | {'N/A':>6}")


if __name__ == "__main__":
    main()

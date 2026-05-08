#!/usr/bin/env python3
"""
Walk-forward backtest: at each quarter, use ONLY past data to decide
which companies to trade. No hindsight.

Core idea: compute trailing correlation of (company score) vs (forward stock return)
using a rolling window. Only trade companies where trailing correlation > 0.

Variants tested:
  WF1: Walk-forward correlation filter (8Q window) + Score>=0.3 + 跌破0.3 exit
  WF2: Walk-forward (8Q) + Score>=0.3 + 3Q decline exit
  WF3: Walk-forward (8Q) + require 4Q consecutive on list + Score>=0.3 + 跌破0.3 exit
  WF4: Walk-forward (6Q shorter window) + Score>=0.3 + 跌破0.3 exit

Plus reference strategies for comparison.
"""
import sys, statistics, math
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
ALL6 = list(SCORES.keys())
QUARTERS = [q for q, _ in SCORES["Prada Group"]]


# ═══════════════════════════════════
# Price utilities
# ═══════════════════════════════════

def parse_q(s):
    parts = s.strip().split()
    return int(parts[1]), int(parts[0][1:])

def next_q(y, q):
    return (y + 1, 1) if q == 4 else (y, q + 1)

def publish_date(y, q):
    if q == 4: return date(y + 1, 1, 25)
    return date(y, [4, 7, 10][q - 1], 25)

def get_price(prices, target, window=10):
    for delta in range(window):
        d = (target + timedelta(days=delta)).strftime("%Y-%m-%d")
        if d in prices: return prices[d]
    for delta in range(1, window):
        d = (target - timedelta(days=delta)).strftime("%Y-%m-%d")
        if d in prices: return prices[d]
    return None

def fetch_prices():
    tickers = list(set(list(TICKER_MAP.values()) + list(FX_MAP.values()) + ["GLUX.PA", "EURUSD=X"]))
    price_data = {}
    print("Fetching price data...")
    for t in tickers:
        df = yf.download(t, start="2018-10-01", end=date.today().strftime("%Y-%m-%d"),
                         auto_adjust=True, progress=False)
        if df.empty: continue
        prices = {}
        for idx, row in df.iterrows():
            ds = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            val = row["Close"]
            prices[ds] = float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
        price_data[t] = prices
        print(f"  {t}: {len(prices)} days")
    return price_data

def compute_all_returns(price_data):
    stock_ret, glux_ret = {}, {}
    for q in QUARTERS:
        y, qn = parse_q(q)
        pub = publish_date(y, qn)
        ny, nq = next_q(y, qn)
        npub = publish_date(ny, nq)

        gp, ep = price_data.get("GLUX.PA", {}), price_data.get("EURUSD=X", {})
        g0, g1 = get_price(gp, pub), get_price(gp, npub)
        e0, e1 = get_price(ep, pub), get_price(ep, npub)
        glux_ret[q] = (g1*e1)/(g0*e0)-1 if g0 and g1 and e0 and e1 and g0>0 and e0>0 else None

        stock_ret[q] = {}
        for co in ALL6:
            ticker = TICKER_MAP[co]
            sp = price_data.get(ticker, {})
            p0, p1 = get_price(sp, pub), get_price(sp, npub)
            if p0 and p1 and p0 > 0:
                ret = (p1/p0) - 1
                if ticker in FX_MAP:
                    fx = price_data.get(FX_MAP[ticker], {})
                    f0, f1 = get_price(fx, pub), get_price(fx, npub)
                    if f0 and f1 and f0 > 0:
                        ret = (p1*f1)/(p0*f0) - 1
                stock_ret[q][co] = ret
    return stock_ret, glux_ret


# ═══════════════════════════════════
# Correlation computation
# ═══════════════════════════════════

def pearson_r(x, y):
    n = len(x)
    if n < 3: return None
    mx, my = sum(x)/n, sum(y)/n
    sx = sum((xi-mx)**2 for xi in x)
    sy = sum((yi-my)**2 for yi in y)
    if sx == 0 or sy == 0: return None
    sxy = sum((xi-mx)*(yi-my) for xi, yi in zip(x, y))
    return sxy / math.sqrt(sx * sy)

def trailing_correlation(co, qi, stock_ret, window, min_data):
    """
    At quarter qi, compute correlation of (score[t], forward_return[t])
    for t in [qi-window, qi-1].

    forward_return[t] = stock return earned during period after seeing score[t].
    This return is already realized by time we're at qi.
    """
    scores_list = []
    returns_list = []

    start = max(0, qi - window)
    for t in range(start, qi):
        q_label = QUARTERS[t]
        score = SCORES[co][t][1]
        ret = stock_ret.get(q_label, {}).get(co)
        if score != 0 and ret is not None:
            scores_list.append(score)
            returns_list.append(ret)

    if len(scores_list) < min_data:
        return None
    return pearson_r(scores_list, returns_list)


def consecutive_on_list(co, qi, required):
    """Check if company has been on list (score > 0) for 'required' consecutive quarters ending at qi."""
    for t in range(qi, qi - required, -1):
        if t < 0:
            return False
        if SCORES[co][t][1] <= 0:
            return False
    return True


# ═══════════════════════════════════
# Walk-forward signal engine
# ═══════════════════════════════════

def walkforward_signals(stock_ret, corr_window=8, min_corr_data=4, corr_threshold=0.0,
                         entry_threshold=0.3, exit_decline_q=99, exit_floor=0.3,
                         require_consec=0, new_entrant_allowed=True):
    """
    Walk-forward signal generation.

    At each quarter qi:
    1. For each company, compute trailing correlation over past corr_window quarters
    2. Company is "eligible" if: correlation > corr_threshold (or insufficient data + new_entrant_allowed)
    3. If require_consec > 0, also require that many consecutive quarters on list
    4. Apply entry/exit rules only to eligible companies
    """
    state = {}
    for co in ALL6:
        state[co] = {
            "position": "FLAT", "prev_score": None,
            "consecutive_decline": 0, "consecutive_rise": 0, "exited": False,
        }

    signals = {}
    corr_log = {}

    for qi, quarter in enumerate(QUARTERS):
        signals[quarter] = {}
        corr_log[quarter] = {}

        for co in ALL6:
            s = state[co]
            score = SCORES[co][qi][1]
            prev = s["prev_score"]

            # Compute trailing correlation (using only past data)
            corr = trailing_correlation(co, qi, stock_ret, corr_window, min_corr_data)
            corr_log[quarter][co] = corr

            # Determine eligibility
            has_enough_data = corr is not None
            if has_enough_data:
                eligible = corr > corr_threshold
            else:
                eligible = new_entrant_allowed

            # Consecutive on-list check
            if require_consec > 0 and not consecutive_on_list(co, qi, require_consec):
                eligible = False

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
                # Check exit: always apply exit rules regardless of eligibility
                exited = False
                if score <= 0:
                    exited = True
                elif s["consecutive_decline"] >= exit_decline_q:
                    exited = True
                elif exit_floor is not None and score < exit_floor:
                    exited = True
                elif not eligible:
                    exited = True  # Correlation turned negative → exit

                if exited:
                    s["position"] = "EXIT"
                    s["exited"] = True

            elif s["position"] in ("EXIT", "FLAT"):
                if eligible:
                    if s["exited"]:
                        # Re-entry
                        reentry_q = max(exit_decline_q, 3) if exit_decline_q < 99 else 3
                        if s["consecutive_rise"] >= reentry_q and score >= entry_threshold:
                            s["position"] = "LONG"
                            s["exited"] = False
                    else:
                        if score >= entry_threshold:
                            s["position"] = "LONG"

            signals[quarter][co] = s["position"]
            s["prev_score"] = score

    return signals, corr_log


# ═══════════════════════════════════
# Simple signal engine (for reference strategies)
# ═══════════════════════════════════

def simple_signals(companies, entry_threshold, exit_decline_q, exit_floor):
    state = {}
    for co in companies:
        state[co] = {
            "position": "FLAT", "prev_score": None,
            "consecutive_decline": 0, "consecutive_rise": 0, "exited": False,
        }
    signals = {}
    for qi, quarter in enumerate(QUARTERS):
        signals[quarter] = {}
        for co in companies:
            s = state[co]
            score = SCORES[co][qi][1]
            prev = s["prev_score"]
            if prev is not None and prev > 0 and score > 0:
                if score < prev: s["consecutive_decline"] += 1; s["consecutive_rise"] = 0
                elif score > prev: s["consecutive_rise"] += 1; s["consecutive_decline"] = 0
                else: s["consecutive_decline"] = 0; s["consecutive_rise"] = 0
            elif score <= 0: s["consecutive_decline"] = 0; s["consecutive_rise"] = 0

            if s["position"] == "LONG":
                ex = False
                if score <= 0: ex = True
                elif s["consecutive_decline"] >= exit_decline_q: ex = True
                elif exit_floor is not None and score < exit_floor: ex = True
                if ex: s["position"] = "EXIT"; s["exited"] = True
            elif s["position"] in ("EXIT", "FLAT"):
                if s["exited"]:
                    if s["consecutive_rise"] >= exit_decline_q and score >= entry_threshold:
                        s["position"] = "LONG"; s["exited"] = False
                else:
                    if score >= entry_threshold: s["position"] = "LONG"
            signals[quarter][co] = s["position"]
            s["prev_score"] = score
        for co in ALL6:
            if co not in companies:
                signals[quarter][co] = "FLAT"
    return signals


# ═══════════════════════════════════
# Backtest engine
# ═══════════════════════════════════

def run_backtest(signals, stock_ret, glux_ret):
    port_rets, glux_rets, details = [], [], []
    for q in QUARTERS:
        gr = glux_ret.get(q)
        if gr is None: continue
        sret = stock_ret.get(q, {})
        longs = [co for co in ALL6 if signals.get(q, {}).get(co) == "LONG"]
        if not longs:
            port_r = 0.0
        else:
            w = 1.0 / len(longs)
            port_r = sum(w * sret.get(co, 0) for co in longs)
        port_rets.append(port_r)
        glux_rets.append(gr)
        details.append((q, port_r, gr, [TICKER_MAP[c] for c in longs]))
    return port_rets, glux_rets, details

def cumulative(rets):
    c = 1.0
    for r in rets: c *= (1+r)
    return c - 1

def max_drawdown(rets):
    c, peak, mdd = 1.0, 1.0, 0
    for r in rets:
        c *= (1+r); peak = max(peak, c); mdd = max(mdd, (peak-c)/peak)
    return mdd

def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def t_test(data):
    n = len(data)
    if n < 2: return 0, 1.0
    m = statistics.mean(data)
    se = statistics.stdev(data) / math.sqrt(n)
    if se == 0: return float('inf'), 0.0
    t = m / se
    return t, 2 * (1 - normal_cdf(abs(t)))


# ═══════════════════════════════════
# Main
# ═══════════════════════════════════

def main():
    price_data = fetch_prices()
    stock_ret, glux_ret = compute_all_returns(price_data)

    strategies = {}

    # WF1: Walk-forward 8Q + Score>=0.3 + 跌破0.3 exit
    sig_wf1, corr_wf1 = walkforward_signals(stock_ret, corr_window=8, min_corr_data=4,
                                              entry_threshold=0.3, exit_floor=0.3)
    strategies["WF1: 8Q滚动验证+跌破0.3退出"] = (sig_wf1, corr_wf1)

    # WF2: Walk-forward 8Q + Score>=0.3 + 3Q decline exit
    sig_wf2, corr_wf2 = walkforward_signals(stock_ret, corr_window=8, min_corr_data=4,
                                              entry_threshold=0.3, exit_decline_q=3, exit_floor=None)
    strategies["WF2: 8Q滚动验证+3Q下滑退出"] = (sig_wf2, corr_wf2)

    # WF3: Walk-forward 8Q + 4Q consecutive + Score>=0.3 + 跌破0.3 exit
    sig_wf3, corr_wf3 = walkforward_signals(stock_ret, corr_window=8, min_corr_data=4,
                                              entry_threshold=0.3, exit_floor=0.3,
                                              require_consec=4)
    strategies["WF3: 8Q验证+连续在榜+跌破0.3退出"] = (sig_wf3, corr_wf3)

    # WF4: Walk-forward 6Q shorter window + Score>=0.3 + 跌破0.3 exit
    sig_wf4, corr_wf4 = walkforward_signals(stock_ret, corr_window=6, min_corr_data=3,
                                              entry_threshold=0.3, exit_floor=0.3)
    strategies["WF4: 6Q滚动验证+跌破0.3退出"] = (sig_wf4, corr_wf4)

    # WF5: Walk-forward 8Q + no new entrants without data
    sig_wf5, corr_wf5 = walkforward_signals(stock_ret, corr_window=8, min_corr_data=4,
                                              entry_threshold=0.3, exit_floor=0.3,
                                              new_entrant_allowed=False)
    strategies["WF5: 8Q验证(无数据不入)+跌破0.3退出"] = (sig_wf5, corr_wf5)

    # Reference: 6家无筛选 + 跌破0.3 exit (best from grid search)
    sig_ref_a = simple_signals(ALL6, 0.3, 99, 0.3)

    # Reference: 3家筛选后 + 3Q decline exit (original best)
    orig3 = ["Prada Group", "Tapestry", "Ralph Lauren"]
    sig_ref_b = simple_signals(orig3, 0.3, 3, None)

    # Run backtests
    results = {}
    for name, (sig, _) in strategies.items():
        p, g, d = run_backtest(sig, stock_ret, glux_ret)
        results[name] = (p, g, d)

    pa_ref, ga_ref, da_ref = run_backtest(sig_ref_a, stock_ret, glux_ret)
    pb_ref, gb_ref, db_ref = run_backtest(sig_ref_b, stock_ret, glux_ret)

    # ═══════════════════════════════════
    # Print trailing correlation log for WF1
    # ═══════════════════════════════════
    print()
    print("=" * 130)
    print("TRAILING CORRELATION LOG (WF1: 8Q window)")
    print("At each quarter, shows the trailing correlation of score vs return for each company.")
    print("Positive = signal works for this company. 'n/a' = insufficient data.")
    print("=" * 130)

    _, corr_main = strategies["WF1: 8Q滚动验证+跌破0.3退出"]
    print(f"\n{'Quarter':<10}", end="")
    for co in ALL6:
        print(f" | {TICKER_MAP[co]:>10}", end="")
    print(" | Decision")
    print("-" * 130)

    for q in QUARTERS:
        print(f"{q:<10}", end="")
        eligible = []
        for co in ALL6:
            c = corr_main[q][co]
            if c is None:
                print(f" | {'n/a':>10}", end="")
            else:
                marker = "✓" if c > 0 else "✗"
                print(f" | {c:>+8.3f}{marker}", end="")
                if c > 0:
                    eligible.append(TICKER_MAP[co])
        elig_str = ", ".join(eligible) if eligible else "(none pass)"
        new_entrants = [TICKER_MAP[co] for co in ALL6 if corr_main[q][co] is None and SCORES[co][QUARTERS.index(q)][1] > 0]
        if new_entrants:
            elig_str += f" + new: {', '.join(new_entrants)}"
        print(f" | {elig_str}")

    # ═══════════════════════════════════
    # Comparison table
    # ═══════════════════════════════════
    print()
    print("=" * 140)
    print("STRATEGY COMPARISON")
    print("=" * 140)

    all_strats = []
    for name, (p, g, d) in results.items():
        n = len(p)
        exc = [a-b for a,b in zip(p, g)]
        t, pval = t_test(exc)
        cum = cumulative(p)
        ann = (1+cum)**(1/(n/4))-1 if n > 0 else 0
        vol = statistics.stdev(p)*2 if n > 1 else 0
        sh = ann/vol if vol > 0 else 0
        mdd = max_drawdown(p)
        all_strats.append((name, cum, ann, sh, mdd, statistics.mean(exc), t, pval, n, d))

    # Add references
    for rname, rp, rg in [("REF-A: 6家无筛选+跌破0.3", pa_ref, ga_ref), ("REF-B: 3家筛选后+3Q下滑", pb_ref, gb_ref)]:
        n = len(rp); exc = [a-b for a,b in zip(rp, rg)]
        t, pval = t_test(exc)
        cum = cumulative(rp); ann = (1+cum)**(1/(n/4))-1
        vol = statistics.stdev(rp)*2; sh = ann/vol if vol > 0 else 0
        mdd = max_drawdown(rp)
        all_strats.append((rname, cum, ann, sh, mdd, statistics.mean(exc), t, pval, n, None))

    # Add GLUX
    gc = cumulative(ga_ref)

    all_strats.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'#':>2} | {'Strategy':<38} | {'Cum':>9} | {'Ann':>8} | {'Sharpe':>7} | {'MaxDD':>7} | {'AvgExc':>8} | {'t':>7} | {'p':>7} | {'Sig':>5}")
    print("-" * 140)
    print(f"{'--':>2} | {'GLUX基准':<38} | {gc:>+8.1%} | {'':>8} | {'':>7} | {'':>7} | {'':>8} | {'':>7} | {'':>7} | {'':>5}")
    print("-" * 140)

    for i, (name, cum, ann, sh, mdd, avg_exc, t, pval, n, _) in enumerate(all_strats, 1):
        sig = "***" if pval < 0.01 else "**" if pval < 0.05 else "*" if pval < 0.10 else "ns"
        beat = ">" if cum > gc else "<"
        print(f"{i:>2} | {name:<38} | {cum:>+8.1%} | {ann:>+7.1%} | {sh:>7.2f} | {mdd:>6.1%} | {avg_exc:>+7.2%} | {t:>7.3f} | {pval:>7.4f} | {sig:>5}")

    # ═══════════════════════════════════
    # Best walk-forward: quarterly details
    # ═══════════════════════════════════
    best_wf = max([(n, c, d) for n, c, _, _, _, _, _, _, _, d in all_strats if d is not None and n.startswith("WF")], key=lambda x: x[1])
    best_name, best_cum, best_details = best_wf

    # Also get ref B details for comparison
    print()
    print("=" * 150)
    print(f"BEST WALK-FORWARD: {best_name}")
    print("vs REF-B (3家筛选后)")
    print("=" * 150)
    print(f"{'Quarter':<10} | {'WF Holdings':<40} | {'WF Ret':>8} | {'RefB Holdings':<20} | {'RefB Ret':>8} | {'GLUX':>8}")
    print("-" * 150)

    db_dict = {q: (pr, gr, longs) for q, pr, gr, longs in db_ref}
    for q, pr, gr, longs in best_details:
        hold_wf = ", ".join(longs) if longs else "CASH"
        pr_b, _, longs_b = db_dict.get(q, (0, gr, []))
        hold_b = ", ".join(longs_b) if longs_b else "CASH"
        marker = " ***" if hold_wf != hold_b else ""
        print(f"{q:<10} | {hold_wf:<40} | {pr:>+7.2%} | {hold_b:<20} | {pr_b:>+7.2%} | {gr:>+7.2%}{marker}")


if __name__ == "__main__":
    main()

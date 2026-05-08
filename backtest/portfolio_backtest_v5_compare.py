#!/usr/bin/env python3
"""
Side-by-side comparison:
  Strategy A: 6 companies, Score>=0.3 entry, 跌破0.3 exit (best unfiltered)
  Strategy B: 3 companies filtered, Score>=0.3 entry, 3Q decline exit (original)

With t-tests and p-values for statistical significance.
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
QUARTERS = [q for q, _ in SCORES["Prada Group"]]


def generate_signals(companies, entry_threshold, require_momentum, exit_decline_q, exit_floor):
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
                    if s["consecutive_rise"] >= exit_decline_q and score >= entry_threshold:
                        if require_momentum:
                            if prev is not None and score > prev:
                                s["position"] = "LONG"
                                s["exited"] = False
                        else:
                            s["position"] = "LONG"
                            s["exited"] = False
                else:
                    if score >= entry_threshold:
                        if require_momentum:
                            if prev is not None and score > prev:
                                s["position"] = "LONG"
                        else:
                            s["position"] = "LONG"

            signals[quarter][co] = s["position"]
            s["prev_score"] = score
    return signals


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
    all_tickers = list(set(list(TICKER_MAP.values()) + list(FX_MAP.values()) + ["GLUX.PA", "EURUSD=X"]))
    price_data = {}
    print("Fetching price data...")
    for t in all_tickers:
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

def quarterly_returns(price_data, companies):
    stock_ret, glux_ret = {}, {}
    for q in QUARTERS:
        y, qn = parse_q(q)
        pub = publish_date(y, qn)
        ny, nq = next_q(y, qn)
        npub = publish_date(ny, nq)

        gp = price_data.get("GLUX.PA", {})
        ep = price_data.get("EURUSD=X", {})
        g0, g1 = get_price(gp, pub), get_price(gp, npub)
        e0, e1 = get_price(ep, pub), get_price(ep, npub)
        glux_ret[q] = (g1 * e1) / (g0 * e0) - 1 if g0 and g1 and e0 and e1 and g0 > 0 and e0 > 0 else None

        stock_ret[q] = {}
        for co in companies:
            ticker = TICKER_MAP[co]
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

def run_backtest(signals, stock_ret, glux_ret, companies):
    port_rets, glux_rets, details = [], [], []
    for q in QUARTERS:
        gr = glux_ret.get(q)
        if gr is None: continue
        sig = signals.get(q, {})
        sret = stock_ret.get(q, {})
        longs = [co for co in companies if sig.get(co) == "LONG"]
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
    for r in rets: c *= (1 + r)
    return c - 1

def max_drawdown(rets):
    c, peak, mdd = 1.0, 1.0, 0
    for r in rets:
        c *= (1 + r)
        peak = max(peak, c)
        mdd = max(mdd, (peak - c) / peak)
    return mdd

def t_test_one_sample(data):
    """One-sample t-test: H0: mean = 0"""
    n = len(data)
    if n < 2: return 0, 1.0
    mean = statistics.mean(data)
    se = statistics.stdev(data) / math.sqrt(n)
    if se == 0: return float('inf'), 0.0
    t = mean / se
    # Two-tailed p-value approximation using normal (good enough for n>=20)
    p = 2 * (1 - normal_cdf(abs(t)))
    return t, p

def t_test_paired(data1, data2):
    """Paired t-test: H0: mean(data1 - data2) = 0"""
    diffs = [a - b for a, b in zip(data1, data2)]
    return t_test_one_sample(diffs)

def normal_cdf(x):
    """Approximation of standard normal CDF"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def main():
    all6 = ["Prada Group", "Tapestry", "Ralph Lauren", "Burberry", "Kering", "Moncler"]
    orig3 = ["Prada Group", "Tapestry", "Ralph Lauren"]

    price_data = fetch_prices()
    stock_ret, glux_ret = quarterly_returns(price_data, all6)

    # Strategy A: 6 companies, Score>=0.3 entry, 跌破0.3 exit
    sig_a = generate_signals(all6, 0.3, False, 99, 0.3)
    pa, ga, da = run_backtest(sig_a, stock_ret, glux_ret, all6)

    # Strategy B: 3 companies filtered, Score>=0.3 entry, 3Q decline exit
    sig_b = generate_signals(orig3, 0.3, False, 3, None)
    pb, gb, db = run_backtest(sig_b, stock_ret, glux_ret, orig3)

    # ═══════════════════════════════════
    # Side-by-side holdings table
    # ═══════════════════════════════════
    print()
    print("=" * 160)
    print("SIDE-BY-SIDE COMPARISON")
    print("Strategy A: 6家无筛选 (Score>=0.3进场, 跌破0.3退出)")
    print("Strategy B: 3家筛选后 (Score>=0.3进场, 3Q连续下滑退出)")
    print("=" * 160)
    print(f"{'Quarter':<10} | {'A: Holdings':<40} | {'A Return':>9} | {'B: Holdings':<20} | {'B Return':>9} | {'GLUX':>9} | {'A Excess':>9} | {'B Excess':>9}")
    print("-" * 160)

    da_dict = {q: (pr, gr, longs) for q, pr, gr, longs in da}
    db_dict = {q: (pr, gr, longs) for q, pr, gr, longs in db}

    for q in QUARTERS:
        if q not in da_dict:
            continue
        pr_a, gr_a, longs_a = da_dict[q]
        pr_b, gr_b, longs_b = db_dict.get(q, (0, gr_a, []))
        hold_a = ", ".join(longs_a) if longs_a else "CASH"
        hold_b = ", ".join(longs_b) if longs_b else "CASH"
        ex_a = pr_a - gr_a
        ex_b = pr_b - gr_b
        # Highlight divergence
        marker = " ***" if hold_a != hold_b else ""
        print(f"{q:<10} | {hold_a:<40} | {pr_a:>+8.2%} | {hold_b:<20} | {pr_b:>+8.2%} | {gr_a:>+8.2%} | {ex_a:>+8.2%} | {ex_b:>+8.2%}{marker}")

    # ═══════════════════════════════════
    # Summary metrics
    # ═══════════════════════════════════
    n = len(pa)
    years = n / 4
    exc_a = [a - g for a, g in zip(pa, ga)]
    exc_b = [b - g for b, g in zip(pb, gb)]

    cum_a, cum_b, cum_g = cumulative(pa), cumulative(pb), cumulative(ga)
    ann_a = (1 + cum_a) ** (1/years) - 1
    ann_b = (1 + cum_b) ** (1/years) - 1
    ann_g = (1 + cum_g) ** (1/years) - 1
    vol_a = statistics.stdev(pa) * 2
    vol_b = statistics.stdev(pb) * 2
    vol_g = statistics.stdev(ga) * 2

    print()
    print("=" * 90)
    print("PERFORMANCE SUMMARY")
    print("=" * 90)
    print(f"{'Metric':<30} | {'A: 6家无筛选':>18} | {'B: 3家筛选后':>18} | {'GLUX':>14}")
    print("-" * 90)
    print(f"{'Cumulative Return':<30} | {cum_a:>+17.1%} | {cum_b:>+17.1%} | {cum_g:>+13.1%}")
    print(f"{'Annualized Return':<30} | {ann_a:>+17.1%} | {ann_b:>+17.1%} | {ann_g:>+13.1%}")
    print(f"{'Annualized Volatility':<30} | {vol_a:>17.1%} | {vol_b:>17.1%} | {vol_g:>13.1%}")
    print(f"{'Sharpe (no Rf)':<30} | {ann_a/vol_a if vol_a>0 else 0:>17.2f} | {ann_b/vol_b if vol_b>0 else 0:>17.2f} | {ann_g/vol_g if vol_g>0 else 0:>13.2f}")
    print(f"{'Max Drawdown':<30} | {max_drawdown(pa):>17.1%} | {max_drawdown(pb):>17.1%} | {max_drawdown(ga):>13.1%}")
    print(f"{'Win Rate (Q>0)':<30} | {sum(1 for r in pa if r>0)/n:>17.1%} | {sum(1 for r in pb if r>0)/n:>17.1%} | {sum(1 for r in ga if r>0)/n:>13.1%}")
    print(f"{'Avg Quarterly Return':<30} | {statistics.mean(pa):>+17.2%} | {statistics.mean(pb):>+17.2%} | {statistics.mean(ga):>+13.2%}")
    print(f"{'Avg Quarterly Excess vs GLUX':<30} | {statistics.mean(exc_a):>+17.2%} | {statistics.mean(exc_b):>+17.2%} |")
    print(f"{'Excess Win Rate':<30} | {sum(1 for e in exc_a if e>0)/n:>17.1%} | {sum(1 for e in exc_b if e>0)/n:>17.1%} |")

    # ═══════════════════════════════════
    # STATISTICAL SIGNIFICANCE TESTS
    # ═══════════════════════════════════
    print()
    print("=" * 90)
    print("STATISTICAL SIGNIFICANCE TESTS")
    print("=" * 90)

    # Test 1: Strategy A excess vs 0
    t_a, p_a = t_test_one_sample(exc_a)
    print(f"\n--- Test 1: Strategy A 季度超额收益是否显著 ≠ 0 ---")
    print(f"  H0: 策略A平均季度超额 = 0 (即策略A不优于GLUX)")
    print(f"  Mean quarterly excess:  {statistics.mean(exc_a):+.2%}")
    print(f"  Std of quarterly excess: {statistics.stdev(exc_a):.2%}")
    print(f"  n = {n} quarters")
    print(f"  t-statistic: {t_a:.3f}")
    print(f"  p-value (two-tailed): {p_a:.4f}")
    print(f"  结论: {'显著 (p < 0.05)' if p_a < 0.05 else '不显著 (p >= 0.05)' if p_a < 0.10 else '不显著'}")

    # Test 2: Strategy B excess vs 0
    t_b, p_b = t_test_one_sample(exc_b)
    print(f"\n--- Test 2: Strategy B 季度超额收益是否显著 ≠ 0 ---")
    print(f"  H0: 策略B平均季度超额 = 0 (即策略B不优于GLUX)")
    print(f"  Mean quarterly excess:  {statistics.mean(exc_b):+.2%}")
    print(f"  Std of quarterly excess: {statistics.stdev(exc_b):.2%}")
    print(f"  n = {n} quarters")
    print(f"  t-statistic: {t_b:.3f}")
    print(f"  p-value (two-tailed): {p_b:.4f}")
    print(f"  结论: {'显著 (p < 0.05)' if p_b < 0.05 else '边际显著 (p < 0.10)' if p_b < 0.10 else '不显著'}")

    # Test 3: Strategy A vs Strategy B (paired)
    t_ab, p_ab = t_test_paired(pa, pb)
    print(f"\n--- Test 3: Strategy A vs Strategy B 是否有显著差异 ---")
    print(f"  H0: 策略A和策略B的平均季度收益无差异")
    print(f"  Mean quarterly diff (A-B): {statistics.mean([a-b for a,b in zip(pa,pb)]):+.2%}")
    print(f"  t-statistic: {t_ab:.3f}")
    print(f"  p-value (two-tailed): {p_ab:.4f}")
    print(f"  结论: {'显著 (p < 0.05)' if p_ab < 0.05 else '边际显著 (p < 0.10)' if p_ab < 0.10 else '不显著'}")

    # Test 4: Strategy A quarterly returns vs 0 (absolute)
    t_a0, p_a0 = t_test_one_sample(pa)
    print(f"\n--- Test 4: Strategy A 季度绝对收益是否显著 > 0 ---")
    print(f"  Mean quarterly return: {statistics.mean(pa):+.2%}")
    print(f"  t-statistic: {t_a0:.3f}")
    print(f"  p-value (two-tailed): {p_a0:.4f}")

    # Test 5: Strategy B quarterly returns vs 0 (absolute)
    t_b0, p_b0 = t_test_one_sample(pb)
    print(f"\n--- Test 5: Strategy B 季度绝对收益是否显著 > 0 ---")
    print(f"  Mean quarterly return: {statistics.mean(pb):+.2%}")
    print(f"  t-statistic: {t_b0:.3f}")
    print(f"  p-value (two-tailed): {p_b0:.4f}")

    # Test 6: Excess returns during LONG vs CASH periods (Strategy A)
    print(f"\n--- Test 6: Strategy A 持仓期 vs 空仓期 超额收益差异 ---")
    long_exc = [pr - gr for q, pr, gr, longs in da if longs]
    cash_exc = [pr - gr for q, pr, gr, longs in da if not longs]
    if long_exc and cash_exc:
        mean_long = statistics.mean(long_exc)
        mean_cash = statistics.mean(cash_exc)
        print(f"  持仓期平均超额: {mean_long:+.2%} (n={len(long_exc)})")
        print(f"  空仓期平均超额: {mean_cash:+.2%} (n={len(cash_exc)})")
        print(f"  Spread: {mean_long - mean_cash:+.2%}")
        # Welch's t-test approximation
        if len(long_exc) > 1 and len(cash_exc) > 1:
            s1 = statistics.stdev(long_exc)
            s2 = statistics.stdev(cash_exc)
            n1, n2 = len(long_exc), len(cash_exc)
            se = math.sqrt(s1**2/n1 + s2**2/n2)
            if se > 0:
                t_lc = (mean_long - mean_cash) / se
                p_lc = 2 * (1 - normal_cdf(abs(t_lc)))
                print(f"  t-statistic: {t_lc:.3f}")
                print(f"  p-value: {p_lc:.4f}")
                print(f"  结论: {'显著' if p_lc < 0.05 else '边际显著' if p_lc < 0.10 else '不显著'}")
    elif not cash_exc:
        print(f"  策略A几乎没有空仓期，无法比较")
        t_long, p_long = t_test_one_sample(long_exc)
        print(f"  持仓期超额收益 t={t_long:.3f}, p={p_long:.4f}")

    # Test 7: Same for Strategy B
    print(f"\n--- Test 7: Strategy B 持仓期 vs 空仓期 超额收益差异 ---")
    long_exc_b = [pr - gr for q, pr, gr, longs in db if longs]
    cash_exc_b = [pr - gr for q, pr, gr, longs in db if not longs]
    if long_exc_b and cash_exc_b:
        mean_long_b = statistics.mean(long_exc_b)
        mean_cash_b = statistics.mean(cash_exc_b)
        print(f"  持仓期平均超额: {mean_long_b:+.2%} (n={len(long_exc_b)})")
        print(f"  空仓期平均超额: {mean_cash_b:+.2%} (n={len(cash_exc_b)})")
        print(f"  Spread: {mean_long_b - mean_cash_b:+.2%}")
        if len(long_exc_b) > 1 and len(cash_exc_b) > 1:
            s1 = statistics.stdev(long_exc_b)
            s2 = statistics.stdev(cash_exc_b)
            n1, n2 = len(long_exc_b), len(cash_exc_b)
            se = math.sqrt(s1**2/n1 + s2**2/n2)
            if se > 0:
                t_lc = (mean_long_b - mean_cash_b) / se
                p_lc = 2 * (1 - normal_cdf(abs(t_lc)))
                print(f"  t-statistic: {t_lc:.3f}")
                print(f"  p-value: {p_lc:.4f}")
                print(f"  结论: {'显著' if p_lc < 0.05 else '边际显著' if p_lc < 0.10 else '不显著'}")

    # Summary of all tests
    print()
    print("=" * 90)
    print("SIGNIFICANCE SUMMARY")
    print("=" * 90)
    print(f"{'Test':<50} | {'t':>8} | {'p':>8} | {'Sig?':>10}")
    print("-" * 85)
    tests = [
        ("A: 6家无筛选 超额 vs 0", t_a, p_a),
        ("B: 3家筛选后 超额 vs 0", t_b, p_b),
        ("A vs B 配对差异", t_ab, p_ab),
        ("A: 绝对收益 vs 0", t_a0, p_a0),
        ("B: 绝对收益 vs 0", t_b0, p_b0),
    ]
    for name, t, p in tests:
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "ns"
        print(f"{name:<50} | {t:>8.3f} | {p:>8.4f} | {sig:>10}")

    print()
    print("Significance levels: *** p<0.01, ** p<0.05, * p<0.10, ns = not significant")


if __name__ == "__main__":
    main()

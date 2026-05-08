#!/usr/bin/env python3
"""
Test different exit strategies against actual stock returns.
Compare: always-hold vs score-decline exit vs score-threshold exit.
"""

import csv, statistics, math
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta, date

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance")
    exit(1)

REPO_ROOT = Path(__file__).resolve().parent
TRACKER_CSV = str(REPO_ROOT / "data" / "lyst-index-tracker.csv")
HISTORICAL_CSV = str(REPO_ROOT / "data" / "lyst-historical-2018.csv")
UNRANKED = 21

KERING_RAW = {
    2017: (72.1, 12.8, 10.0), 2018: (83.0, 11.6, 6.1),
    2019: (82.6, 11.8, 4.5), 2020: (83.4, 12.8, 5.5),
    2021: (74.0, 14.2, 5.7), 2022: (66.8, 18.2, 6.6),
    2023: (68.7, 20.4, 6.6), 2024: (62.8, 23.2, 10.0),
    2025: (59.2, 32.4, 16.4),
}
PRADA_RAW = {
    2017: (0.82, 0.18), 2018: (0.82, 0.18), 2019: (0.81, 0.19),
    2020: (0.80, 0.20), 2021: (0.78, 0.22), 2022: (0.74, 0.26),
    2023: (0.70, 0.30), 2024: (0.62, 0.38), 2025: (0.55, 0.45),
}

COMPANIES = {
    "Prada Group": {"ticker": "1913.HK", "currency": "HKD", "brands": ["Prada", "Miu Miu"]},
    "Tapestry": {"ticker": "TPR", "currency": "USD", "brands": ["Coach"]},
    "Ralph Lauren": {"ticker": "RL", "currency": "USD", "brands": ["Ralph Lauren"]},
}
FX_TICKERS = {"HKD": "HKDUSD=X"}


def parse_q(q_str):
    parts = q_str.strip().split()
    return int(parts[1]), int(parts[0][1:])

def q_str(year, qtr):
    return f"Q{qtr} {year}"

def publish_date(year, qtr):
    if qtr == 4:
        return f"{year + 1}-01-25"
    return f"{year}-{['04','07','10'][qtr - 1]}-25"

def build_quarters():
    quarters = []
    y, q = 2018, 1
    end_y, end_q = 2026, 1
    while (y, q) <= (end_y, end_q):
        quarters.append(q_str(y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return quarters

def get_weights(company, year):
    if company == "Prada Group":
        fy = max(min(year - 1, max(PRADA_RAW.keys())), min(PRADA_RAW.keys()))
        p, m = PRADA_RAW[fy]
        return {"Prada": p, "Miu Miu": m}
    elif company == "Tapestry":
        return {"Coach": 1.0}
    elif company == "Ralph Lauren":
        return {"Ralph Lauren": 1.0}

def normalize_quarter(q_str_raw):
    q_str_raw = q_str_raw.strip()
    if q_str_raw.startswith("Q"):
        return q_str_raw
    if "Q" in q_str_raw:
        parts = q_str_raw.split("Q")
        if len(parts) == 2:
            return f"Q{parts[1].strip()} {parts[0].strip()}"
    return q_str_raw

def load_all_brands(quarters_set):
    data = defaultdict(dict)
    aliases = {"Alaïa": "Alaia", "Chloé": "Chloe", "Totême": "Toteme"}
    with open(HISTORICAL_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            brand = row["brand"].strip().rstrip("?")
            brand = aliases.get(brand, brand)
            q = normalize_quarter(row["quarter"])
            if q not in quarters_set or "2018" not in q:
                continue
            try:
                data[brand][q] = int(row["rank"].strip())
            except (ValueError, KeyError):
                continue
    with open(TRACKER_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            q = row["Quarter"].strip()
            if q not in quarters_set:
                continue
            brand = row["Brand"].strip()
            brand = aliases.get(brand, brand)
            try:
                data[brand][q] = int(row["Rank"].strip())
            except (ValueError, KeyError):
                continue
    return data

def compute_composite_scores(brand_data, quarters):
    results = {}
    for brand, q_ranks in brand_data.items():
        results[brand] = {}
        for i, q in enumerate(quarters):
            rank = q_ranks.get(q, UNRANKED)
            level = max(0, (21 - rank)) / 20
            streak = 0
            for j in range(i, -1, -1):
                if q_ranks.get(quarters[j], UNRANKED) < UNRANKED:
                    streak += 1
                else:
                    break
            trend = 0
            if i >= 3:
                rank_3back = q_ranks.get(quarters[i - 3], UNRANKED)
                trend = rank_3back - rank
            trend_sc = max(-1, min(1, trend / 10))
            pres = min(1, streak / 8)
            score = 0.5 * level + 0.3 * trend_sc + 0.2 * pres
            results[brand][q] = round(score, 3)
    return results

def compute_company_scores(brand_scores, quarters):
    co_scores = {}
    for company in COMPANIES:
        co_scores[company] = {}
        for q in quarters:
            year, _ = parse_q(q)
            weights = get_weights(company, year)
            total = 0
            for brand, w in weights.items():
                bs = brand_scores.get(brand, {}).get(q, 0)
                total += w * bs
            co_scores[company][q] = round(total, 3)
    return co_scores

def get_price(hist, date_str, max_days=5):
    target = datetime.strptime(date_str, "%Y-%m-%d")
    for d in range(max_days + 1):
        check = (target + timedelta(days=d)).strftime("%Y-%m-%d")
        matches = hist.loc[hist.index.strftime("%Y-%m-%d") == check]
        if not matches.empty:
            return float(matches["Close"].iloc[-1])
    return None

def fetch_and_compute_returns(quarters):
    tickers = ["1913.HK", "TPR", "RL", "GLUX.PA"]
    fx_tickers = {"HKD": "HKDUSD=X"}
    stock_data, fx_data = {}, {}

    print("Fetching prices...")
    for t in tickers:
        try:
            h = yf.Ticker(t).history(start="2018-01-01", end=date.today().strftime("%Y-%m-%d"), auto_adjust=True)
            if not h.empty:
                stock_data[t] = h
                print(f"  {t}: {len(h)} days")
        except Exception as e:
            print(f"  {t}: ERROR {e}")

    for ccy, ft in fx_tickers.items():
        try:
            h = yf.Ticker(ft).history(start="2018-01-01", end=date.today().strftime("%Y-%m-%d"), auto_adjust=True)
            if not h.empty:
                fx_data[ccy] = h
        except:
            pass

    pairs = list(zip(quarters[:-1], quarters[1:]))
    glux_hist = stock_data.get("GLUX.PA")
    glux_ret = {}
    if glux_hist is not None:
        for q1, q2 in pairs:
            pub1, pub2 = publish_date(*parse_q(q1)), publish_date(*parse_q(q2))
            p0 = get_price(glux_hist, pub1)
            p1 = get_price(glux_hist, pub2)
            if p0 and p1:
                fx0 = get_price(fx_data.get("EUR", fx_data.get("HKD")), pub1) if "EUR" in fx_data else None
                glux_ret[q1] = round((p1 / p0 - 1) * 100, 2)

    excess_ret = {}
    for company, cfg in COMPANIES.items():
        hist = stock_data.get(cfg["ticker"])
        if hist is None:
            continue
        excess_ret[company] = {}
        for q1, q2 in pairs:
            pub1, pub2 = publish_date(*parse_q(q1)), publish_date(*parse_q(q2))
            p0 = get_price(hist, pub1)
            p1 = get_price(hist, pub2)
            if p0 is None or p1 is None:
                continue
            ccy = cfg["currency"]
            if ccy != "USD" and ccy in fx_data:
                fx0 = get_price(fx_data[ccy], pub1)
                fx1 = get_price(fx_data[ccy], pub2)
                if fx0 and fx1:
                    p0, p1 = p0 * fx0, p1 * fx1
            r = round((p1 / p0 - 1) * 100, 2)
            if q1 in glux_ret:
                excess_ret[company][q1] = round(r - glux_ret[q1], 2)

    return excess_ret


def t_test_mean(values):
    n = len(values)
    if n < 2:
        return None, None, None, n
    mean = statistics.mean(values)
    se = statistics.stdev(values) / math.sqrt(n)
    t = mean / se if se > 0 else 0
    from math import exp, pi
    df = n - 1
    x = df / (df + t * t)
    p = 1.0
    if abs(t) > 0:
        p = 0.5
        if abs(t) > 0.5:
            p = max(0.001, min(0.999, 0.5 * (1 + math.erf(-abs(t) / math.sqrt(2)))) * 2)
    return round(mean, 3), round(t, 3), round(p, 3), n


def main():
    quarters = build_quarters()
    quarters_set = set(quarters)
    brand_data = load_all_brands(quarters_set)
    brand_scores = compute_composite_scores(brand_data, quarters)
    co_scores = compute_company_scores(brand_scores, quarters)
    excess_ret = fetch_and_compute_returns(quarters)

    show_qs = [q for i, q in enumerate(quarters) if i >= 3]

    print("\n" + "=" * 80)
    print("EXIT STRATEGY COMPARISON: Hold-Through vs Score-Based Exit")
    print("=" * 80)

    for company in COMPANIES:
        if company not in excess_ret:
            continue

        scores = co_scores[company]
        rets = excess_ret[company]

        print(f"\n{'─' * 60}")
        print(f"  {company} ({COMPANIES[company]['ticker']})")
        print(f"{'─' * 60}")

        # Find confirmed entry point (2Q on chart + rank improving)
        entry_q = None
        for i, q in enumerate(show_qs):
            if i < 2:
                continue
            s = scores.get(q, 0)
            s_prev = scores.get(show_qs[i-1], 0)
            s_prev2 = scores.get(show_qs[i-2], 0)
            if s > 0 and s_prev > 0 and s >= s_prev:
                entry_q = q
                break

        if not entry_q:
            print("  No confirmed entry found")
            continue

        entry_idx = show_qs.index(entry_q)
        print(f"  Confirmed entry: {entry_q} (score={scores[entry_q]:.3f})")

        # Strategy A: Always hold (from entry to end)
        hold_rets_a = []
        # Strategy B: Exit when score declines 2 consecutive quarters
        hold_rets_b = []
        # Strategy C: Exit when score declines 3 consecutive quarters
        hold_rets_c = []
        # Strategy D: Exit when score drops below own median
        all_scores_post_entry = [scores[q] for q in show_qs[entry_idx:] if scores.get(q, 0) > 0]
        median_score = statistics.median(all_scores_post_entry) if all_scores_post_entry else 0
        hold_rets_d = []
        # Strategy E: Exit when score drops below 0.3
        hold_rets_e = []

        # Track each strategy's state
        in_a = True
        in_b, b_decline_count = True, 0
        in_c, c_decline_count = True, 0
        in_d = True
        in_e = True
        prev_score = scores.get(entry_q, 0)

        detail_rows = []

        for i in range(entry_idx, len(show_qs) - 1):
            q = show_qs[i]
            s = scores.get(q, 0)
            ret = rets.get(q)
            if ret is None:
                continue

            # Score direction
            declining = s < prev_score

            # Strategy B: 2Q consecutive decline
            if in_b:
                if declining:
                    b_decline_count += 1
                else:
                    b_decline_count = 0
                if b_decline_count >= 2:
                    in_b = False

            # Strategy C: 3Q consecutive decline
            if in_c:
                if declining:
                    c_decline_count += 1
                else:
                    c_decline_count = 0
                if c_decline_count >= 3:
                    in_c = False

            # Strategy D: below median
            if in_d and s < median_score:
                in_d = False
            elif not in_d and s >= median_score:
                in_d = True

            # Strategy E: below 0.3
            if in_e and s < 0.3:
                in_e = False
            elif not in_e and s >= 0.3:
                in_e = True

            hold_rets_a.append(ret)
            if in_b:
                hold_rets_b.append(ret)
            if in_c:
                hold_rets_c.append(ret)
            if in_d:
                hold_rets_d.append(ret)
            if in_e:
                hold_rets_e.append(ret)

            detail_rows.append({
                "q": q, "score": s, "ret": ret,
                "a": True, "b": in_b, "c": in_c, "d": in_d, "e": in_e,
                "direction": "↓" if declining else "↑",
            })

            prev_score = s

        # Print detail table
        print(f"\n  {'Quarter':<10} {'Score':>6} {'Trend':>5} {'Excess':>7}  {'A:Hold':>6} {'B:2Qdec':>7} {'C:3Qdec':>7} {'D:>Med':>6} {'E:>0.3':>6}")
        print(f"  {'─'*10} {'─'*6} {'─'*5} {'─'*7}  {'─'*6} {'─'*7} {'─'*7} {'─'*6} {'─'*6}")
        for r in detail_rows:
            print(f"  {r['q']:<10} {r['score']:>6.3f} {r['direction']:>5} {r['ret']:>+7.2f}  "
                  f"{'HOLD':>6} {'HOLD' if r['b'] else 'OUT':>7} {'HOLD' if r['c'] else 'OUT':>7} "
                  f"{'HOLD' if r['d'] else 'OUT':>6} {'HOLD' if r['e'] else 'OUT':>6}")

        # Summary
        print(f"\n  Median score (post-entry): {median_score:.3f}")
        print(f"\n  {'Strategy':<30} {'Quarters':>8} {'Cum Excess':>11} {'Avg/Q':>8} {'Win%':>6}")
        print(f"  {'─'*30} {'─'*8} {'─'*11} {'─'*8} {'─'*6}")

        strategies = [
            ("A: Always hold", hold_rets_a),
            ("B: Exit on 2Q decline", hold_rets_b),
            ("C: Exit on 3Q decline", hold_rets_c),
            ("D: Hold only above median", hold_rets_d),
            ("E: Hold only above 0.3", hold_rets_e),
        ]

        for name, rets_list in strategies:
            if not rets_list:
                print(f"  {name:<30} {'0':>8} {'N/A':>11} {'N/A':>8} {'N/A':>6}")
                continue
            cum = sum(rets_list)
            avg = statistics.mean(rets_list)
            win = sum(1 for r in rets_list if r > 0) / len(rets_list) * 100
            print(f"  {name:<30} {len(rets_list):>8} {cum:>+11.1f}% {avg:>+8.2f}% {win:>5.0f}%")

        # Declined-period returns (quarters when score was declining)
        decline_rets = [r["ret"] for r in detail_rows if r["direction"] == "↓"]
        rise_rets = [r["ret"] for r in detail_rows if r["direction"] == "↑"]
        print(f"\n  Score rising quarters:   avg excess {statistics.mean(rise_rets):+.2f}% (n={len(rise_rets)})" if rise_rets else "")
        print(f"  Score declining quarters: avg excess {statistics.mean(decline_rets):+.2f}% (n={len(decline_rets)})" if decline_rets else "")

    # Aggregate across all 3 companies
    print(f"\n{'=' * 80}")
    print("AGGREGATE: All 3 Companies (Prada + Tapestry + RL)")
    print(f"{'=' * 80}")

    agg = defaultdict(list)
    agg_rise, agg_decline = [], []

    for company in COMPANIES:
        if company not in excess_ret:
            continue
        scores = co_scores[company]
        rets = excess_ret[company]

        entry_q = None
        for i, q in enumerate(show_qs):
            if i < 2:
                continue
            s = scores.get(q, 0)
            s_prev = scores.get(show_qs[i-1], 0)
            if s > 0 and s_prev > 0 and s >= s_prev:
                entry_q = q
                break
        if not entry_q:
            continue

        entry_idx = show_qs.index(entry_q)
        all_s = [scores[q] for q in show_qs[entry_idx:] if scores.get(q, 0) > 0]
        med = statistics.median(all_s) if all_s else 0
        prev_score = scores.get(entry_q, 0)
        in_b, bc = True, 0
        in_c, cc = True, 0
        in_d, in_e = True, True

        for i in range(entry_idx, len(show_qs) - 1):
            q = show_qs[i]
            s = scores.get(q, 0)
            ret = rets.get(q)
            if ret is None:
                continue
            declining = s < prev_score
            if in_b:
                bc = bc + 1 if declining else 0
                if bc >= 2: in_b = False
            if in_c:
                cc = cc + 1 if declining else 0
                if cc >= 3: in_c = False
            if s < med: in_d = False
            elif s >= med: in_d = True
            if s < 0.3: in_e = False
            elif s >= 0.3: in_e = True

            agg["A"].append(ret)
            if in_b: agg["B"].append(ret)
            if in_c: agg["C"].append(ret)
            if in_d: agg["D"].append(ret)
            if in_e: agg["E"].append(ret)

            if declining:
                agg_decline.append(ret)
            else:
                agg_rise.append(ret)

            prev_score = s

    print(f"\n  {'Strategy':<30} {'Quarters':>8} {'Cum Excess':>11} {'Avg/Q':>8} {'Win%':>6}")
    print(f"  {'─'*30} {'─'*8} {'─'*11} {'─'*8} {'─'*6}")
    labels = {
        "A": "A: Always hold",
        "B": "B: Exit on 2Q decline",
        "C": "C: Exit on 3Q decline",
        "D": "D: Hold only above median",
        "E": "E: Hold only above 0.3",
    }
    for k in ["A", "B", "C", "D", "E"]:
        rl = agg[k]
        if not rl:
            continue
        cum = sum(rl)
        avg = statistics.mean(rl)
        win = sum(1 for r in rl if r > 0) / len(rl) * 100
        print(f"  {labels[k]:<30} {len(rl):>8} {cum:>+11.1f}% {avg:>+8.2f}% {win:>5.0f}%")

    if agg_rise:
        print(f"\n  Score RISING quarters:    avg excess {statistics.mean(agg_rise):+.2f}%  (n={len(agg_rise)})")
    if agg_decline:
        print(f"  Score DECLINING quarters: avg excess {statistics.mean(agg_decline):+.2f}%  (n={len(agg_decline)})")

    if agg_rise and agg_decline:
        spread = statistics.mean(agg_rise) - statistics.mean(agg_decline)
        _, t, p, _ = t_test_mean([r for r in agg_rise] + [-r for r in agg_decline])
        print(f"  Spread (rise - decline):  {spread:+.2f}%")


if __name__ == "__main__":
    main()

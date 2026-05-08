#!/usr/bin/env python3
"""
Test different ENTRY timing strategies against actual stock returns.
Compare: immediate entry vs N-quarter confirmation vs score threshold vs momentum.
"""

import sys, csv, statistics, math
sys.stdout.reconfigure(encoding='utf-8')
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

PRADA_RAW = {
    2017: (0.82, 0.18), 2018: (0.82, 0.18), 2019: (0.81, 0.19),
    2020: (0.80, 0.20), 2021: (0.78, 0.22), 2022: (0.74, 0.26),
    2023: (0.70, 0.30), 2024: (0.62, 0.38), 2025: (0.55, 0.45),
}

COMPANIES = {
    "Prada Group":  {"ticker": "1913.HK", "currency": "HKD", "brands": ["Prada", "Miu Miu"]},
    "Tapestry":     {"ticker": "TPR",     "currency": "USD", "brands": ["Coach"]},
    "Ralph Lauren": {"ticker": "RL",      "currency": "USD", "brands": ["Ralph Lauren"]},
}
FX_TICKERS = {"HKD": "HKDUSD=X"}


# ── helpers (shared with exit_strategy_test.py) ──

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
            h = yf.Ticker(t).history(start="2018-01-01",
                                     end=date.today().strftime("%Y-%m-%d"),
                                     auto_adjust=True)
            if not h.empty:
                stock_data[t] = h
                print(f"  {t}: {len(h)} days")
        except Exception as e:
            print(f"  {t}: ERROR {e}")

    for ccy, ft in fx_tickers.items():
        try:
            h = yf.Ticker(ft).history(start="2018-01-01",
                                      end=date.today().strftime("%Y-%m-%d"),
                                      auto_adjust=True)
            if not h.empty:
                fx_data[ccy] = h
        except:
            pass

    pairs = list(zip(quarters[:-1], quarters[1:]))
    glux_hist = stock_data.get("GLUX.PA")
    glux_ret = {}
    if glux_hist is not None:
        for q1, q2 in pairs:
            pub1 = publish_date(*parse_q(q1))
            pub2 = publish_date(*parse_q(q2))
            p0 = get_price(glux_hist, pub1)
            p1 = get_price(glux_hist, pub2)
            if p0 and p1:
                glux_ret[q1] = round((p1 / p0 - 1) * 100, 2)

    excess_ret = {}
    for company, cfg in COMPANIES.items():
        hist = stock_data.get(cfg["ticker"])
        if hist is None:
            continue
        excess_ret[company] = {}
        for q1, q2 in pairs:
            pub1 = publish_date(*parse_q(q1))
            pub2 = publish_date(*parse_q(q2))
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


# ── entry detection helpers ──

def find_first_appearance(brands, brand_data, quarters):
    """Quarter when any brand first appears on Lyst Top 20."""
    for q in quarters:
        for brand in brands:
            if brand_data.get(brand, {}).get(q, UNRANKED) < UNRANKED:
                return q
    return None

def find_2q_on_list(brands, brand_data, quarters):
    """Quarter when any brand has been on list 2 consecutive quarters."""
    for i in range(1, len(quarters)):
        q, prev = quarters[i], quarters[i - 1]
        for brand in brands:
            bd = brand_data.get(brand, {})
            if bd.get(q, UNRANKED) < UNRANKED and bd.get(prev, UNRANKED) < UNRANKED:
                return q
    return None

def find_3q_confirmed(brands, brand_data, quarters):
    """3 consecutive quarters on list + rank improved vs first appearance."""
    for i in range(2, len(quarters)):
        q, p1, p2 = quarters[i], quarters[i - 1], quarters[i - 2]
        for brand in brands:
            bd = brand_data.get(brand, {})
            r0 = bd.get(q, UNRANKED)
            r1 = bd.get(p1, UNRANKED)
            r2 = bd.get(p2, UNRANKED)
            if r0 < UNRANKED and r1 < UNRANKED and r2 < UNRANKED:
                first_rank = UNRANKED
                for qq in quarters:
                    rr = bd.get(qq, UNRANKED)
                    if rr < UNRANKED:
                        first_rank = rr
                        break
                if r0 <= first_rank:
                    return q
    return None

def find_score_threshold(scores, show_qs, threshold):
    """First quarter where company score >= threshold."""
    for q in show_qs:
        if scores.get(q, 0) >= threshold:
            return q
    return None

def find_2q_momentum(scores, show_qs):
    """First quarter where company score improved 2 consecutive quarters."""
    for i in range(1, len(show_qs)):
        q, prev = show_qs[i], show_qs[i - 1]
        s, sp = scores.get(q, 0), scores.get(prev, 0)
        if s > sp and sp > 0 and s > 0:
            return q
    return None

def find_top10_entry(brands, brand_data, quarters):
    """First quarter when any brand enters Top 10."""
    for q in quarters:
        for brand in brands:
            rank = brand_data.get(brand, {}).get(q, UNRANKED)
            if rank <= 10:
                return q
    return None


def returns_from(entry_q, show_qs, rets, quarters):
    """Collect quarterly excess returns from entry_q onward."""
    if entry_q in show_qs:
        start_idx = show_qs.index(entry_q)
    else:
        start_idx = 0
        entry_pos = quarters.index(entry_q)
        for i, q in enumerate(show_qs):
            if quarters.index(q) >= entry_pos:
                start_idx = i
                break
    hold = []
    for i in range(start_idx, len(show_qs)):
        r = rets.get(show_qs[i])
        if r is not None:
            hold.append((show_qs[i], r))
    return hold


def main():
    quarters = build_quarters()
    quarters_set = set(quarters)
    brand_data = load_all_brands(quarters_set)
    brand_scores = compute_composite_scores(brand_data, quarters)
    co_scores = compute_company_scores(brand_scores, quarters)
    excess_ret = fetch_and_compute_returns(quarters)

    show_qs = [q for i, q in enumerate(quarters) if i >= 3]

    print("\n" + "=" * 80)
    print("ENTRY STRATEGY COMPARISON: When to Enter the Trade")
    print("=" * 80)

    STRAT_NAMES = [
        "A: First appearance",
        "B: 2Q on list",
        "C: 3Q confirmed+improving",
        "D: Score >= 0.3",
        "E: Score >= 0.5",
        "F: 2Q score momentum",
        "G: Brand enters Top 10",
    ]
    agg = {name: {"fwd1": [], "fwd4": [], "all_rets": [], "cum": []} for name in STRAT_NAMES}

    for company in COMPANIES:
        if company not in excess_ret:
            continue

        scores = co_scores[company]
        rets = excess_ret[company]
        brands = COMPANIES[company]["brands"]

        print(f"\n{'─' * 70}")
        print(f"  {company} ({COMPANIES[company]['ticker']})")
        print(f"{'─' * 70}")

        # ── Detect entry points ──
        entries = {
            "A: First appearance":       find_first_appearance(brands, brand_data, quarters),
            "B: 2Q on list":             find_2q_on_list(brands, brand_data, quarters),
            "C: 3Q confirmed+improving": find_3q_confirmed(brands, brand_data, quarters),
            "D: Score >= 0.3":            find_score_threshold(scores, show_qs, 0.3),
            "E: Score >= 0.5":            find_score_threshold(scores, show_qs, 0.5),
            "F: 2Q score momentum":      find_2q_momentum(scores, show_qs),
            "G: Brand enters Top 10":    find_top10_entry(brands, brand_data, quarters),
        }

        # ── Timeline ──
        entry_qs_set = {eq for eq in entries.values() if eq}
        if not entry_qs_set:
            print("  No entry signals found.")
            continue

        earliest_pos = min(quarters.index(eq) for eq in entry_qs_set)
        tl_start = max(0, earliest_pos - 1)

        entry_markers = defaultdict(list)
        for name, eq in entries.items():
            if eq:
                entry_markers[eq].append(name[0])

        print(f"\n  Timeline (>> = entry point):")
        print(f"  {'Quarter':<10} {'Score':>6} {'Excess':>7}  {'Signals':<12} Brands on list")
        print(f"  {'─' * 10} {'─' * 6} {'─' * 7}  {'─' * 12} {'─' * 30}")

        for i in range(tl_start, len(quarters)):
            q = quarters[i]
            s = scores.get(q, 0)
            r = rets.get(q)
            r_str = f"{r:>+7.2f}" if r is not None else "    N/A"
            markers = entry_markers.get(q, [])
            marker_str = ",".join(markers) if markers else ""

            on_list = []
            for brand in brands:
                rank = brand_data.get(brand, {}).get(q, UNRANKED)
                if rank < UNRANKED:
                    on_list.append(f"{brand} #{rank}")
            brand_str = ", ".join(on_list) if on_list else "—"

            prefix = ">>" if markers else "  "
            print(f"{prefix}{q:<10} {s:>6.3f} {r_str}  {marker_str:<12} {brand_str}")

        # ── Compute returns per strategy ──
        print(f"\n  {'Strategy':<26} {'Entry':>10} {'Score':>6} {'#Qs':>4}"
              f" {'Cum Exc':>8} {'Avg/Q':>7} {'Win%':>5}"
              f" {'Fwd1Q':>7} {'Fwd4Q':>7}")
        print(f"  {'─' * 26} {'─' * 10} {'─' * 6} {'─' * 4}"
              f" {'─' * 8} {'─' * 7} {'─' * 5}"
              f" {'─' * 7} {'─' * 7}")

        strat_results = []
        for name in STRAT_NAMES:
            eq = entries[name]
            if eq is None:
                print(f"  {name:<26} {'N/A':>10}")
                strat_results.append((name, None, 0, []))
                continue

            es = scores.get(eq, 0)
            hold = returns_from(eq, show_qs, rets, quarters)
            hold_rets = [r for _, r in hold]
            n = len(hold_rets)
            cum = sum(hold_rets)
            avg_q = statistics.mean(hold_rets) if n else 0
            win = (sum(1 for r in hold_rets if r > 0) / n * 100) if n else 0
            fwd1 = hold_rets[0] if n >= 1 else None
            fwd4 = sum(hold_rets[:4]) if n >= 4 else None

            f1s = f"{fwd1:>+7.1f}" if fwd1 is not None else "    N/A"
            f4s = f"{fwd4:>+7.1f}" if fwd4 is not None else "    N/A"
            print(f"  {name:<26} {eq:>10} {es:>6.3f} {n:>4}"
                  f" {cum:>+8.1f}% {avg_q:>+7.2f}% {win:>4.0f}%"
                  f" {f1s}% {f4s}%")

            strat_results.append((name, eq, es, hold_rets))

            # aggregate
            a = agg[name]
            if fwd1 is not None: a["fwd1"].append(fwd1)
            if fwd4 is not None: a["fwd4"].append(fwd4)
            a["all_rets"].extend(hold_rets)
            a["cum"].append(cum)

        # ── Opportunity cost vs earliest entry ──
        valid = [(name, eq) for name, eq, _, _ in strat_results if eq is not None]
        if len(valid) > 1:
            earliest_q = min(valid, key=lambda x: quarters.index(x[1]))[1]
            print(f"\n  Opportunity cost vs earliest entry ({earliest_q}):")
            e_idx = show_qs.index(earliest_q) if earliest_q in show_qs else 0

            for name, eq, _, _ in strat_results:
                if eq is None or eq == earliest_q:
                    continue
                if eq in show_qs:
                    this_idx = show_qs.index(eq)
                else:
                    this_idx = 0
                    for i, q in enumerate(show_qs):
                        if quarters.index(q) >= quarters.index(eq):
                            this_idx = i
                            break
                missed = []
                for i in range(e_idx, this_idx):
                    r = rets.get(show_qs[i])
                    if r is not None:
                        missed.append(r)
                missed_sum = sum(missed)
                wait = this_idx - e_idx
                avg_missed = statistics.mean(missed) if missed else 0
                print(f"    {name}: waited {wait}Q, missed {missed_sum:>+.1f}%"
                      f" (avg {avg_missed:>+.1f}%/Q)")

        # ── False entry check ──
        # For immediate entry, check if brand fell off list within 2 quarters
        eq_a = entries["A: First appearance"]
        if eq_a:
            a_idx = quarters.index(eq_a)
            fell_off = False
            for brand in brands:
                bd = brand_data.get(brand, {})
                if bd.get(eq_a, UNRANKED) < UNRANKED:
                    next_qs_on = 0
                    for j in range(a_idx + 1, min(a_idx + 4, len(quarters))):
                        if bd.get(quarters[j], UNRANKED) < UNRANKED:
                            next_qs_on += 1
                        else:
                            break
                    if next_qs_on < 2:
                        fell_off = True
                        print(f"\n  WARNING: False entry risk: {brand} appeared {eq_a}"
                              f" but only stayed {next_qs_on + 1}Q on list")

    # ════════════════════════════════════════════
    # AGGREGATE
    # ════════════════════════════════════════════
    print(f"\n{'=' * 80}")
    print("AGGREGATE: All 3 Companies (Prada + Tapestry + RL)")
    print(f"{'=' * 80}")

    print(f"\n  {'Strategy':<26} {'N':>3}"
          f" {'AvgFwd1Q':>9} {'AvgFwd4Q':>9}"
          f" {'AvgCum':>8} {'Avg/Q':>7} {'Win%':>5}")
    print(f"  {'─' * 26} {'─' * 3}"
          f" {'─' * 9} {'─' * 9}"
          f" {'─' * 8} {'─' * 7} {'─' * 5}")

    for name in STRAT_NAMES:
        a = agg[name]
        n = len(a["cum"])
        f1 = statistics.mean(a["fwd1"]) if a["fwd1"] else None
        f4 = statistics.mean(a["fwd4"]) if a["fwd4"] else None
        ac = statistics.mean(a["cum"]) if a["cum"] else None
        aq = statistics.mean(a["all_rets"]) if a["all_rets"] else None
        aw = (sum(1 for r in a["all_rets"] if r > 0) / len(a["all_rets"]) * 100
              ) if a["all_rets"] else None

        f1s = f"{f1:>+9.2f}%" if f1 is not None else "      N/A"
        f4s = f"{f4:>+9.2f}%" if f4 is not None else "      N/A"
        acs = f"{ac:>+8.1f}%" if ac is not None else "     N/A"
        aqs = f"{aq:>+7.2f}%" if aq is not None else "    N/A"
        aws = f"{aw:>4.0f}%" if aw is not None else "  N/A"

        print(f"  {name:<26} {n:>3} {f1s} {f4s} {acs} {aqs} {aws}")

    # ── Signal quality: forward 1Q per entry event ──
    print(f"\n  Per-entry signal quality (forward 1Q excess):")
    print(f"  {'Strategy':<26} {'Company':<15} {'Entry':>10} {'Score':>6} {'Fwd1Q':>7}")
    print(f"  {'─' * 26} {'─' * 15} {'─' * 10} {'─' * 6} {'─' * 7}")

    for name in STRAT_NAMES:
        for company in COMPANIES:
            if company not in excess_ret:
                continue
            brands = COMPANIES[company]["brands"]
            scores = co_scores[company]
            rets = excess_ret[company]

            eq = None
            if name == "A: First appearance":
                eq = find_first_appearance(brands, brand_data, quarters)
            elif name == "B: 2Q on list":
                eq = find_2q_on_list(brands, brand_data, quarters)
            elif name == "C: 3Q confirmed+improving":
                eq = find_3q_confirmed(brands, brand_data, quarters)
            elif name == "D: Score >= 0.3":
                eq = find_score_threshold(scores, show_qs, 0.3)
            elif name == "E: Score >= 0.5":
                eq = find_score_threshold(scores, show_qs, 0.5)
            elif name == "F: 2Q score momentum":
                eq = find_2q_momentum(scores, show_qs)
            elif name == "G: Brand enters Top 10":
                eq = find_top10_entry(brands, brand_data, quarters)

            if eq is None:
                continue

            es = scores.get(eq, 0)
            hold = returns_from(eq, show_qs, rets, quarters)
            fwd1 = hold[0][1] if hold else None
            f1s = f"{fwd1:>+7.1f}%" if fwd1 is not None else "    N/A"
            print(f"  {name:<26} {company:<15} {eq:>10} {es:>6.3f} {f1s}")

    # ── Key takeaway ──
    print(f"\n{'─' * 80}")
    print("  KEY QUESTION: Is waiting for 3Q confirmation worth the opportunity cost?")
    print(f"{'─' * 80}")

    # Compare Strategy A vs C
    a_all = agg["A: First appearance"]["all_rets"]
    c_all = agg["C: 3Q confirmed+improving"]["all_rets"]
    a_cum = agg["A: First appearance"]["cum"]
    c_cum = agg["C: 3Q confirmed+improving"]["cum"]

    if a_all and c_all:
        print(f"\n  Strategy A (immediate):     avg {statistics.mean(a_all):+.2f}%/Q,"
              f" total qs={len(a_all)}, avg cum={statistics.mean(a_cum):+.1f}%")
        print(f"  Strategy C (3Q confirmed):  avg {statistics.mean(c_all):+.2f}%/Q,"
              f" total qs={len(c_all)}, avg cum={statistics.mean(c_cum):+.1f}%")

        a_fwd1 = agg["A: First appearance"]["fwd1"]
        c_fwd1 = agg["C: 3Q confirmed+improving"]["fwd1"]
        if a_fwd1 and c_fwd1:
            print(f"\n  Fwd 1Q at entry:  A={statistics.mean(a_fwd1):+.1f}%"
                  f"  vs  C={statistics.mean(c_fwd1):+.1f}%")
        a_fwd4 = agg["A: First appearance"]["fwd4"]
        c_fwd4 = agg["C: 3Q confirmed+improving"]["fwd4"]
        if a_fwd4 and c_fwd4:
            print(f"  Fwd 4Q at entry:  A={statistics.mean(a_fwd4):+.1f}%"
                  f"  vs  C={statistics.mean(c_fwd4):+.1f}%")


if __name__ == "__main__":
    main()

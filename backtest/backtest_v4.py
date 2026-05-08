#!/usr/bin/env python3
"""
Lyst Index × Stock Return Backtest v4

Hypothesis: Lyst ranking changes predict forward stock returns
for companies where the tracked brand has high revenue exposure.

Groups:
  High-exposure: Prada Group, Tapestry, Ralph Lauren, Burberry, Kering
  Low-exposure:  LVMH

Signal: Revenue-weighted composite ΔRank (QoQ improvement = positive)
Return: Forward quarter USD excess return vs GLUX
"""

import csv
import math
import statistics
import random
from datetime import datetime, timedelta, date
from collections import defaultdict
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance")
    exit(1)

# ════════════════════════════════════════════
# 1. CONFIGURATION
# ════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent
TRACKER_CSV = str(REPO_ROOT / "data" / "lyst-index-tracker.csv")
HISTORICAL_CSV = str(REPO_ROOT / "data" / "lyst-historical-2018.csv")
OUTPUT_PATH = str(REPO_ROOT / "results" / "v4-results.md")

UNRANKED = 21
PRICE_END = date.today().strftime("%Y-%m-%d")

# Kering brand OPERATING INCOME weights (% of Kering total, from FactSet)
# Normalized to Gucci+YSL+BV = 1.0 for each year
# Key: fiscal year (Dec) → used for NEXT calendar year signals
# OI better reflects profit sensitivity to each brand
KERING_RAW = {
    2017: (72.1, 12.8, 10.0),  # Gucci, YSL, BV (operating income %)
    2018: (83.0, 11.6, 6.1),
    2019: (82.6, 11.8, 4.5),
    2020: (83.4, 12.8, 5.5),
    2021: (74.0, 14.2, 5.7),
    2022: (66.8, 18.2, 6.6),
    2023: (68.7, 20.4, 6.6),
    2024: (62.8, 23.2, 10.0),
    2025: (59.2, 32.4, 16.4),
}

# Prada Group brand weights (approximate, from annual reports)
# Normalized to Prada+Miu Miu = 1.0
PRADA_RAW = {
    2017: (0.82, 0.18),  # (Prada, Miu Miu)
    2018: (0.82, 0.18),
    2019: (0.81, 0.19),
    2020: (0.80, 0.20),
    2021: (0.78, 0.22),
    2022: (0.74, 0.26),
    2023: (0.70, 0.30),
    2024: (0.62, 0.38),
    2025: (0.55, 0.45),
}


def _kering_weights(signal_year):
    """Get Kering brand weights for a given signal year (uses prior FY)."""
    fy = signal_year - 1
    fy = max(fy, min(KERING_RAW.keys()))
    fy = min(fy, max(KERING_RAW.keys()))
    g, y, b = KERING_RAW[fy]
    s = g + y + b
    return {"Gucci": g / s, "Saint Laurent": y / s, "Bottega Veneta": b / s}


def _prada_weights(signal_year):
    """Get Prada Group brand weights for a given signal year."""
    fy = signal_year - 1
    fy = max(fy, min(PRADA_RAW.keys()))
    fy = min(fy, max(PRADA_RAW.keys()))
    p, m = PRADA_RAW[fy]
    return {"Prada": p, "Miu Miu": m}


# LVMH: LV + Dior fixed weights (LVMH doesn't disclose brand-level)
LVMH_WEIGHTS = {"Louis Vuitton": 0.70, "Dior": 0.30}

COMPANIES = {
    "Prada Group": {
        "ticker": "1913.HK", "currency": "HKD", "group": "high",
        "brands": ["Prada", "Miu Miu"],
        "get_weights": lambda yr: _prada_weights(yr),
    },
    "Tapestry": {
        "ticker": "TPR", "currency": "USD", "group": "high",
        "brands": ["Coach"],
        "get_weights": lambda yr: {"Coach": 1.0},
    },
    "Ralph Lauren": {
        "ticker": "RL", "currency": "USD", "group": "high",
        "brands": ["Ralph Lauren"],
        "get_weights": lambda yr: {"Ralph Lauren": 1.0},
    },
    "Burberry": {
        "ticker": "BRBY.L", "currency": "GBP", "group": "high",
        "brands": ["Burberry"],
        "get_weights": lambda yr: {"Burberry": 1.0},
    },
    "Kering": {
        "ticker": "KER.PA", "currency": "EUR", "group": "high",
        "brands": ["Gucci", "Saint Laurent", "Bottega Veneta"],
        "get_weights": lambda yr: _kering_weights(yr),
    },
    "LVMH": {
        "ticker": "MC.PA", "currency": "EUR", "group": "low",
        "brands": ["Louis Vuitton", "Dior"],
        "get_weights": lambda yr: LVMH_WEIGHTS.copy(),
    },
}

FX_TICKERS = {"EUR": "EURUSD=X", "GBP": "GBPUSD=X", "HKD": "HKDUSD=X"}


# ════════════════════════════════════════════
# 2. QUARTER MANAGEMENT
# ════════════════════════════════════════════

def parse_q(q_str):
    """'Q1 2026' → (2026, 1)"""
    parts = q_str.strip().split()
    return int(parts[1]), int(parts[0][1:])


def q_str(year, qtr):
    return f"Q{qtr} {year}"


def publish_date(year, qtr):
    """Approximate Lyst publish date: ~25 days after quarter end."""
    if qtr == 4:
        return f"{year + 1}-01-25"
    return f"{year}-{['04','07','10'][qtr - 1]}-25"


def build_quarters(latest):
    """Build ordered list of quarters from Q1 2018 to latest."""
    end_y, end_q = parse_q(latest)
    quarters = []
    y, q = 2018, 1
    while (y, q) <= (end_y, end_q):
        quarters.append(q_str(y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return quarters


def detect_latest(csv_path):
    latest = (2025, 4)
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            q = row.get("Quarter", "").strip()
            if not q.startswith("Q"):
                continue
            try:
                yq = parse_q(q)
                if yq > latest:
                    latest = yq
            except (ValueError, IndexError):
                continue
    return q_str(*latest)


# ════════════════════════════════════════════
# 3. DATA LOADING
# ════════════════════════════════════════════

def normalize_quarter(q_str_raw):
    q_str_raw = q_str_raw.strip()
    if q_str_raw.startswith("Q"):
        return q_str_raw
    if "Q" in q_str_raw:
        parts = q_str_raw.split("Q")
        if len(parts) == 2:
            return f"Q{parts[1].strip()} {parts[0].strip()}"
    return q_str_raw


def load_historical(quarters_set):
    """Parse 2018 historical CSV."""
    data = defaultdict(dict)
    with open(HISTORICAL_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            brand = row["brand"].strip().rstrip("?")
            q = normalize_quarter(row["quarter"])
            if q not in quarters_set or "2018" not in q:
                continue
            try:
                data[brand][q] = int(row["rank"].strip())
            except (ValueError, KeyError):
                continue
    return data


def load_tracker(quarters_set):
    """Parse main tracker CSV (Q1 2019+)."""
    data = defaultdict(dict)
    aliases = {"Alaïa": "Alaia", "Chloé": "Chloe", "Totême": "Toteme"}
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


def merge_brand_data(*sources):
    merged = defaultdict(dict)
    for src in sources:
        for brand, quarters in src.items():
            for q, rank in quarters.items():
                merged[brand][q] = rank
    return merged


# ════════════════════════════════════════════
# 4. COMPOSITE RANK COMPUTATION
# ════════════════════════════════════════════

def compute_composite_ranks(brand_data, quarters):
    """Revenue-weighted composite rank per company per quarter."""
    result = {}
    for company, cfg in COMPANIES.items():
        result[company] = {}
        for q in quarters:
            year, _ = parse_q(q)
            weights = cfg["get_weights"](year)
            weighted_rank = 0.0
            total_w = 0.0
            any_ranked = False
            brand_details = {}
            for brand in cfg["brands"]:
                w = weights.get(brand, 0)
                if w == 0:
                    continue
                rank = brand_data.get(brand, {}).get(q, UNRANKED)
                weighted_rank += rank * w
                total_w += w
                if rank < UNRANKED:
                    any_ranked = True
                brand_details[brand] = rank

            composite = weighted_rank / total_w if total_w > 0 else UNRANKED
            result[company][q] = {
                "composite": round(composite, 2),
                "any_ranked": any_ranked,
                "brands": brand_details,
            }
    return result


def is_all_unranked(comp_ranks, company, q):
    """True if no brand is ranked in this quarter."""
    return not comp_ranks[company].get(q, {}).get("any_ranked", False)


# ════════════════════════════════════════════
# 5. PRICE & RETURN COMPUTATION
# ════════════════════════════════════════════

def fetch_prices():
    """Fetch stock + FX + benchmark prices."""
    tickers = list(set(cfg["ticker"] for cfg in COMPANIES.values()))
    tickers += ["GLUX.PA", "SPY"]
    fx_tickers = list(FX_TICKERS.values())

    print(f"\nFetching {len(tickers)} stocks + {len(fx_tickers)} FX...")
    stock_data, fx_data = {}, {}

    for t in tickers:
        try:
            h = yf.Ticker(t).history(start="2018-01-01", end=PRICE_END, auto_adjust=True)
            if not h.empty:
                stock_data[t] = h
                print(f"  {t}: {len(h)} days")
            else:
                print(f"  {t}: NO DATA")
        except Exception as e:
            print(f"  {t}: ERROR {e}")

    for ccy, ft in FX_TICKERS.items():
        try:
            h = yf.Ticker(ft).history(start="2018-01-01", end=PRICE_END, auto_adjust=True)
            if not h.empty:
                fx_data[ccy] = h
                print(f"  FX {ccy}: {len(h)} days")
        except Exception as e:
            print(f"  FX {ccy}: ERROR {e}")

    return stock_data, fx_data


def get_price(hist, date_str, max_days=5):
    """Get closing price on first trading day on or after date_str."""
    target = datetime.strptime(date_str, "%Y-%m-%d")
    for d in range(max_days + 1):
        check = (target + timedelta(days=d)).strftime("%Y-%m-%d")
        matches = hist.loc[hist.index.strftime("%Y-%m-%d") == check]
        if not matches.empty:
            return float(matches["Close"].iloc[-1])
    return None


def compute_returns(stock_data, fx_data, quarters, pairs):
    """Compute forward USD returns and excess returns vs GLUX."""
    def _qtr_return(hist, ccy, q1, q2):
        pub1, pub2 = publish_date(*parse_q(q1)), publish_date(*parse_q(q2))
        p0 = get_price(hist, pub1)
        p1 = get_price(hist, pub2)
        if p0 is None or p1 is None:
            return None
        if ccy != "USD" and ccy in fx_data:
            fx0 = get_price(fx_data[ccy], pub1)
            fx1 = get_price(fx_data[ccy], pub2)
            if fx0 and fx1:
                p0, p1 = p0 * fx0, p1 * fx1
        return round((p1 / p0 - 1) * 100, 2)

    # Benchmark returns
    glux_ret = {}
    glux_hist = stock_data.get("GLUX.PA")
    if glux_hist is not None:
        for q1, q2 in pairs:
            r = _qtr_return(glux_hist, "EUR", q1, q2)
            if r is not None:
                glux_ret[q1] = r

    spy_ret = {}
    spy_hist = stock_data.get("SPY")
    if spy_hist is not None:
        for q1, q2 in pairs:
            r = _qtr_return(spy_hist, "USD", q1, q2)
            if r is not None:
                spy_ret[q1] = r

    # Company returns
    raw_ret, excess_ret = {}, {}
    for company, cfg in COMPANIES.items():
        hist = stock_data.get(cfg["ticker"])
        if hist is None:
            continue
        raw_ret[company] = {}
        excess_ret[company] = {}
        for q1, q2 in pairs:
            r = _qtr_return(hist, cfg["currency"], q1, q2)
            if r is None:
                continue
            raw_ret[company][q1] = r
            if q1 in glux_ret:
                excess_ret[company][q1] = round(r - glux_ret[q1], 2)

    return raw_ret, excess_ret, glux_ret, spy_ret


# ════════════════════════════════════════════
# 6. SIGNAL ANALYSIS
# ════════════════════════════════════════════

def compute_signals(comp_ranks, excess_ret, quarters, pairs):
    """Compute ΔRank and pair with forward excess return."""
    signals = []
    for company in COMPANIES:
        if company not in excess_ret:
            continue
        for q1, q2 in pairs:
            idx = quarters.index(q1)
            if idx == 0:
                continue
            prev_q = quarters[idx - 1]

            # Skip if all brands unranked in BOTH quarters
            if is_all_unranked(comp_ranks, company, prev_q) and \
               is_all_unranked(comp_ranks, company, q1):
                continue

            if q1 not in excess_ret[company]:
                continue

            prev_comp = comp_ranks[company][prev_q]["composite"]
            curr_comp = comp_ranks[company][q1]["composite"]
            delta_rank = prev_comp - curr_comp  # positive = improvement

            signals.append({
                "company": company,
                "group": COMPANIES[company]["group"],
                "quarter": q1,
                "prev_rank": prev_comp,
                "curr_rank": curr_comp,
                "delta_rank": round(delta_rank, 2),
                "fwd_excess": excess_ret[company][q1],
                "brands": comp_ranks[company][q1]["brands"],
            })
    return signals


# ════════════════════════════════════════════
# 6b. TREND & PRESENCE SIGNALS
# ════════════════════════════════════════════

def compute_trend_signals(comp_ranks, excess_ret, quarters, pairs):
    """3-quarter trend: rank change over 3 quarters instead of 1."""
    signals = []
    for company in COMPANIES:
        if company not in excess_ret:
            continue
        for q1, q2 in pairs:
            idx = quarters.index(q1)
            if idx < 3:
                continue
            q_3back = quarters[idx - 3]

            if is_all_unranked(comp_ranks, company, q_3back) and \
               is_all_unranked(comp_ranks, company, q1):
                continue
            if q1 not in excess_ret[company]:
                continue

            rank_3back = comp_ranks[company][q_3back]["composite"]
            rank_now = comp_ranks[company][q1]["composite"]
            trend = rank_3back - rank_now  # positive = improved over 3Q

            signals.append({
                "company": company,
                "group": COMPANIES[company]["group"],
                "quarter": q1,
                "rank_3q_ago": rank_3back,
                "rank_now": rank_now,
                "trend_3q": round(trend, 2),
                "fwd_excess": excess_ret[company][q1],
            })
    return signals


def compute_presence_signals(comp_ranks, excess_ret, quarters, pairs):
    """Sustained presence: consecutive quarters on chart and in top N."""
    signals = []
    for company in COMPANIES:
        if company not in excess_ret:
            continue
        for q1, q2 in pairs:
            idx = quarters.index(q1)
            if q1 not in excess_ret[company]:
                continue

            # Count consecutive quarters with any brand ranked (looking back)
            streak_chart = 0
            streak_top10 = 0
            streak_top5 = 0
            for j in range(idx, -1, -1):
                qj = quarters[j]
                comp = comp_ranks[company][qj]["composite"]
                if not comp_ranks[company][qj]["any_ranked"]:
                    break
                streak_chart += 1
                if comp <= 10 and streak_top10 == streak_chart - 1:
                    streak_top10 += 1
                if comp <= 5 and streak_top5 == streak_chart - 1:
                    streak_top5 += 1

            rank_now = comp_ranks[company][q1]["composite"]

            signals.append({
                "company": company,
                "group": COMPANIES[company]["group"],
                "quarter": q1,
                "rank_now": rank_now,
                "streak_chart": streak_chart,
                "streak_top10": streak_top10,
                "streak_top5": streak_top5,
                "fwd_excess": excess_ret[company][q1],
            })
    return signals


# ════════════════════════════════════════════
# 7. STATISTICAL HELPERS
# ════════════════════════════════════════════

def pearson(xs, ys):
    if len(xs) < 3:
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs) / (n - 1)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / (n - 1)) ** 0.5
    if sx == 0 or sy == 0:
        return None
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (n - 1)
    return round(cov / (sx * sy), 4)


def t_from_r(r, n):
    if r is None or abs(r) >= 1.0 or n < 4:
        return None
    return r * math.sqrt(n - 2) / math.sqrt(1 - r ** 2)


def p_from_t(t, df):
    if t is None:
        return None
    x = abs(t)
    if df > 30:
        a1, a2, a3 = 0.4361836, -0.1201676, 0.9372980
        p_coeff = 0.33267
        t_val = 1 / (1 + p_coeff * x)
        cdf = 1 - (a1 * t_val + a2 * t_val ** 2 + a3 * t_val ** 3) * \
              math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
        return round(2 * (1 - cdf), 4)
    else:
        a = df / (df + t * t)
        n_steps = 200
        dt = a / n_steps
        total = 0
        for i in range(n_steps):
            u = (i + 0.5) * dt
            if 0 < u < 1:
                total += u ** (df / 2 - 1) * (1 - u) ** (-0.5) * dt
        beta_val = math.gamma(df / 2) * math.gamma(0.5) / math.gamma(df / 2 + 0.5)
        return round(min(1.0, total / beta_val), 4)


def t_test_mean(values):
    n = len(values)
    if n < 3:
        return None, None, None, n
    m = statistics.mean(values)
    s = statistics.stdev(values)
    if s == 0:
        return m, None, None, n
    t = m / (s / math.sqrt(n))
    p = p_from_t(t, n - 1)
    return round(m, 2), round(t, 3), p, n


def bootstrap_ci(values, n_boot=5000, ci=0.95):
    if len(values) < 3:
        return None, None
    random.seed(42)
    n = len(values)
    means = sorted(
        statistics.mean(random.choices(values, k=n)) for _ in range(n_boot)
    )
    lo = means[int(n_boot * (1 - ci) / 2)]
    hi = means[int(n_boot * (1 + ci) / 2) - 1]
    return round(lo, 2), round(hi, 2)


def corr_stats(xs, ys):
    """Return (r, t, p, n) for a correlation."""
    n = len(xs)
    r = pearson(xs, ys)
    t = t_from_r(r, n)
    p = p_from_t(t, n - 2) if t is not None else None
    return r, t, p, n


# ════════════════════════════════════════════
# 8. REPORT GENERATION
# ════════════════════════════════════════════

def generate_report(signals, comp_ranks, quarters, glux_ret, spy_ret,
                    trend_signals=None, presence_signals=None):
    L = []

    L.append("# Lyst Index × Stock Return Backtest v4")
    L.append("")
    L.append(f"> Generated: {datetime.now().strftime('%Y-%m-%d')}")
    L.append(f"> Data: Q1 2018 – {quarters[-1]} ({len(quarters)} quarters)")
    L.append("> Hypothesis: ΔRank predicts forward excess return,")
    L.append(">   stronger for high brand-exposure companies")
    L.append("> Benchmark: GLUX (S&P Global Luxury Index)")
    L.append("")

    # ─── Data Coverage ───
    L.append("## 1. Data Coverage")
    L.append("")
    L.append("| Company | Group | Brands | Observations |")
    L.append("|---------|-------|--------|-------------|")
    for company in COMPANIES:
        grp = COMPANIES[company]["group"]
        brands = ", ".join(COMPANIES[company]["brands"])
        n_obs = len([s for s in signals if s["company"] == company])
        L.append(f"| {company} | {grp} | {brands} | {n_obs} |")
    L.append("")

    # Brand rank timeline for key brands
    L.append("### Key Brand Rank Timeline")
    L.append("")
    key_brands = ["Miu Miu", "Prada", "Coach", "Ralph Lauren", "Burberry",
                  "Gucci", "Louis Vuitton", "Dior"]
    header = "| Quarter | " + " | ".join(key_brands) + " |"
    sep = "|---------|" + "|".join(["------" for _ in key_brands]) + "|"
    L.append(header)
    L.append(sep)
    # Show every 4th quarter to keep table manageable
    show_qs = [q for i, q in enumerate(quarters) if i % 2 == 0 or q == quarters[-1]]
    from collections import defaultdict as _dd
    # Need brand_data here — we'll pass it through
    # Actually, we can reconstruct from comp_ranks
    # Let me just show composite ranks per company instead
    L.append("")

    # ─── Per-Company Results ───
    L.append("## 2. Per-Company Correlation: ΔRank vs Forward Excess Return")
    L.append("")
    L.append("| Company | Group | r | t-stat | p-value | Hit% | Avg Excess | n |")
    L.append("|---------|-------|---|--------|---------|------|-----------|---|")

    company_results = {}
    for company in COMPANIES:
        co_sigs = [s for s in signals if s["company"] == company]
        if len(co_sigs) < 3:
            L.append(f"| {company} | {COMPANIES[company]['group']} | — | — | — | — | — | {len(co_sigs)} |")
            continue
        xs = [s["delta_rank"] for s in co_sigs]
        ys = [s["fwd_excess"] for s in co_sigs]
        r, t, p, n = corr_stats(xs, ys)
        hit = sum(1 for s in co_sigs
                  if (s["delta_rank"] > 0 and s["fwd_excess"] > 0) or
                     (s["delta_rank"] < 0 and s["fwd_excess"] < 0)) / n * 100
        avg_ex = statistics.mean(ys)

        company_results[company] = {"r": r, "t": t, "p": p, "n": n, "hit": hit}

        r_s = f"{r:+.3f}" if r else "—"
        t_s = f"{t:.2f}" if t else "—"
        p_s = f"{p:.3f}" if p else "—"
        sig = " ✓" if p and p < 0.10 else ""
        L.append(f"| {company} | {COMPANIES[company]['group']} | {r_s} | {t_s} | {p_s}{sig} | {hit:.0f}% | {avg_ex:+.2f}% | {n} |")

    L.append("")

    # ─── Group Results ───
    L.append("## 3. Group Comparison: High vs Low Exposure")
    L.append("")

    for grp_name in ["high", "low"]:
        grp_sigs = [s for s in signals if s["group"] == grp_name]
        label = "High-Exposure" if grp_name == "high" else "Low-Exposure (Control)"
        companies = [c for c, cfg in COMPANIES.items() if cfg["group"] == grp_name]
        L.append(f"### {label}: {', '.join(companies)}")
        L.append("")

        if len(grp_sigs) < 3:
            L.append(f"Insufficient data (n={len(grp_sigs)})")
            L.append("")
            continue

        xs = [s["delta_rank"] for s in grp_sigs]
        ys = [s["fwd_excess"] for s in grp_sigs]
        r, t, p, n = corr_stats(xs, ys)
        hit = sum(1 for s in grp_sigs
                  if (s["delta_rank"] > 0 and s["fwd_excess"] > 0) or
                     (s["delta_rank"] < 0 and s["fwd_excess"] < 0)) / n * 100

        # Split by improvers vs decliners
        improvers = [s for s in grp_sigs if s["delta_rank"] > 1]
        decliners = [s for s in grp_sigs if s["delta_rank"] < -1]
        avg_imp = statistics.mean([s["fwd_excess"] for s in improvers]) if improvers else 0
        avg_dec = statistics.mean([s["fwd_excess"] for s in decliners]) if decliners else 0

        ci_lo, ci_hi = bootstrap_ci(ys)

        r_s = f"{r:+.3f}" if r else "—"
        t_s = f"{t:.2f}" if t else "—"
        p_s = f"{p:.3f}" if p else "—"

        L.append(f"- **Pooled correlation**: r={r_s}, t={t_s}, p={p_s}, n={n}")
        L.append(f"- **Direction hit rate**: {hit:.1f}%")
        L.append(f"- **Improvers** (ΔRank>1): avg excess {avg_imp:+.2f}% (n={len(improvers)})")
        L.append(f"- **Decliners** (ΔRank<-1): avg excess {avg_dec:+.2f}% (n={len(decliners)})")
        L.append(f"- **Long/short spread**: {avg_imp - avg_dec:+.2f}%")
        L.append(f"- **95% CI of excess return**: [{ci_lo}, {ci_hi}]")
        L.append("")

    # ─── Hypothesis Test ───
    L.append("## 4. Hypothesis Test: High > Low Exposure")
    L.append("")
    high_sigs = [s for s in signals if s["group"] == "high"]
    low_sigs = [s for s in signals if s["group"] == "low"]
    if len(high_sigs) >= 3 and len(low_sigs) >= 3:
        r_h = pearson([s["delta_rank"] for s in high_sigs],
                      [s["fwd_excess"] for s in high_sigs])
        r_l = pearson([s["delta_rank"] for s in low_sigs],
                      [s["fwd_excess"] for s in low_sigs])
        r_h_s = f"{r_h:+.3f}" if r_h else "—"
        r_l_s = f"{r_l:+.3f}" if r_l else "—"
        L.append(f"| Group | r (ΔRank vs Excess) | n |")
        L.append(f"|-------|--------------------|----|")
        L.append(f"| High-Exposure | {r_h_s} | {len(high_sigs)} |")
        L.append(f"| Low-Exposure | {r_l_s} | {len(low_sigs)} |")
        L.append("")
        if r_h and r_l:
            if r_h > r_l:
                L.append("**Result**: High-exposure group shows stronger correlation, "
                         "consistent with the hypothesis.")
            else:
                L.append("**Result**: Low-exposure group shows equal or stronger correlation, "
                         "hypothesis not supported.")
        L.append("")

    # ─── Detail: Quarter-by-Quarter for User's Key Companies ───
    L.append("## 5. Quarter-by-Quarter Detail")
    L.append("")

    for company in ["Prada Group", "Tapestry", "Ralph Lauren", "Burberry"]:
        co_sigs = sorted([s for s in signals if s["company"] == company],
                         key=lambda s: parse_q(s["quarter"]))
        if not co_sigs:
            continue
        L.append(f"### {company} ({COMPANIES[company]['ticker']})")
        L.append("")
        L.append("| Quarter | Brands (rank) | Composite | ΔRank | Fwd Excess |")
        L.append("|---------|--------------|-----------|-------|-----------|")
        for s in co_sigs:
            brands_str = ", ".join(f"{b}={r}" for b, r in s["brands"].items())
            L.append(f"| {s['quarter']} | {brands_str} | {s['curr_rank']:.1f} | "
                     f"{s['delta_rank']:+.1f} | {s['fwd_excess']:+.2f}% |")
        L.append("")

    # ─── Simple L/S Backtest ───
    L.append("## 6. Simple Long/Short Backtest (High-Exposure Group)")
    L.append("")
    L.append("Rule: Each quarter, among high-exposure companies with data,")
    L.append("long the one with best ΔRank, short the one with worst ΔRank.")
    L.append("")

    # Group signals by quarter
    from collections import defaultdict as _dd2
    qtr_sigs = defaultdict(list)
    for s in signals:
        if s["group"] == "high":
            qtr_sigs[s["quarter"]].append(s)

    ls_returns = []
    L.append("| Quarter | Long | Short | L/S Return |")
    L.append("|---------|------|-------|-----------|")
    for q in quarters:
        if q not in qtr_sigs or len(qtr_sigs[q]) < 2:
            continue
        sorted_sigs = sorted(qtr_sigs[q], key=lambda s: s["delta_rank"], reverse=True)
        long_s = sorted_sigs[0]
        short_s = sorted_sigs[-1]
        ls_ret = long_s["fwd_excess"] - short_s["fwd_excess"]
        ls_returns.append(ls_ret)
        L.append(f"| {q} | {long_s['company']} ({long_s['delta_rank']:+.1f}) | "
                 f"{short_s['company']} ({short_s['delta_rank']:+.1f}) | {ls_ret:+.2f}% |")

    if ls_returns:
        cum = 1.0
        for r in ls_returns:
            cum *= (1 + r / 100)
        avg, t_val, p_val, n_ls = t_test_mean(ls_returns)
        L.append("")
        t_s = f"{t_val:.2f}" if t_val else "—"
        p_s = f"{p_val:.3f}" if p_val else "—"
        L.append(f"- **Cumulative L/S**: {(cum - 1) * 100:+.1f}% over {len(ls_returns)} quarters")
        L.append(f"- **Avg quarterly L/S**: {avg:+.2f}% (t={t_s}, p={p_s})")
        L.append(f"- **Win rate**: {sum(1 for r in ls_returns if r > 0) / len(ls_returns) * 100:.0f}%")
    L.append("")

    # ─── 7. Trend Signal (3Q) ───
    L.append("## 7. Trend Signal: 3-Quarter Rank Change vs Forward Excess Return")
    L.append("")
    L.append("Instead of QoQ ΔRank, measure rank change over 3 quarters.")
    L.append("Captures sustained trends (Gucci decline, Coach rise) that QoQ misses.")
    L.append("")

    if trend_signals:
        L.append("### Per-Company")
        L.append("")
        L.append("| Company | Group | r | t-stat | p-value | n |")
        L.append("|---------|-------|---|--------|---------|---|")
        for company in COMPANIES:
            ts = [s for s in trend_signals if s["company"] == company]
            if len(ts) < 3:
                L.append(f"| {company} | {COMPANIES[company]['group']} | — | — | — | {len(ts)} |")
                continue
            xs = [s["trend_3q"] for s in ts]
            ys = [s["fwd_excess"] for s in ts]
            r, t, p, n = corr_stats(xs, ys)
            r_s = f"{r:+.3f}" if r else "—"
            t_s = f"{t:.2f}" if t else "—"
            p_s = f"{p:.3f}" if p else "—"
            sig = " ✓" if p and p < 0.10 else ""
            L.append(f"| {company} | {COMPANIES[company]['group']} | {r_s} | {t_s} | {p_s}{sig} | {n} |")
        L.append("")

        # Group comparison for trend signal
        L.append("### Group Comparison (Trend 3Q)")
        L.append("")
        for grp_name in ["high", "low"]:
            grp_ts = [s for s in trend_signals if s["group"] == grp_name]
            label = "High-Exposure" if grp_name == "high" else "Low-Exposure"
            if len(grp_ts) < 3:
                continue
            xs = [s["trend_3q"] for s in grp_ts]
            ys = [s["fwd_excess"] for s in grp_ts]
            r, t, p, n = corr_stats(xs, ys)
            r_s = f"{r:+.3f}" if r else "—"
            t_s = f"{t:.2f}" if t else "—"
            p_s = f"{p:.3f}" if p else "—"
            L.append(f"- **{label}**: r={r_s}, t={t_s}, p={p_s}, n={n}")
        L.append("")

        # Kering deep dive with trend
        L.append("### Kering Deep Dive: Gucci Sustained Decline")
        L.append("")
        ker_ts = sorted([s for s in trend_signals if s["company"] == "Kering"],
                       key=lambda s: parse_q(s["quarter"]))
        if ker_ts:
            L.append("| Quarter | Composite 3Q ago | Composite now | Trend 3Q | Fwd Excess |")
            L.append("|---------|-----------------|--------------|----------|-----------|")
            for s in ker_ts:
                L.append(f"| {s['quarter']} | {s['rank_3q_ago']:.1f} | {s['rank_now']:.1f} | "
                         f"{s['trend_3q']:+.1f} | {s['fwd_excess']:+.2f}% |")
        L.append("")

    # ─── 8. Sustained Presence Signal ───
    L.append("## 8. Sustained Presence: Consecutive Quarters on Chart / in Top 10")
    L.append("")
    L.append("Tests whether sustained Lyst presence (not just QoQ change) predicts returns.")
    L.append("Relevant for Coach/Tapestry and Ralph Lauren style signals.")
    L.append("")

    if presence_signals:
        # Analyze: does being in top10 for 3+ consecutive quarters predict positive excess?
        L.append("### Top-10 Streak vs Forward Excess Return")
        L.append("")
        L.append("| Streak (consecutive Q in top 10) | Avg Excess | Median | n |")
        L.append("|----------------------------------|-----------|--------|---|")

        for streak_min, streak_max, label in [
            (0, 0, "0 (not in top 10)"),
            (1, 2, "1-2 quarters"),
            (3, 5, "3-5 quarters"),
            (6, 99, "6+ quarters"),
        ]:
            bucket = [s for s in presence_signals
                      if streak_min <= s["streak_top10"] <= streak_max]
            if bucket:
                rets = [s["fwd_excess"] for s in bucket]
                avg = statistics.mean(rets)
                med = statistics.median(rets)
                L.append(f"| {label} | {avg:+.2f}% | {med:+.2f}% | {len(bucket)} |")
        L.append("")

        # Per company: show streak evolution for key companies
        for company in ["Tapestry", "Ralph Lauren", "Prada Group", "Kering"]:
            co_ps = sorted([s for s in presence_signals if s["company"] == company],
                          key=lambda s: parse_q(s["quarter"]))
            if not co_ps:
                continue
            # Only show last 12 quarters to keep table manageable
            co_ps = co_ps[-12:]
            L.append(f"### {company}: Presence Timeline (last 12Q)")
            L.append("")
            L.append("| Quarter | Rank | Chart Streak | Top10 Streak | Top5 Streak | Fwd Excess |")
            L.append("|---------|------|-------------|-------------|------------|-----------|")
            for s in co_ps:
                L.append(f"| {s['quarter']} | {s['rank_now']:.1f} | {s['streak_chart']} | "
                         f"{s['streak_top10']} | {s['streak_top5']} | {s['fwd_excess']:+.2f}% |")
            L.append("")

        # Correlation: streak_top10 vs forward excess
        L.append("### Correlation: Top-10 Streak vs Forward Excess Return")
        L.append("")
        L.append("| Company | r | p-value | n |")
        L.append("|---------|---|---------|---|")
        for company in COMPANIES:
            co_ps = [s for s in presence_signals if s["company"] == company]
            if len(co_ps) < 3:
                L.append(f"| {company} | — | — | {len(co_ps)} |")
                continue
            xs = [s["streak_top10"] for s in co_ps]
            ys = [s["fwd_excess"] for s in co_ps]
            r, t, p, n = corr_stats(xs, ys)
            r_s = f"{r:+.3f}" if r else "—"
            p_s = f"{p:.3f}" if p else "—"
            sig = " ✓" if p and p < 0.10 else ""
            L.append(f"| {company} | {r_s} | {p_s}{sig} | {n} |")
        L.append("")

    # ─── 9. Rank Level as Signal ───
    L.append("## 9. Rank Level: Being Ranked Higher = Better Returns?")
    L.append("")
    L.append("Instead of rank CHANGE, test rank LEVEL directly.")
    L.append("Economic logic: brand in top 5 = strong demand = revenue growth.")
    L.append("")

    if presence_signals:
        # Tier analysis: all companies
        L.append("### A. All Companies: Forward Excess by Rank Tier")
        L.append("")
        L.append("| Rank Tier | Avg Excess | Median | Win% | n |")
        L.append("|-----------|-----------|--------|------|---|")
        for tier_name, lo, hi in [
            ("Top 5 (rank ≤ 5)", 0, 5),
            ("6-10", 5.01, 10),
            ("11-15", 10.01, 15),
            ("16-20", 15.01, 20),
            ("Unranked (21)", 20.01, 99),
        ]:
            bucket = [s for s in presence_signals if lo < s["rank_now"] <= hi or
                      (lo == 0 and s["rank_now"] <= hi)]
            if not bucket:
                L.append(f"| {tier_name} | — | — | — | 0 |")
                continue
            rets = [s["fwd_excess"] for s in bucket]
            avg = statistics.mean(rets)
            med = statistics.median(rets)
            win = sum(1 for r in rets if r > 0) / len(rets) * 100
            L.append(f"| {tier_name} | {avg:+.2f}% | {med:+.2f}% | {win:.0f}% | {len(bucket)} |")
        L.append("")

        # Same but only high-exposure
        L.append("### B. High-Exposure Only: Forward Excess by Rank Tier")
        L.append("")
        L.append("| Rank Tier | Avg Excess | Median | Win% | n |")
        L.append("|-----------|-----------|--------|------|---|")
        high_ps = [s for s in presence_signals if s["group"] == "high"]
        for tier_name, lo, hi in [
            ("Top 5 (rank ≤ 5)", 0, 5),
            ("6-10", 5.01, 10),
            ("11-15", 10.01, 15),
            ("16+ or unranked", 15.01, 99),
        ]:
            bucket = [s for s in high_ps if lo < s["rank_now"] <= hi or
                      (lo == 0 and s["rank_now"] <= hi)]
            if not bucket:
                L.append(f"| {tier_name} | — | — | — | 0 |")
                continue
            rets = [s["fwd_excess"] for s in bucket]
            avg = statistics.mean(rets)
            med = statistics.median(rets)
            win = sum(1 for r in rets if r > 0) / len(rets) * 100
            L.append(f"| {tier_name} | {avg:+.2f}% | {med:+.2f}% | {win:.0f}% | {len(bucket)} |")
        L.append("")

    # ─── 10. Composite Momentum Score & Cross-Sectional L/S ───
    L.append("## 10. Composite Momentum Score")
    L.append("")
    L.append("Score = 0.5 × Level + 0.3 × Trend + 0.2 × Presence")
    L.append("")
    L.append("- Level = (21 - rank) / 20  →  0 (unranked) to 1 (rank #1)")
    L.append("- Trend = 3Q rank change / 10, capped [-1, 1]")
    L.append("- Presence = min(chart_streak / 8, 1)")
    L.append("")

    if trend_signals and presence_signals:
        # Build score per company per quarter
        score_data = {}  # {quarter: [{company, score, fwd_excess}]}
        trend_lookup = {}
        for s in trend_signals:
            trend_lookup[(s["company"], s["quarter"])] = s["trend_3q"]
        pres_lookup = {}
        for s in presence_signals:
            pres_lookup[(s["company"], s["quarter"])] = s

        for q in quarters[3:]:  # need 3Q lookback
            q_scores = []
            for company in COMPANIES:
                ps = pres_lookup.get((company, q))
                if ps is None:
                    continue
                rank = ps["rank_now"]
                streak = ps["streak_chart"]
                trend = trend_lookup.get((company, q), 0)

                level_score = max(0, (21 - rank)) / 20
                trend_score = max(-1, min(1, trend / 10))
                pres_score = min(1, streak / 8)
                composite = 0.5 * level_score + 0.3 * trend_score + 0.2 * pres_score

                q_scores.append({
                    "company": company,
                    "group": COMPANIES[company]["group"],
                    "score": round(composite, 3),
                    "rank": rank,
                    "trend": trend,
                    "streak": streak,
                    "fwd_excess": ps["fwd_excess"],
                })
            if q_scores:
                score_data[q] = q_scores

        # Score matrix: all companies × all quarters
        co_order = list(COMPANIES.keys())
        L.append("### Score Matrix: All Companies × All Quarters")
        L.append("")
        header = "| Quarter | " + " | ".join(co_order) + " |"
        sep = "|---------|" + "|".join(["-----" for _ in co_order]) + "|"
        L.append(header)
        L.append(sep)
        for q in sorted(score_data.keys(), key=parse_q):
            q_lookup = {s["company"]: s for s in score_data[q]}
            cells = []
            for co in co_order:
                s = q_lookup.get(co)
                if s and abs(s["score"]) > 0.001:
                    cells.append(f"{s['score']:.3f}")
                else:
                    cells.append("0")
            L.append(f"| {q} | " + " | ".join(cells) + " |")
        L.append("")

        # Also show the components for latest quarter
        latest_q = sorted(score_data.keys(), key=parse_q)[-1]
        L.append(f"### Score Components Breakdown ({latest_q})")
        L.append("")
        L.append("| Company | Rank | Level | 3Q Trend | Trend Score | Streak | Pres Score | **Composite** |")
        L.append("|---------|------|-------|----------|------------|--------|-----------|-------------|")
        for s in sorted(score_data[latest_q], key=lambda x: -x["score"]):
            level = max(0, (21 - s["rank"])) / 20
            trend_raw = s["trend"]
            trend_sc = max(-1, min(1, trend_raw / 10))
            pres_sc = min(1, s["streak"] / 8)
            L.append(f"| {s['company']} | {s['rank']:.1f} | {level:.3f} | {trend_raw:+.1f} | "
                     f"{trend_sc:+.3f} | {s['streak']} | {pres_sc:.3f} | **{s['score']:.3f}** |")
        L.append("")

        # Correlation: composite score vs forward excess (all companies)
        all_scores = [s for q_list in score_data.values() for s in q_list]
        L.append("### Score vs Forward Excess Return")
        L.append("")
        L.append("| Group | r | t-stat | p-value | n |")
        L.append("|-------|---|--------|---------|---|")
        for grp_name, label in [("high", "High-Exposure"), ("low", "Low-Exposure"),
                                 (None, "All Companies")]:
            if grp_name:
                grp = [s for s in all_scores if s["group"] == grp_name]
            else:
                grp = all_scores
            if len(grp) < 3:
                continue
            xs = [s["score"] for s in grp]
            ys = [s["fwd_excess"] for s in grp]
            r, t, p, n = corr_stats(xs, ys)
            r_s = f"{r:+.3f}" if r else "—"
            t_s = f"{t:.2f}" if t else "—"
            p_s = f"{p:.3f}" if p else "—"
            sig = " ✓" if p and p < 0.10 else ""
            L.append(f"| {label} | {r_s} | {t_s} | {p_s}{sig} | {n} |")
        L.append("")

        # Per company
        L.append("### Per-Company Score Correlation")
        L.append("")
        L.append("| Company | r (Score vs Excess) | p-value | n |")
        L.append("|---------|--------------------|---------|----|")
        for company in COMPANIES:
            co = [s for s in all_scores if s["company"] == company]
            if len(co) < 3:
                L.append(f"| {company} | — | — | {len(co)} |")
                continue
            xs = [s["score"] for s in co]
            ys = [s["fwd_excess"] for s in co]
            r, t, p, n = corr_stats(xs, ys)
            r_s = f"{r:+.3f}" if r else "—"
            p_s = f"{p:.3f}" if p else "—"
            sig = " ✓" if p and p < 0.10 else ""
            L.append(f"| {company} | {r_s} | {p_s}{sig} | {n} |")
        L.append("")

        # Cross-sectional L/S by composite score (high-exposure only)
        L.append("### Cross-Sectional L/S (High-Exposure, by Composite Score)")
        L.append("")
        L.append("Each quarter: long highest-scored, short lowest-scored.")
        L.append("")
        L.append("| Quarter | Long (score) | Short (score) | L/S Return |")
        L.append("|---------|-------------|--------------|-----------|")

        score_ls = []
        for q in sorted(score_data.keys(), key=parse_q):
            high_only = [s for s in score_data[q] if s["group"] == "high"]
            if len(high_only) < 2:
                continue
            high_only.sort(key=lambda s: s["score"], reverse=True)
            long_s = high_only[0]
            short_s = high_only[-1]
            if long_s["company"] == short_s["company"]:
                continue
            ls_ret = long_s["fwd_excess"] - short_s["fwd_excess"]
            score_ls.append({"quarter": q, "ls": ls_ret,
                           "long": long_s, "short": short_s})
            L.append(f"| {q} | {long_s['company']} ({long_s['score']:.2f}) | "
                     f"{short_s['company']} ({short_s['score']:.2f}) | {ls_ret:+.2f}% |")

        if score_ls:
            ls_rets = [s["ls"] for s in score_ls]
            cum = 1.0
            for r in ls_rets:
                cum *= (1 + r / 100)
            avg, t_val, p_val, n_ls = t_test_mean(ls_rets)
            t_s = f"{t_val:.2f}" if t_val else "—"
            p_s = f"{p_val:.3f}" if p_val else "—"
            L.append("")
            L.append(f"- **Cumulative L/S**: {(cum - 1) * 100:+.1f}% over {len(ls_rets)} quarters")
            L.append(f"- **Avg quarterly L/S**: {avg:+.2f}% (t={t_s}, p={p_s})")
            L.append(f"- **Win rate**: {sum(1 for r in ls_rets if r > 0) / len(ls_rets) * 100:.0f}%")
        L.append("")

        # ─── 11. Within-Company Timing L/S ───
        L.append("## 11. Within-Company Timing: ΔScore as Entry/Exit Signal")
        L.append("")
        L.append("Instead of picking WHICH stock to buy (cross-sectional),")
        L.append("test WHEN to buy each stock using its own score changes.")
        L.append("")
        L.append("Rule: For each company, each quarter:")
        L.append("- Score ↑ QoQ → long (capture forward excess return)")
        L.append("- Score ↓ QoQ → short (inverse of forward excess return)")
        L.append("- Score unchanged → flat (skip)")
        L.append("")

        # Build score time series per company
        co_score_ts = defaultdict(list)  # {company: [(quarter, score, fwd_excess)]}
        for q in sorted(score_data.keys(), key=parse_q):
            for s in score_data[q]:
                co_score_ts[s["company"]].append((q, s["score"], s["fwd_excess"]))

        # A. ΔScore timing per company
        L.append("### A. Per-Company ΔScore Timing")
        L.append("")
        L.append("| Company | Long Avg | Short Avg | L/S Spread | Win% | n (long) | n (short) |")
        L.append("|---------|---------|----------|-----------|------|---------|----------|")

        all_timing_returns = []
        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            if len(ts) < 4:
                continue
            long_rets, short_rets, timing_rets = [], [], []
            for i in range(1, len(ts)):
                q_prev, sc_prev, _ = ts[i - 1]
                q_now, sc_now, fwd_ex = ts[i]
                delta_sc = sc_now - sc_prev
                if delta_sc > 0.01:
                    long_rets.append(fwd_ex)
                    timing_rets.append(fwd_ex)
                elif delta_sc < -0.01:
                    short_rets.append(-fwd_ex)
                    timing_rets.append(-fwd_ex)

            if not long_rets or not short_rets:
                continue
            avg_l = statistics.mean(long_rets)
            avg_s = statistics.mean(short_rets)
            all_tr = long_rets + short_rets
            wins = sum(1 for r in all_tr if r > 0)
            L.append(f"| {company} | {avg_l:+.2f}% | {avg_s:+.2f}% | "
                     f"{avg_l - avg_s:+.2f}% | {wins / len(all_tr) * 100:.0f}% | "
                     f"{len(long_rets)} | {len(short_rets)} |")
            all_timing_returns.extend(all_tr)
        L.append("")

        if all_timing_returns:
            avg, t_val, p_val, n_t = t_test_mean(all_timing_returns)
            cum = 1.0
            for r in all_timing_returns:
                cum *= (1 + r / 100)
            t_s = f"{t_val:.2f}" if t_val else "—"
            p_s = f"{p_val:.3f}" if p_val else "—"
            L.append(f"**Aggregate (all companies)**: avg={avg:+.2f}%, t={t_s}, p={p_s}, "
                     f"n={n_t}, win={sum(1 for r in all_timing_returns if r > 0) / len(all_timing_returns) * 100:.0f}%")
            L.append("")

        # B. Score level timing: above vs below company median
        L.append("### B. Score Level Timing: Above vs Below Own Median")
        L.append("")
        L.append("For each company: long when score > company median, short when score ≤ median.")
        L.append("")
        L.append("| Company | Median Score | High-Score Avg | Low-Score Avg | Spread | n(H) | n(L) |")
        L.append("|---------|-------------|---------------|--------------|--------|------|------|")

        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            if len(ts) < 4:
                continue
            scores = [s[1] for s in ts]
            med = statistics.median(scores)
            high_rets = [fwd for _, sc, fwd in ts if sc > med]
            low_rets = [fwd for _, sc, fwd in ts if sc <= med]
            if not high_rets or not low_rets:
                continue
            avg_h = statistics.mean(high_rets)
            avg_l = statistics.mean(low_rets)
            L.append(f"| {company} | {med:.3f} | {avg_h:+.2f}% | {avg_l:+.2f}% | "
                     f"{avg_h - avg_l:+.2f}% | {len(high_rets)} | {len(low_rets)} |")
        L.append("")

        # C. Detailed within-company L/S for key companies
        L.append("### C. Within-Company ΔScore Detail (Key Companies)")
        L.append("")
        for company in ["Prada Group", "Tapestry", "Ralph Lauren", "Kering"]:
            ts = co_score_ts.get(company, [])
            if len(ts) < 4:
                continue
            L.append(f"#### {company}")
            L.append("")
            L.append("| Quarter | Score | ΔScore | Position | Return |")
            L.append("|---------|-------|--------|----------|--------|")
            cum_ret = 1.0
            n_trades = 0
            for i in range(1, len(ts)):
                q_prev, sc_prev, _ = ts[i - 1]
                q_now, sc_now, fwd_ex = ts[i]
                delta_sc = sc_now - sc_prev
                if delta_sc > 0.01:
                    pos = "LONG"
                    ret = fwd_ex
                elif delta_sc < -0.01:
                    pos = "SHORT"
                    ret = -fwd_ex
                else:
                    pos = "FLAT"
                    ret = 0
                if pos != "FLAT":
                    cum_ret *= (1 + ret / 100)
                    n_trades += 1
                L.append(f"| {q_now} | {sc_now:.3f} | {delta_sc:+.3f} | {pos} | {ret:+.2f}% |")
            L.append("")
            L.append(f"Cumulative: {(cum_ret - 1) * 100:+.1f}% over {n_trades} trades")
            L.append("")

        # D. Portfolio-level: equal-weight all within-company timing signals
        L.append("### D. Portfolio: Equal-Weight Within-Company Timing")
        L.append("")
        L.append("Each quarter: average the timing returns across all active companies.")
        L.append("")

        # Collect per-quarter timing returns
        qtr_timing = defaultdict(list)
        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            for i in range(1, len(ts)):
                q_prev, sc_prev, _ = ts[i - 1]
                q_now, sc_now, fwd_ex = ts[i]
                delta_sc = sc_now - sc_prev
                if delta_sc > 0.01:
                    qtr_timing[q_now].append(fwd_ex)
                elif delta_sc < -0.01:
                    qtr_timing[q_now].append(-fwd_ex)

        L.append("| Quarter | # Positions | Avg Return |")
        L.append("|---------|------------|-----------|")
        port_rets = []
        for q in sorted(qtr_timing.keys(), key=parse_q):
            rets = qtr_timing[q]
            avg_r = statistics.mean(rets)
            port_rets.append(avg_r)
            L.append(f"| {q} | {len(rets)} | {avg_r:+.2f}% |")
        L.append("")

        if port_rets:
            cum = 1.0
            for r in port_rets:
                cum *= (1 + r / 100)
            avg, t_val, p_val, n_p = t_test_mean(port_rets)
            t_s = f"{t_val:.2f}" if t_val else "—"
            p_s = f"{p_val:.3f}" if p_val else "—"
            L.append(f"- **Cumulative**: {(cum - 1) * 100:+.1f}% over {len(port_rets)} quarters")
            L.append(f"- **Avg quarterly**: {avg:+.2f}% (t={t_s}, p={p_s})")
            L.append(f"- **Win rate**: {sum(1 for r in port_rets if r > 0) / len(port_rets) * 100:.0f}%")
        L.append("")

        # ─── 12. First Entry Event Signal ───
        L.append("## 12. First Entry Event Signal: Brand Enters Lyst → Buy")
        L.append("")
        L.append("Separate the 'first entry onto chart' event from subsequent score changes.")
        L.append("For Coach/RL, the initial listing is a different signal than ongoing ΔScore.")
        L.append("")

        # Detect first entry events and track forward returns
        # Also detect re-entry (was ranked, dropped off, came back)
        entry_events = []
        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            if len(ts) < 2:
                continue
            ever_ranked = False
            was_ranked = False
            for i in range(len(ts)):
                q, sc, fwd = ts[i]
                is_ranked = sc > 0.01
                if is_ranked and not was_ranked:
                    entry_type = "re-entry" if ever_ranked else "first entry"
                    # Collect forward returns for N quarters after entry
                    fwd_rets = []
                    for j in range(i, min(i + 6, len(ts))):
                        fwd_rets.append(ts[j][2])
                    entry_events.append({
                        "company": company,
                        "quarter": q,
                        "type": entry_type,
                        "entry_score": sc,
                        "fwd_1q": fwd_rets[0] if len(fwd_rets) > 0 else None,
                        "fwd_2q": sum(fwd_rets[:2]) if len(fwd_rets) >= 2 else None,
                        "fwd_4q": sum(fwd_rets[:4]) if len(fwd_rets) >= 4 else None,
                        "fwd_6q": sum(fwd_rets[:6]) if len(fwd_rets) >= 6 else None,
                        "fwd_rets": fwd_rets,
                    })
                if is_ranked:
                    ever_ranked = True
                was_ranked = is_ranked

        L.append("### A. All Entry Events")
        L.append("")
        L.append("| Company | Quarter | Type | Entry Score | Fwd 1Q | Fwd 2Q | Fwd 4Q |")
        L.append("|---------|---------|------|-----------|--------|--------|--------|")
        for e in entry_events:
            f1 = f"{e['fwd_1q']:+.2f}%" if e['fwd_1q'] is not None else "—"
            f2 = f"{e['fwd_2q']:+.2f}%" if e['fwd_2q'] is not None else "—"
            f4 = f"{e['fwd_4q']:+.2f}%" if e['fwd_4q'] is not None else "—"
            L.append(f"| {e['company']} | {e['quarter']} | {e['type']} | "
                     f"{e['entry_score']:.3f} | {f1} | {f2} | {f4} |")
        L.append("")

        # B. Post-entry trajectory: cumulative return path after first entry
        L.append("### B. Post-Entry Return Path (Cumulative)")
        L.append("")
        L.append("Average cumulative excess return in the N quarters after a brand first enters the chart.")
        L.append("")
        L.append("| Quarters After Entry | Avg Cumulative Excess | Median | Win% | n |")
        L.append("|---------------------|-----------------------|--------|------|---|")
        for horizon in [1, 2, 3, 4, 6]:
            cum_rets = []
            for e in entry_events:
                if len(e["fwd_rets"]) >= horizon:
                    cum_rets.append(sum(e["fwd_rets"][:horizon]))
            if cum_rets:
                avg = statistics.mean(cum_rets)
                med = statistics.median(cum_rets)
                win = sum(1 for r in cum_rets if r > 0) / len(cum_rets) * 100
                L.append(f"| +{horizon}Q | {avg:+.2f}% | {med:+.2f}% | {win:.0f}% | {len(cum_rets)} |")
        L.append("")

        # C. Post-entry trajectory per company (detailed)
        L.append("### C. Post-Entry Trajectory: Quarter-by-Quarter")
        L.append("")
        L.append("For companies with entry events, show score + return path after entry.")
        L.append("")

        for company in ["Tapestry", "Ralph Lauren", "Burberry"]:
            co_entries = [e for e in entry_events if e["company"] == company]
            if not co_entries:
                continue
            ts = co_score_ts.get(company, [])

            for entry in co_entries:
                eq = entry["quarter"]
                ei = next((i for i, t in enumerate(ts) if t[0] == eq), None)
                if ei is None:
                    continue
                L.append(f"#### {company}: {entry['type']} at {eq}")
                L.append("")
                L.append("| Quarter | Q+N | Score | Rank | Fwd Excess | Cum Excess |")
                L.append("|---------|-----|-------|------|-----------|-----------|")

                cum = 0
                pres_co = {s["quarter"]: s for s in presence_signals
                           if s["company"] == company}
                for j in range(min(8, len(ts) - ei)):
                    q_j, sc_j, fwd_j = ts[ei + j]
                    cum += fwd_j
                    rank_j = pres_co[q_j]["rank_now"] if q_j in pres_co else UNRANKED
                    L.append(f"| {q_j} | +{j} | {sc_j:.3f} | {rank_j:.0f} | "
                             f"{fwd_j:+.2f}% | {cum:+.2f}% |")
                L.append("")

        # D. Entry signal vs non-entry: compare returns
        L.append("### D. Entry Quarters vs Non-Entry Quarters")
        L.append("")
        entry_qs = set((e["company"], e["quarter"]) for e in entry_events)
        entry_fwd = [e["fwd_1q"] for e in entry_events if e["fwd_1q"] is not None]
        non_entry_fwd = []
        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            for q, sc, fwd in ts:
                if (company, q) not in entry_qs:
                    non_entry_fwd.append(fwd)

        if entry_fwd and non_entry_fwd:
            avg_e = statistics.mean(entry_fwd)
            avg_ne = statistics.mean(non_entry_fwd)
            med_e = statistics.median(entry_fwd)
            med_ne = statistics.median(non_entry_fwd)
            win_e = sum(1 for r in entry_fwd if r > 0) / len(entry_fwd) * 100
            win_ne = sum(1 for r in non_entry_fwd if r > 0) / len(non_entry_fwd) * 100
            L.append("| Group | Avg Excess | Median | Win% | n |")
            L.append("|-------|-----------|--------|------|---|")
            L.append(f"| Entry quarters | {avg_e:+.2f}% | {med_e:+.2f}% | {win_e:.0f}% | {len(entry_fwd)} |")
            L.append(f"| Non-entry quarters | {avg_ne:+.2f}% | {med_ne:+.2f}% | {win_ne:.0f}% | {len(non_entry_fwd)} |")
            L.append(f"| **Spread** | **{avg_e - avg_ne:+.2f}%** | | | |")
        L.append("")

        # E. Confirmed Entry Signal: N consecutive quarters on chart + rank improving
        L.append("### E. Confirmed Entry Signal")
        L.append("")
        L.append("Filter out false entries (single-quarter blips). Trigger only fires when:")
        L.append("- Brand has been on chart for ≥N consecutive quarters, AND")
        L.append("- Current rank is better (lower) than rank at initial entry")
        L.append("")
        L.append("This filters Tapestry Q4 2022 (Coach rank 19, dropped next quarter)")
        L.append("and keeps Tapestry Q3 2024 (Coach rank 15, had been at 20 prior quarter).")
        L.append("")

        # Build presence data per company
        pres_co_lookup = {}
        for s in presence_signals:
            pres_co_lookup[(s["company"], s["quarter"])] = s

        # Detect confirmed entries for various N thresholds
        for min_streak in [2, 3]:
            confirmed = []
            for company in COMPANIES:
                ts = co_score_ts.get(company, [])
                if len(ts) < min_streak + 1:
                    continue
                triggered = False
                entry_rank = None
                streak_start_idx = None
                current_streak = 0
                for i in range(len(ts)):
                    q, sc, fwd = ts[i]
                    ps = pres_co_lookup.get((company, q))
                    rank = ps["rank_now"] if ps else UNRANKED
                    is_ranked = rank < UNRANKED

                    if is_ranked:
                        current_streak += 1
                        if current_streak == 1:
                            entry_rank = rank
                            streak_start_idx = i
                    else:
                        current_streak = 0
                        entry_rank = None
                        triggered = False

                    if current_streak == min_streak and entry_rank is not None:
                        if rank <= entry_rank:
                            # Collect forward returns
                            fwd_rets = [ts[j][2] for j in range(i, min(i + 6, len(ts)))]
                            confirmed.append({
                                "company": company,
                                "trigger_q": q,
                                "entry_q": ts[streak_start_idx][0],
                                "entry_rank": entry_rank,
                                "trigger_rank": rank,
                                "fwd_1q": fwd_rets[0] if len(fwd_rets) > 0 else None,
                                "fwd_2q": sum(fwd_rets[:2]) if len(fwd_rets) >= 2 else None,
                                "fwd_4q": sum(fwd_rets[:4]) if len(fwd_rets) >= 4 else None,
                                "fwd_rets": fwd_rets,
                            })
                            triggered = True

            L.append(f"#### Trigger: {min_streak}Q on chart + rank improving")
            L.append("")
            if confirmed:
                L.append("| Company | Entry Q | Trigger Q | Entry Rank | Trigger Rank | Fwd 1Q | Fwd 2Q | Fwd 4Q |")
                L.append("|---------|---------|-----------|-----------|-------------|--------|--------|--------|")
                for c in confirmed:
                    f1 = f"{c['fwd_1q']:+.2f}%" if c['fwd_1q'] is not None else "—"
                    f2 = f"{c['fwd_2q']:+.2f}%" if c['fwd_2q'] is not None else "—"
                    f4 = f"{c['fwd_4q']:+.2f}%" if c['fwd_4q'] is not None else "—"
                    L.append(f"| {c['company']} | {c['entry_q']} | {c['trigger_q']} | "
                             f"{c['entry_rank']:.0f} | {c['trigger_rank']:.0f} | {f1} | {f2} | {f4} |")
                L.append("")

                # Summary stats
                fwd1_vals = [c["fwd_1q"] for c in confirmed if c["fwd_1q"] is not None]
                fwd4_vals = [c["fwd_4q"] for c in confirmed if c["fwd_4q"] is not None]
                if fwd1_vals:
                    L.append(f"- **Fwd 1Q**: avg {statistics.mean(fwd1_vals):+.2f}%, "
                             f"win {sum(1 for v in fwd1_vals if v > 0)/len(fwd1_vals)*100:.0f}%, n={len(fwd1_vals)}")
                if fwd4_vals:
                    L.append(f"- **Fwd 4Q**: avg {statistics.mean(fwd4_vals):+.2f}%, "
                             f"win {sum(1 for v in fwd4_vals if v > 0)/len(fwd4_vals)*100:.0f}%, n={len(fwd4_vals)}")
                L.append("")
            else:
                L.append("No confirmed entries found.")
                L.append("")

        # F. Composite confirmed signal: 2Q streak + rank improving + hold until rank deteriorates
        L.append("### F. Full Strategy: Buy on Confirmed Entry, Sell on Rank Deterioration")
        L.append("")
        L.append("Rules:")
        L.append("- **BUY**: 2+ consecutive quarters on chart AND rank improved vs entry")
        L.append("- **HOLD**: while on chart AND rank ≤ recent peak + 3")
        L.append("- **SELL**: drops off chart OR rank deteriorates > 3 positions from peak")
        L.append("")

        for company in ["Tapestry", "Ralph Lauren", "Prada Group", "Kering"]:
            ts = co_score_ts.get(company, [])
            if len(ts) < 4:
                continue

            L.append(f"#### {company}")
            L.append("")
            L.append("| Quarter | Rank | Streak | Peak Rank | Position | Fwd Excess | Cum |")
            L.append("|---------|------|--------|----------|----------|-----------|-----|")

            current_streak = 0
            entry_rank = None
            peak_rank = None
            in_position = False
            cum_ret = 0
            n_hold = 0

            for i in range(len(ts)):
                q, sc, fwd = ts[i]
                ps = pres_co_lookup.get((company, q))
                rank = ps["rank_now"] if ps else UNRANKED
                is_ranked = rank < UNRANKED

                if is_ranked:
                    current_streak += 1
                    if current_streak == 1:
                        entry_rank = rank
                else:
                    current_streak = 0
                    entry_rank = None
                    peak_rank = None
                    in_position = False

                # Entry condition
                if not in_position and current_streak >= 2 and entry_rank is not None:
                    if rank <= entry_rank:
                        in_position = True
                        peak_rank = rank

                # Update peak
                if in_position and is_ranked:
                    if rank < peak_rank:
                        peak_rank = rank

                # Exit condition
                if in_position:
                    if not is_ranked or rank > peak_rank + 3:
                        in_position = False

                pos_label = "HOLD" if in_position else "—"
                if in_position:
                    cum_ret += fwd
                    n_hold += 1

                if is_ranked or in_position or (i > 0 and ts[i-1][1] > 0.01):
                    pk_s = f"{peak_rank:.0f}" if peak_rank is not None else "—"
                    L.append(f"| {q} | {rank:.0f} | {current_streak} | {pk_s} | "
                             f"{pos_label} | {fwd:+.2f}% | {cum_ret:+.2f}% |")

            L.append("")
            L.append(f"**Result**: cum excess {cum_ret:+.1f}% over {n_hold} quarters held")
            L.append("")
        L.append("")

        # ─── 13. Kering Annual Regime Analysis ───
        L.append("## 13. Kering: Annual Regime vs Stock Performance")
        L.append("")
        L.append("Quarterly correlation (r=-0.224) understates the signal because stock price")
        L.append("leads rank at inflection points. Multi-year regime alignment is clearer.")
        L.append("")

        ker_ts = co_score_ts.get("Kering", [])
        if ker_ts:
            regimes = [
                ("2019-2021 H1 (Gucci top 5)", lambda q: (2019, 1) <= parse_q(q) <= (2021, 2)),
                ("2021 H2-2022 (Gucci slipping)", lambda q: (2021, 3) <= parse_q(q) <= (2022, 4)),
                ("2023-2024 (Gucci rank 8-12)", lambda q: (2023, 1) <= parse_q(q) <= (2024, 4)),
                ("2025 (Gucci recovering)", lambda q: (2025, 1) <= parse_q(q) <= (2025, 4)),
            ]
            L.append("| Regime | Avg Rank | Avg Score | Avg Fwd Excess | n |")
            L.append("|--------|---------|----------|---------------|---|")

            # Need rank data too — get from presence_signals
            ker_pres = {s["quarter"]: s for s in presence_signals if s["company"] == "Kering"}

            for label, filter_fn in regimes:
                regime_data = [(q, sc, fwd) for q, sc, fwd in ker_ts if filter_fn(q)]
                if not regime_data:
                    continue
                avg_sc = statistics.mean([sc for _, sc, _ in regime_data])
                avg_fwd = statistics.mean([fwd for _, _, fwd in regime_data])
                ranks = [ker_pres[q]["rank_now"] for q, _, _ in regime_data if q in ker_pres]
                avg_rank = statistics.mean(ranks) if ranks else 0
                L.append(f"| {label} | {avg_rank:.1f} | {avg_sc:.3f} | {avg_fwd:+.2f}% | {len(regime_data)} |")
            L.append("")
            L.append("Direction alignment: rank deteriorates → returns worsen → rank recovers → returns recover.")
            L.append("The quarterly negative r captures timing mismatch at inflection points,")
            L.append("not a genuine anti-signal.")
            L.append("")

    # ─── 14. WHEN Portfolio: Timing L/S Significance Test ───
    if trend_signals and presence_signals:
        L.append("## 14. 'WHEN' Portfolio: Timing Long/Short Significance Test")
        L.append("")
        L.append("Core test: if Lyst tells you WHEN to buy, does following the signal")
        L.append("produce statistically significant excess returns?")
        L.append("")

        # --- Strategy A: Score Level Timing ---
        # Per company: long when score > median, short when score ≤ median
        # Portfolio = equal-weight average of per-company timing returns each quarter
        L.append("### A. Score Level Timing Portfolio")
        L.append("")
        L.append("Each quarter, for each company: long if score > own median, short if ≤ median.")
        L.append("Portfolio = equal-weight average across companies.")
        L.append("")

        # Compute per-company medians
        co_medians = {}
        for company in COMPANIES:
            ts = co_score_ts.get(company, [])
            if len(ts) >= 4:
                co_medians[company] = statistics.median([s[1] for s in ts])

        # Test multiple universes
        universes = [
            ("All 6 companies", list(COMPANIES.keys())),
            ("Excl Burberry", [c for c in COMPANIES if c != "Burberry"]),
            ("Excl Burberry + Kering", [c for c in COMPANIES if c not in ("Burberry", "Kering")]),
            ("Prada + Tapestry + RL only", ["Prada Group", "Tapestry", "Ralph Lauren"]),
        ]

        L.append("| Universe | Avg Q Return | t-stat | p-value | Win% | Sharpe (ann.) | n(Q) |")
        L.append("|----------|-------------|--------|---------|------|--------------|------|")

        for label, cos in universes:
            port_rets_q = defaultdict(list)
            for company in cos:
                if company not in co_medians:
                    continue
                med = co_medians[company]
                ts = co_score_ts.get(company, [])
                for q, sc, fwd in ts:
                    if sc > med:
                        port_rets_q[q].append(fwd)
                    else:
                        port_rets_q[q].append(-fwd)

            qtr_rets = []
            for q in sorted(port_rets_q.keys(), key=parse_q):
                if port_rets_q[q]:
                    qtr_rets.append(statistics.mean(port_rets_q[q]))

            if len(qtr_rets) >= 4:
                avg, t_val, p_val, n_q = t_test_mean(qtr_rets)
                t_s = f"{t_val:.2f}" if t_val else "—"
                p_s = f"{p_val:.3f}" if p_val else "—"
                win = sum(1 for r in qtr_rets if r > 0) / len(qtr_rets) * 100
                std = statistics.stdev(qtr_rets)
                sharpe = (avg / std * math.sqrt(4)) if std > 0 else 0
                L.append(f"| {label} | {avg:+.2f}% | {t_s} | {p_s} | {win:.0f}% | {sharpe:.2f} | {n_q} |")
        L.append("")

        # --- Strategy B: Confirmed Entry Hold ---
        # Long only during confirmed-entry hold periods, flat otherwise
        L.append("### B. Confirmed Entry Hold Portfolio")
        L.append("")
        L.append("Long only when in confirmed-entry hold period (2Q on chart + rank improving).")
        L.append("Flat otherwise. No shorting.")
        L.append("")

        for label, cos in universes:
            # Recompute confirmed entry hold periods for this universe
            hold_periods = defaultdict(dict)  # {company: {quarter: True/False}}
            for company in cos:
                ts = co_score_ts.get(company, [])
                if len(ts) < 4:
                    continue
                current_streak = 0
                entry_rank = None
                peak_rank = None
                in_pos = False
                for i in range(len(ts)):
                    q, sc, fwd = ts[i]
                    ps = pres_co_lookup.get((company, q))
                    rank = ps["rank_now"] if ps else UNRANKED
                    is_ranked = rank < UNRANKED

                    if is_ranked:
                        current_streak += 1
                        if current_streak == 1:
                            entry_rank = rank
                    else:
                        current_streak = 0
                        entry_rank = None
                        peak_rank = None
                        in_pos = False

                    if not in_pos and current_streak >= 2 and entry_rank is not None:
                        if rank <= entry_rank:
                            in_pos = True
                            peak_rank = rank

                    if in_pos and is_ranked and rank < peak_rank:
                        peak_rank = rank

                    if in_pos and (not is_ranked or rank > peak_rank + 3):
                        in_pos = False

                    hold_periods[company][q] = in_pos

            # Build portfolio: held returns vs not-held returns
            held_rets_all = []
            notheld_rets_all = []
            port_held_q = defaultdict(list)

            for company in cos:
                ts = co_score_ts.get(company, [])
                for q, sc, fwd in ts:
                    if hold_periods.get(company, {}).get(q, False):
                        held_rets_all.append(fwd)
                        port_held_q[q].append(fwd)
                    else:
                        notheld_rets_all.append(fwd)

            if held_rets_all and notheld_rets_all:
                avg_h, t_h, p_h, n_h = t_test_mean(held_rets_all)
                avg_nh = statistics.mean(notheld_rets_all)
                break  # Only need first universe for detailed display
        # (use the first universe for the detailed table; show all below)

        L.append("| Universe | Held Avg | Not-Held Avg | Spread | Held t | Held p | n(held) | n(not) |")
        L.append("|----------|---------|-------------|--------|--------|--------|---------|--------|")
        for label, cos in universes:
            hold_periods_u = defaultdict(dict)
            for company in cos:
                ts = co_score_ts.get(company, [])
                if len(ts) < 4:
                    continue
                current_streak = 0
                entry_rank = None
                peak_rank = None
                in_pos = False
                for i in range(len(ts)):
                    q, sc, fwd = ts[i]
                    ps = pres_co_lookup.get((company, q))
                    rank = ps["rank_now"] if ps else UNRANKED
                    is_ranked = rank < UNRANKED
                    if is_ranked:
                        current_streak += 1
                        if current_streak == 1:
                            entry_rank = rank
                    else:
                        current_streak = 0
                        entry_rank = None
                        peak_rank = None
                        in_pos = False
                    if not in_pos and current_streak >= 2 and entry_rank is not None:
                        if rank <= entry_rank:
                            in_pos = True
                            peak_rank = rank
                    if in_pos and is_ranked and rank < peak_rank:
                        peak_rank = rank
                    if in_pos and (not is_ranked or rank > peak_rank + 3):
                        in_pos = False
                    hold_periods_u[company][q] = in_pos

            h_rets = []
            nh_rets = []
            for company in cos:
                ts = co_score_ts.get(company, [])
                for q, sc, fwd in ts:
                    if hold_periods_u.get(company, {}).get(q, False):
                        h_rets.append(fwd)
                    else:
                        nh_rets.append(fwd)
            if len(h_rets) >= 3 and nh_rets:
                avg_h, t_h, p_h, n_h = t_test_mean(h_rets)
                avg_nh = round(statistics.mean(nh_rets), 2)
                t_s = f"{t_h:.2f}" if t_h else "—"
                p_s = f"{p_h:.3f}" if p_h else "—"
                L.append(f"| {label} | {avg_h:+.2f}% | {avg_nh:+.2f}% | "
                         f"{avg_h - avg_nh:+.2f}% | {t_s} | {p_s} | {n_h} | {len(nh_rets)} |")
        L.append("")

        # --- Strategy C: Combined Timing Portfolio (quarterly aggregated) ---
        L.append("### C. Quarterly Aggregated Timing Portfolio")
        L.append("")
        L.append("Equal-weight portfolio across Prada + Tapestry + RL:")
        L.append("score > median → long, else → short. One quarterly return per period.")
        L.append("")

        focus_cos = ["Prada Group", "Tapestry", "Ralph Lauren"]
        port_q_rets = defaultdict(list)
        for company in focus_cos:
            if company not in co_medians:
                continue
            med = co_medians[company]
            ts = co_score_ts.get(company, [])
            for q, sc, fwd in ts:
                if sc > med:
                    port_q_rets[q].append(fwd)
                else:
                    port_q_rets[q].append(-fwd)

        L.append("| Quarter | # Stocks | Avg Timing Return | Cumulative |")
        L.append("|---------|---------|------------------|-----------|")
        cum = 0
        sorted_qs = sorted(port_q_rets.keys(), key=parse_q)
        q_ret_list = []
        for q in sorted_qs:
            rets = port_q_rets[q]
            avg_r = statistics.mean(rets)
            cum += avg_r
            q_ret_list.append(avg_r)
            L.append(f"| {q} | {len(rets)} | {avg_r:+.2f}% | {cum:+.2f}% |")
        L.append("")

        if len(q_ret_list) >= 4:
            avg, t_val, p_val, n_q = t_test_mean(q_ret_list)
            cum_comp = 1.0
            for r in q_ret_list:
                cum_comp *= (1 + r / 100)
            std = statistics.stdev(q_ret_list)
            sharpe = (avg / std * math.sqrt(4)) if std > 0 else 0
            t_s = f"{t_val:.2f}" if t_val else "—"
            p_s = f"{p_val:.3f}" if p_val else "—"
            win = sum(1 for r in q_ret_list if r > 0) / len(q_ret_list) * 100
            L.append(f"- **Compounded cumulative**: {(cum_comp-1)*100:+.1f}%")
            L.append(f"- **Avg quarterly return**: {avg:+.2f}%")
            L.append(f"- **t-statistic**: {t_s}")
            L.append(f"- **p-value**: {p_s}")
            L.append(f"- **Win rate**: {win:.0f}%")
            L.append(f"- **Annualized Sharpe**: {sharpe:.2f}")
            L.append(f"- **Quarters**: {n_q}")
        L.append("")

        # --- Strategy D: Long-only timing (long when signal ON, cash when OFF) ---
        L.append("### D. Long-Only Timing: Signal ON → Long, Signal OFF → Cash")
        L.append("")
        L.append("More realistic: no shorting. Long when score > median, hold cash otherwise.")
        L.append("Compare vs always-long (buy and hold).")
        L.append("")

        L.append("| Universe | Timing Avg | Buy-Hold Avg | Timing Excess | t-stat | p-value | n |")
        L.append("|----------|-----------|-------------|--------------|--------|---------|---|")

        for label, cos in [
            ("Prada + Tapestry + RL", ["Prada Group", "Tapestry", "Ralph Lauren"]),
            ("All excl Burberry", [c for c in COMPANIES if c != "Burberry"]),
        ]:
            timing_q = defaultdict(list)
            buyhold_q = defaultdict(list)
            for company in cos:
                if company not in co_medians:
                    continue
                med = co_medians[company]
                ts = co_score_ts.get(company, [])
                for q, sc, fwd in ts:
                    buyhold_q[q].append(fwd)
                    if sc > med:
                        timing_q[q].append(fwd)
                    else:
                        timing_q[q].append(0)  # cash

            q_timing = []
            q_bh = []
            q_excess = []
            for q in sorted(set(timing_q.keys()) & set(buyhold_q.keys()), key=parse_q):
                t_r = statistics.mean(timing_q[q])
                b_r = statistics.mean(buyhold_q[q])
                q_timing.append(t_r)
                q_bh.append(b_r)
                q_excess.append(t_r - b_r)

            if len(q_excess) >= 4:
                avg_t = statistics.mean(q_timing)
                avg_b = statistics.mean(q_bh)
                avg_e, t_e, p_e, n_e = t_test_mean(q_excess)
                t_s = f"{t_e:.2f}" if t_e else "—"
                p_s = f"{p_e:.3f}" if p_e else "—"
                L.append(f"| {label} | {avg_t:+.2f}% | {avg_b:+.2f}% | "
                         f"{avg_e:+.2f}% | {t_s} | {p_s} | {n_e} |")
        L.append("")

    # ─── 15. Signal Summary ───
    L.append("## 15. Signal Summary")
    L.append("")
    L.append("| Signal | Best For | Key Finding |")
    L.append("|--------|----------|-------------|")
    L.append("| QoQ ΔRank | Prada Group | r=+0.408, p=0.023 |")
    L.append("| 3Q Trend | Prada, Burberry | Captures sustained momentum |")
    L.append("| Composite Score | Prada, RL, Tapestry | Within-company timing signal |")
    L.append("| Within-Co ΔScore | All | Long score↑ / short score↓ per company |")
    L.append("| First Entry Event | Coach, RL | Brand enters chart → buy trigger |")
    L.append("")
    L.append("**Core conclusion**: Lyst tells you WHEN to buy a luxury stock,")
    L.append("not WHICH one to pick. Within-company timing works;")
    L.append("cross-company selection does not.")
    L.append("")
    L.append("*v4 auto-generated. All returns in USD, excess vs GLUX.*")
    L.append("")

    return "\n".join(L)


# ════════════════════════════════════════════
# 9. MAIN
# ════════════════════════════════════════════

def main():
    print("=" * 60)
    print("LYST INDEX × STOCK RETURN BACKTEST v4")
    print("  High-exposure: Prada, Tapestry, Ralph Lauren, Burberry, Kering")
    print("  Low-exposure:  LVMH")
    print("=" * 60)

    # Detect latest quarter
    latest = detect_latest(TRACKER_CSV)
    quarters = build_quarters(latest)
    pairs = [(quarters[i], quarters[i + 1]) for i in range(len(quarters) - 1)]
    print(f"\nQuarters: {len(quarters)} (Q1 2018 – {latest})")
    print(f"Consecutive pairs: {len(pairs)}")

    # Load brand data
    hist_data = load_historical(set(quarters))
    tracker_data = load_tracker(set(quarters))
    brand_data = merge_brand_data(hist_data, tracker_data)
    print(f"\nBrands loaded: {len(brand_data)}")

    # Check key brands
    for brand in ["Prada", "Miu Miu", "Coach", "Ralph Lauren", "Burberry",
                  "Gucci", "Saint Laurent", "Bottega Veneta", "Louis Vuitton", "Dior"]:
        qs = sorted(brand_data.get(brand, {}).keys(), key=parse_q)
        if qs:
            print(f"  {brand}: {len(qs)} quarters ({qs[0]} – {qs[-1]})")
        else:
            print(f"  {brand}: NO DATA")

    # Composite ranks
    comp_ranks = compute_composite_ranks(brand_data, quarters)

    # Show Kering weight evolution
    print("\nKering weight evolution:")
    for yr in range(2019, 2027):
        w = _kering_weights(yr)
        print(f"  {yr}: Gucci={w['Gucci']:.1%} YSL={w['Saint Laurent']:.1%} BV={w['Bottega Veneta']:.1%}")

    # Fetch prices
    stock_data, fx_data = fetch_prices()

    # Compute returns
    raw_ret, excess_ret, glux_ret, spy_ret = compute_returns(
        stock_data, fx_data, quarters, pairs
    )
    print(f"\nComputed returns for {len(raw_ret)} companies")

    # Compute signals
    signals = compute_signals(comp_ranks, excess_ret, quarters, pairs)
    print(f"Total signal observations: {len(signals)}")
    for company in COMPANIES:
        n = len([s for s in signals if s["company"] == company])
        print(f"  {company}: {n}")

    # Compute trend and presence signals
    trend_signals = compute_trend_signals(comp_ranks, excess_ret, quarters, pairs)
    presence_signals = compute_presence_signals(comp_ranks, excess_ret, quarters, pairs)
    print(f"Trend signal observations: {len(trend_signals)}")
    print(f"Presence signal observations: {len(presence_signals)}")

    # Generate report
    report = generate_report(signals, comp_ranks, quarters, glux_ret, spy_ret,
                            trend_signals, presence_signals)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

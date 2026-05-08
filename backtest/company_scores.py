#!/usr/bin/env python3
"""
Company-level composite score using ALL Lyst-tracked brands.
Weights = brand revenue / parent total revenue (not normalized to 1.0).
Conglomerates naturally get lower scores because untracked business has 0 weight.
"""

import csv, math, statistics
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TRACKER_CSV = str(REPO_ROOT / "data" / "lyst-index-tracker.csv")
HISTORICAL_CSV = str(REPO_ROOT / "data" / "lyst-historical-2018.csv")
OUTPUT_PATH = str(REPO_ROOT / "results" / "company-scores.md")
UNRANKED = 21

# ═══════════════════════════════════════════
# Company → Brand mapping with revenue weights
# Weight = brand revenue / parent TOTAL revenue (approximate, 2024 basis)
# Conglomerates: weights don't sum to 1.0
# ═══════════════════════════════════════════

# Kering: Gucci/YSL/BV use OI weights (from FactSet), Balenciaga/McQueen use revenue est.
KERING_OI_RAW = {
    2017: (72.1, 12.8, 10.0),
    2018: (83.0, 11.6, 6.1),
    2019: (82.6, 11.8, 4.5),
    2020: (83.4, 12.8, 5.5),
    2021: (74.0, 14.2, 5.7),
    2022: (66.8, 18.2, 6.6),
    2023: (68.7, 20.4, 6.6),
    2024: (62.8, 23.2, 10.0),
    2025: (59.2, 32.4, 16.4),
}
# Balenciaga/McQueen approximate revenue % of Kering total
KERING_OTHER = {
    "Balenciaga": 0.10,
    "Alexander McQueen": 0.04,
}

# Prada: revenue weights varying by year
PRADA_RAW = {
    2017: (0.82, 0.18), 2018: (0.82, 0.18), 2019: (0.81, 0.19),
    2020: (0.80, 0.20), 2021: (0.78, 0.22), 2022: (0.74, 0.26),
    2023: (0.70, 0.30), 2024: (0.62, 0.38), 2025: (0.55, 0.45),
}

# LVMH: brand revenue as % of LVMH total (approximate)
LVMH_WEIGHTS = {
    "Louis Vuitton": 0.35,
    "Dior": 0.10,
    "Fendi": 0.03,
    "Celine": 0.03,
    "Loewe": 0.02,
}

COMPANIES = {
    "Prada Group": {
        "ticker": "1913.HK",
        "brands_fixed": {},
        "brands_dynamic": True,
    },
    "Tapestry": {
        "ticker": "TPR",
        "brands_fixed": {"Coach": 0.75},
        "brands_dynamic": False,
    },
    "Ralph Lauren": {
        "ticker": "RL",
        "brands_fixed": {"Ralph Lauren": 1.00},
        "brands_dynamic": False,
    },
    "Burberry": {
        "ticker": "BRBY.L",
        "brands_fixed": {"Burberry": 1.00},
        "brands_dynamic": False,
    },
    "Kering": {
        "ticker": "KER.PA",
        "brands_fixed": {},
        "brands_dynamic": True,
    },
    "LVMH": {
        "ticker": "MC.PA",
        "brands_fixed": LVMH_WEIGHTS,
        "brands_dynamic": False,
    },
    "Capri Holdings": {
        "ticker": "CPRI",
        "brands_fixed": {"Versace": 0.35},
        "brands_dynamic": False,
    },
    "Moncler": {
        "ticker": "MONC.MI",
        "brands_fixed": {"Moncler": 0.85, "Stone Island": 0.15},
        "brands_dynamic": False,
    },
}


def get_kering_weights(signal_year):
    fy = signal_year - 1
    fy = max(fy, min(KERING_OI_RAW.keys()))
    fy = min(fy, max(KERING_OI_RAW.keys()))
    g, y, b = KERING_OI_RAW[fy]
    # OI percentages as share of total Kering (not normalized)
    w = {"Gucci": g / 100, "Saint Laurent": y / 100, "Bottega Veneta": b / 100}
    w.update(KERING_OTHER)
    return w


def get_prada_weights(signal_year):
    fy = signal_year - 1
    fy = max(fy, min(PRADA_RAW.keys()))
    fy = min(fy, max(PRADA_RAW.keys()))
    p, m = PRADA_RAW[fy]
    return {"Prada": p, "Miu Miu": m}


def get_company_weights(company, year):
    if company == "Kering":
        return get_kering_weights(year)
    elif company == "Prada Group":
        return get_prada_weights(year)
    else:
        return COMPANIES[company]["brands_fixed"].copy()


def parse_q(q_str):
    parts = q_str.strip().split()
    return int(parts[1]), int(parts[0][1:])


def q_str(year, qtr):
    return f"Q{qtr} {year}"


def normalize_quarter(q_str_raw):
    q_str_raw = q_str_raw.strip()
    if q_str_raw.startswith("Q"):
        return q_str_raw
    if "Q" in q_str_raw:
        parts = q_str_raw.split("Q")
        if len(parts) == 2:
            return f"Q{parts[1].strip()} {parts[0].strip()}"
    return q_str_raw


def build_quarters():
    quarters = []
    y, q = 2018, 1
    end_y, end_q = 2026, 1
    while (y, q) <= (end_y, end_q):
        quarters.append(q_str(y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return quarters


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


def compute_brand_scores(brand_data, quarters):
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
                q_3back = quarters[i - 3]
                rank_3back = q_ranks.get(q_3back, UNRANKED)
                trend = rank_3back - rank
            trend_sc = max(-1, min(1, trend / 10))
            pres = min(1, streak / 8)
            score = 0.5 * level + 0.3 * trend_sc + 0.2 * pres
            results[brand][q] = {
                "rank": rank, "score": round(score, 3),
                "level": level, "trend": trend, "streak": streak,
            }
    return results


def compute_company_scores(brand_scores, quarters):
    """Company score = sum(brand_weight × brand_score) for each quarter."""
    results = {}
    for company in COMPANIES:
        results[company] = {}
        for q in quarters:
            year, _ = parse_q(q)
            weights = get_company_weights(company, year)
            total_score = 0
            total_weight = 0
            brand_details = {}
            for brand, w in weights.items():
                bs = brand_scores.get(brand, {}).get(q, {"score": 0, "rank": UNRANKED})
                total_score += w * bs["score"]
                total_weight += w
                brand_details[brand] = {
                    "weight": w, "rank": bs["rank"], "brand_score": bs["score"],
                    "contribution": round(w * bs["score"], 4),
                }
            results[company][q] = {
                "score": round(total_score, 3),
                "total_weight": round(total_weight, 3),
                "brands": brand_details,
            }
    return results


def main():
    quarters = build_quarters()
    quarters_set = set(quarters)
    brand_data = load_all_brands(quarters_set)
    brand_scores = compute_brand_scores(brand_data, quarters)
    company_scores = compute_company_scores(brand_scores, quarters)

    L = []
    L.append("# Company-Level Composite Scores")
    L.append("")
    L.append("> Score = Σ (brand_revenue_weight × brand_composite_score)")
    L.append("> Brand score = 0.5×Level + 0.3×Trend + 0.2×Presence")
    L.append("> Weights = brand revenue / parent total revenue (don't sum to 1.0 for conglomerates)")
    L.append("")

    # --- 1. Score matrix ---
    L.append("## 1. Company Score Matrix")
    L.append("")
    co_order = list(COMPANIES.keys())
    # Show from Q4 2018 onwards (need 3Q lookback)
    show_qs = [q for q in quarters if parse_q(q) >= (2018, 4)]

    # Split into two tables for readability
    for table_cos, table_label in [
        (["Prada Group", "Tapestry", "Ralph Lauren", "Burberry"], "High-Concentration"),
        (["Kering", "LVMH", "Capri Holdings", "Moncler"], "Multi-Brand / Conglomerate"),
    ]:
        L.append(f"### {table_label}")
        L.append("")
        header = "| Quarter | " + " | ".join(table_cos) + " |"
        sep = "|---------|" + "|".join(["------" for _ in table_cos]) + "|"
        L.append(header)
        L.append(sep)
        for q in show_qs:
            cells = []
            for co in table_cos:
                s = company_scores[co][q]["score"]
                cells.append(f"{s:.3f}" if abs(s) > 0.001 else "0")
            L.append(f"| {q} | " + " | ".join(cells) + " |")
        L.append("")

    # --- 2. Latest quarter brand-level breakdown ---
    latest_q = show_qs[-1]
    L.append(f"## 2. Brand Contribution Breakdown ({latest_q})")
    L.append("")

    for company in co_order:
        cs = company_scores[company][latest_q]
        L.append(f"### {company} ({COMPANIES[company]['ticker']}) — Score: **{cs['score']:.3f}** (coverage: {cs['total_weight']:.0%})")
        L.append("")
        L.append("| Brand | Weight | Lyst Rank | Brand Score | Contribution |")
        L.append("|-------|--------|----------|------------|-------------|")
        for brand, bd in sorted(cs["brands"].items(), key=lambda x: -x[1]["contribution"]):
            rank_s = str(bd["rank"]) if bd["rank"] < UNRANKED else "—"
            L.append(f"| {brand} | {bd['weight']:.0%} | {rank_s} | {bd['brand_score']:.3f} | {bd['contribution']:+.4f} |")
        L.append("")

    # --- 3. Score evolution last 8Q ---
    L.append("## 3. Score Evolution (Last 8 Quarters)")
    L.append("")
    last_8 = show_qs[-8:]
    L.append("| Company | " + " | ".join(last_8) + " |")
    L.append("|---------|" + "|".join(["------" for _ in last_8]) + "|")
    for co in co_order:
        cells = []
        for q in last_8:
            s = company_scores[co][q]["score"]
            cells.append(f"{s:.3f}" if abs(s) > 0.001 else "0")
        L.append(f"| {co} | " + " | ".join(cells) + " |")
    L.append("")

    # --- 4. Weight coverage table ---
    L.append("## 4. Lyst Brand Coverage by Company")
    L.append("")
    L.append("| Company | Tracked Brands | Revenue Coverage | Untracked |")
    L.append("|---------|---------------|-----------------|-----------|")
    coverage_info = {
        "Prada Group": ("Prada, Miu Miu", "100%", "—"),
        "Tapestry": ("Coach", "75%", "Kate Spade 20%, Stuart Weitzman 5%"),
        "Ralph Lauren": ("Ralph Lauren", "100%", "—"),
        "Burberry": ("Burberry", "100%", "—"),
        "Kering": ("Gucci, YSL, BV, Balenciaga, McQueen", "~85%", "Brioni, Boucheron, etc."),
        "LVMH": ("LV, Dior, Fendi, Celine, Loewe", "~53%", "Wines, Watches, Perfumes, Retail"),
        "Capri Holdings": ("Versace", "~35%", "Michael Kors 55%, Jimmy Choo 10%"),
        "Moncler": ("Moncler, Stone Island", "100%", "—"),
    }
    for co in co_order:
        brands, cov, untracked = coverage_info[co]
        L.append(f"| {co} | {brands} | {cov} | {untracked} |")
    L.append("")

    # --- 5. Comparison: old vs new Kering/LVMH scores ---
    L.append("## 5. Impact of Adding Brands: Kering & LVMH")
    L.append("")
    L.append("Comparison of company score with and without additional brands.")
    L.append("")

    for company, old_brands, new_brands in [
        ("Kering", ["Gucci", "Saint Laurent", "Bottega Veneta"],
         ["Gucci", "Saint Laurent", "Bottega Veneta", "Balenciaga", "Alexander McQueen"]),
        ("LVMH", ["Louis Vuitton", "Dior"],
         ["Louis Vuitton", "Dior", "Fendi", "Celine", "Loewe"]),
    ]:
        L.append(f"### {company}")
        L.append("")
        L.append("| Quarter | Old Score (fewer brands) | New Score (all brands) | Delta |")
        L.append("|---------|------------------------|----------------------|-------|")
        for q in show_qs[-12:]:
            year, _ = parse_q(q)
            weights = get_company_weights(company, year)
            # Old: only old_brands, normalized
            old_w = {b: weights[b] for b in old_brands if b in weights}
            old_sum_w = sum(old_w.values())
            old_score = sum(
                (old_w[b] / old_sum_w) * brand_scores.get(b, {}).get(q, {"score": 0})["score"]
                for b in old_brands if b in old_w
            ) if old_sum_w > 0 else 0
            new_score = company_scores[company][q]["score"]
            L.append(f"| {q} | {old_score:.3f} | {new_score:.3f} | {new_score - old_score:+.3f} |")
        L.append("")

    report = "\n".join(L)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

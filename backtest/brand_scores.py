#!/usr/bin/env python3
"""Compute composite momentum score for ALL brands on the Lyst index."""

import csv
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TRACKER_CSV = str(REPO_ROOT / "data" / "lyst-index-tracker.csv")
HISTORICAL_CSV = str(REPO_ROOT / "data" / "lyst-historical-2018.csv")
OUTPUT_PATH = str(REPO_ROOT / "results" / "all-brand-scores.md")
UNRANKED = 21

BRAND_TO_PARENT = {
    "Gucci": "Kering", "Saint Laurent": "Kering", "Bottega Veneta": "Kering",
    "Balenciaga": "Kering", "Alexander McQueen": "Kering",
    "Prada": "Prada Group", "Miu Miu": "Prada Group",
    "Coach": "Tapestry",
    "Ralph Lauren": "Ralph Lauren Corp",
    "Burberry": "Burberry Group",
    "Louis Vuitton": "LVMH", "Dior": "LVMH", "Loewe": "LVMH",
    "Fendi": "LVMH", "Celine": "LVMH", "Givenchy": "LVMH",
    "Nike": "Nike Inc", "New Balance": "New Balance (private)",
    "Valentino": "Kering (acquired 2025)",
    "Versace": "Capri Holdings",
    "Off-White": "LVMH", "Jacquemus": "Jacquemus (private)",
    "The Row": "The Row (private)", "Alaia": "Richemont",
    "Toteme": "Toteme (private)", "Maison Margiela": "OTB Group",
    "Coperni": "Coperni (independent)", "Schiaparelli": "Schiaparelli (private)",
}


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
    """Compute Level + Trend + Presence score for each brand each quarter."""
    results = {}  # {brand: {quarter: {score, rank, level, trend, trend_sc, streak, pres}}}

    for brand, q_ranks in brand_data.items():
        results[brand] = {}
        for i, q in enumerate(quarters):
            rank = q_ranks.get(q, UNRANKED)

            # Level
            level = max(0, (21 - rank)) / 20

            # Streak (consecutive quarters ranked, looking back)
            streak = 0
            for j in range(i, -1, -1):
                qj = quarters[j]
                if q_ranks.get(qj, UNRANKED) < UNRANKED:
                    streak += 1
                else:
                    break

            # 3Q Trend
            trend = 0
            if i >= 3:
                q_3back = quarters[i - 3]
                rank_3back = q_ranks.get(q_3back, UNRANKED)
                trend = rank_3back - rank  # positive = improved

            trend_sc = max(-1, min(1, trend / 10))
            pres = min(1, streak / 8)
            score = 0.5 * level + 0.3 * trend_sc + 0.2 * pres

            results[brand][q] = {
                "rank": rank, "level": level, "trend": trend,
                "trend_sc": trend_sc, "streak": streak, "pres": pres,
                "score": round(score, 3),
            }

    return results


def main():
    quarters = build_quarters()
    quarters_set = set(quarters)
    brand_data = load_all_brands(quarters_set)
    scores = compute_brand_scores(brand_data, quarters)

    # Find all brands that have been ranked at least once
    ranked_brands = sorted(
        [b for b in scores if any(scores[b][q]["rank"] < UNRANKED for q in quarters)],
        key=lambda b: b
    )

    print(f"Total brands ever ranked: {len(ranked_brands)}")

    L = []
    L.append("# All Brand Composite Scores")
    L.append("")
    L.append(f"> {len(ranked_brands)} brands, Q1 2018 – Q1 2026")
    L.append("> Score = 0.5 × Level + 0.3 × Trend + 0.2 × Presence")
    L.append("")

    # --- Latest quarter score ranking ---
    latest_q = quarters[-1]
    L.append(f"## 1. {latest_q} Score Ranking (All Brands)")
    L.append("")
    L.append("| Rank | Brand | Parent | Lyst Rank | Level | 3Q Trend | Streak | **Score** |")
    L.append("|------|-------|--------|----------|-------|----------|--------|----------|")

    latest_scores = []
    for brand in ranked_brands:
        s = scores[brand][latest_q]
        parent = BRAND_TO_PARENT.get(brand, "—")
        latest_scores.append((brand, parent, s))

    latest_scores.sort(key=lambda x: -x[2]["score"])
    for i, (brand, parent, s) in enumerate(latest_scores):
        if s["rank"] >= UNRANKED and s["score"] <= 0:
            continue
        L.append(f"| {i+1} | {brand} | {parent} | {s['rank'] if s['rank'] < UNRANKED else '—'} | "
                 f"{s['level']:.3f} | {s['trend']:+.0f} | {s['streak']} | **{s['score']:.3f}** |")
    L.append("")

    # --- Score evolution for top brands (last 8 quarters) ---
    L.append("## 2. Score Evolution (Last 8 Quarters)")
    L.append("")

    # Select brands that were ranked in latest quarter or have score > 0
    active_brands = [b for b, _, s in latest_scores if s["score"] > 0 or s["rank"] < UNRANKED]
    show_qs = quarters[-8:]

    L.append("| Brand | " + " | ".join(show_qs) + " |")
    L.append("|-------|" + "|".join(["------" for _ in show_qs]) + "|")
    for brand in active_brands:
        cells = []
        for q in show_qs:
            s = scores[brand][q]
            if s["score"] > 0.001 or s["rank"] < UNRANKED:
                cells.append(f"{s['score']:.3f}")
            else:
                cells.append("—")
        L.append(f"| {brand} | " + " | ".join(cells) + " |")
    L.append("")

    # --- Full history for all brands (score > 0 only) ---
    L.append("## 3. Full Score History (All Brands, Score > 0)")
    L.append("")

    # Show every 2nd quarter to keep manageable
    show_qs_full = [q for i, q in enumerate(quarters) if i >= 3]  # need 3Q lookback
    # Only show quarters where at least some brands are ranked
    L.append("| Brand | Parent | " + " | ".join(show_qs_full) + " |")
    L.append("|-------|--------|" + "|".join(["---" for _ in show_qs_full]) + "|")

    for brand in ranked_brands:
        parent = BRAND_TO_PARENT.get(brand, "—")
        cells = []
        any_nonzero = False
        for q in show_qs_full:
            s = scores[brand][q]
            if s["score"] > 0.001:
                cells.append(f"{s['score']:.2f}")
                any_nonzero = True
            elif s["rank"] < UNRANKED:
                cells.append(f"{s['score']:.2f}")
                any_nonzero = True
            else:
                cells.append("")
        if any_nonzero:
            L.append(f"| {brand} | {parent} | " + " | ".join(cells) + " |")
    L.append("")

    # --- Rank table (brand × quarter) ---
    L.append("## 4. Lyst Rank History (All Brands)")
    L.append("")
    L.append("| Brand | " + " | ".join(show_qs_full) + " |")
    L.append("|-------|" + "|".join(["---" for _ in show_qs_full]) + "|")
    for brand in ranked_brands:
        cells = []
        any_ranked = False
        for q in show_qs_full:
            r = brand_data[brand].get(q, UNRANKED)
            if r < UNRANKED:
                cells.append(str(r))
                any_ranked = True
            else:
                cells.append("")
        if any_ranked:
            L.append(f"| {brand} | " + " | ".join(cells) + " |")
    L.append("")

    report = "\n".join(L)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

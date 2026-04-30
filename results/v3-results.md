---
tags:
  - backtest
  - lyst-index
  - consumer
  - fashion
date: 2026-03-09
version: v3
---

# Lyst Index → Stock Price Backtest v3

> **v3 改进** (vs v2):
> - 扩展数据: 2018 Q1 – 2025 Q4 (32 季度, 无缺口)
>   - 2018: Top-10 排名; 2019+: Top-20 排名
> - **LVMH 仅跟踪 Louis Vuitton** (原为 Loewe) — 更好的收入代理
> - **Kering 仅跟踪 Gucci** (原为 5 个品牌) — 主导收入贡献者
> - 主基准: GLUX
> - Train/test 分割: 2018-2021 vs 2022-2025
> - 总数据: 32 个季度, 31 个连续季度对

## 数据覆盖

### v3 品牌变更影响

| Company | v2 品牌 | v3 品牌 | 理由 |
|---------|--------|--------|------|
| LVMH (MC.PA) | Loewe | **Louis Vuitton** | LV 占 LVMH Fashion & Leather ~60% 收入 |
| Kering (KER.PA) | Gucci+SL+BV+Bal+Val | **Gucci only** | Gucci 占 Kering ~50% 收入 |

### LV & Gucci 排名时间线

| Quarter | Louis Vuitton | Gucci |
|---------|--------------|-------|
| Q1 2018 | — | 2 |
| Q2 2018 | — | 1 |
| Q3 2018 | — | 2 |
| Q4 2018 | — | 1 |
| Q1 2019 | — | — |
| Q2 2019 | — | — |
| Q3 2019 | — | — |
| Q4 2019 | — | — |
| Q1 2020 | — | — |
| Q2 2020 | — | — |
| Q3 2020 | — | — |
| Q4 2020 | — | — |
| Q1 2021 | — | — |
| Q2 2021 | — | — |
| Q3 2021 | — | — |
| Q4 2021 | — | — |
| Q1 2022 | 3 | 2 |
| Q2 2022 | 5 | 1 |
| Q3 2022 | 15 | 1 |
| Q4 2022 | 15 | 2 |
| Q1 2023 | 12 | 10 |
| Q2 2023 | 11 | 9 |
| Q3 2023 | 15 | 11 |
| Q4 2023 | 16 | 11 |
| Q1 2024 | 14 | 11 |
| Q2 2024 | 15 | 10 |
| Q3 2024 | 18 | 8 |
| Q4 2024 | — | 12 |
| Q1 2025 | — | 17 |
| Q2 2025 | — | 18 |
| Q3 2025 | — | 14 |
| Q4 2025 | — | 9 |

## 基准对比

| Quarter | SPY | GLUX (奢侈品) | EW (等权) | GLUX-SPY |
|---------|-----|---------------|----------|----------|
| Q1 2018→Q2 2018 | +8.21% | +1.05% | +5.59% | -7.16% |
| Q2 2018→Q3 2018 | -4.47% | -13.75% | -14.42% | -9.28% |
| Q3 2018→Q4 2018 | -1.02% | +0.12% | -3.33% | +1.14% |
| Q4 2018→Q1 2019 | +10.37% | +13.11% | +10.20% | +2.74% |
| Q1 2019→Q2 2019 | +3.22% | -0.19% | +1.05% | -3.41% |
| Q2 2019→Q3 2019 | +1.00% | +0.85% | -3.11% | -0.15% |
| Q3 2019→Q4 2019 | +7.79% | +5.52% | +6.63% | -2.27% |
| Q4 2019→Q1 2020 | -10.75% | -18.52% | -27.66% | -7.77% |
| Q1 2020→Q2 2020 | +13.10% | +23.09% | +8.18% | +9.99% |
| Q2 2020→Q3 2020 | +5.42% | +12.65% | +22.64% | +7.23% |
| Q3 2020→Q4 2020 | +13.74% | +25.13% | +34.64% | +11.39% |
| Q4 2020→Q1 2021 | +9.00% | +12.75% | +16.60% | +3.75% |
| Q1 2021→Q2 2021 | +5.95% | +1.99% | +2.76% | -3.96% |
| Q2 2021→Q3 2021 | +3.63% | +2.11% | -3.51% | -1.52% |
| Q3 2021→Q4 2021 | -4.29% | -7.01% | -3.94% | -2.72% |
| Q4 2021→Q1 2022 | -1.07% | -8.91% | -14.72% | -7.84% |
| Q1 2022→Q2 2022 | -7.29% | -9.36% | -2.87% | -2.07% |
| Q2 2022→Q3 2022 | -2.29% | -6.87% | -7.01% | -4.58% |
| Q3 2022→Q4 2022 | +4.49% | +24.30% | +33.66% | +19.81% |
| Q4 2022→Q1 2023 | +1.82% | +7.24% | +4.38% | +5.42% |
| Q1 2023→Q2 2023 | +12.57% | +1.53% | -2.12% | -11.04% |
| Q2 2023→Q3 2023 | -8.00% | -17.00% | -14.60% | -9.00% |
| Q3 2023→Q4 2023 | +17.35% | +6.43% | +5.65% | -10.92% |
| Q4 2023→Q1 2024 | +3.49% | +4.37% | +3.40% | +0.88% |
| Q1 2024→Q2 2024 | +7.28% | -5.15% | -12.11% | -12.43% |
| Q2 2024→Q3 2024 | +7.88% | +4.13% | +3.09% | -3.75% |
| Q3 2024→Q4 2024 | +3.86% | +8.47% | +15.72% | +4.61% |
| Q4 2024→Q1 2025 | -7.85% | -11.57% | -18.62% | -3.72% |
| Q1 2025→Q2 2025 | +16.04% | +16.81% | +29.08% | +0.77% |
| Q2 2025→Q3 2025 | +7.85% | +3.46% | +13.22% | -4.39% |
| Q3 2025→Q4 2025 | +1.39% | -1.13% | -2.27% | -2.52% |
| **Train (2018-2021)** | **+205.4%** | **+77.6%** | **+96.4%** | **-127.8%** |
| **Test (2022-2025)** | **+121.5%** | **+38.8%** | **+45.4%** | **-82.7%** |
| **Overall** | **+196.5%** | **+75.8%** | **+72.5%** | **-120.8%** |

### S1 信号在不同基准下的稳健性

| Benchmark | r (ΔRank vs Excess) | t-stat | p-value | Hit Rate | n |
|-----------|-------|--------|---------|----------|---|
| SPY (大盘) | 0.0717 | 1.24 | 0.215 | 21% | 300 |
| GLUX (奢侈品指数) | 0.0901 | 1.56 | 0.118 | 21% | 300 |
| EW (等权) | 0.0792 | 1.37 | 0.170 | 20% | 300 |

### S3 信号在不同基准下的稳健性

| Benchmark | Avg Excess | t-stat | p-value | % Positive | n |
|-----------|-----------|--------|---------|-----------|---|
| SPY (大盘) | -1.97% | -0.52 | 0.609 | 55% | 20 |
| GLUX (奢侈品指数) | +0.50% | 0.18 | 0.849 | 60% | 20 |
| EW (等权) | -0.79% | -0.27 | 0.784 | 55% | 20 |

## S1: 排名改善 → 下季超额回报 (USD)

**全样本** (n=300)

- **相关系数**: r=0.0901 (t=1.56, p=0.118)
- **方向命中率**: 21.0%
- **改善组**: +3.43% (n=44) vs **下跌组**: -4.68% (n=38)
- **多空价差**: +8.11%

| Company | Ticker | n | Corr (r) | t-stat | p-value | Hit% | Avg Excess |
|---------|--------|---|----------|--------|---------|------|-----------|
| Burberry | BRBY.L | 30 | -0.168 | -0.90 | 0.376 | 10% | -1.43% |
| Capri | CPRI | 30 | +0.227 | 1.23 | 0.229 | 37% | -1.46% |
| H&M Group | HM-B.ST | 30 | -0.070 | -0.37 | 0.710 | 7% | +0.72% |
| Kering | KER.PA | 30 | +0.064 | 0.34 | 0.735 | 23% | -2.20% |
| LVMH | MC.PA | 30 | +0.024 | 0.13 | 0.873 | 13% | +1.32% |
| Moncler | MONC.MI | 30 | +0.178 | 0.96 | 0.346 | 40% | -0.40% |
| Nike | NKE | 30 | +0.020 | 0.11 | 0.883 | 13% | -1.61% |
| Prada Group | 1913.HK | 30 | +0.298 | 1.65 | 0.109 | 40% | -0.12% |
| Ralph Lauren | RL | 30 | +0.344 | 1.94 | 0.063 | 13% | +2.74% |
| Tapestry | TPR | 30 | +0.169 | 0.91 | 0.373 | 13% | +4.45% |

### Train/Test 分割

**Train (2018 Q1 – 2021 Q4):**
  r=0.0555, t=0.91, p=0.363, hit=19%, n=270

**Test (2022 Q1 – 2025 Q3):**
  r=0.095, t=1.56, p=0.118, hit=23%, n=270

## S2: 排名水平 → 下季超额回报 (Tercile)

| Tercile | Avg Excess | Median | t-stat | p-value | 95% CI | % Pos | n |
|---------|-----------|--------|--------|---------|--------|-------|---|
| Top (最佳排名) | -1.04% | -1.14% | -0.69 | 0.489 | [-3.97, 1.79] | 50% | 103 |
| Mid (中等排名) | +1.63% | +1.62% | 1.28 | 0.201 | [-0.84, 4.11] | 57% | 103 |
| Bottom (最差排名) | +0.43% | -1.35% | 0.25 | 0.806 | [-2.83, 4.05] | 45% | 104 |

## S3: 进入 Top 10 → 下季超额回报

- **事件数**: 20
- **平均超额回报**: +0.50% (t=0.18, p=0.849)
- **95% CI**: [-4.83, 5.46]
- **正超额率**: 60%

| Company | Quarter | Rank Move | Excess Return |
|---------|---------|-----------|---------------|
| Kering | Q1 2022 | 21→2 | +10.41% |
| Kering | Q2 2024 | 11→10 | -19.78% |
| Prada Group | Q2 2018 | 21→10 | -12.25% |
| Prada Group | Q1 2022 | 21→4 | +6.50% |
| LVMH | Q1 2022 | 21→3 | +8.17% |
| Ralph Lauren | Q3 2025 | 11→9 | +8.14% |
| Burberry | Q4 2018 | 21→10 | -3.22% |
| Burberry | Q2 2022 | 12→10 | +8.60% |
| Burberry | Q3 2023 | 13→10 | -28.71% |
| Moncler | Q4 2018 | 21→4 | +5.68% |
| Moncler | Q1 2022 | 21→7 | -2.24% |
| Moncler | Q4 2022 | 17→3 | +14.66% |
| Moncler | Q4 2024 | 13→8 | +8.37% |
| Moncler | Q2 2025 | 11→10 | +4.97% |
| Tapestry | Q4 2024 | 15→5 | +6.97% |
| Nike | Q2 2018 | 21→9 | +8.72% |
| H&M Group | Q1 2025 | 17→6 | -11.20% |
| Capri | Q2 2018 | 21→7 | -2.95% |
| Capri | Q3 2022 | 11→9 | +15.39% |
| Capri | Q1 2023 | 13→8 | -16.29% |

## S3b: 跌出 Top 10 → 下季超额回报

- **事件数**: 18
- **平均超额回报**: -7.20% (t=-1.92, p=0.072)
- **95% CI**: [-14.5, -0.38]
- **正超额率**: 39%

| Company | Quarter | Rank Move | Excess Return |
|---------|---------|-----------|---------------|
| Kering | Q1 2019 | 1→21 | -2.47% |
| Kering | Q3 2023 | 9→11 | -10.99% |
| Kering | Q4 2024 | 8→12 | -16.22% |
| Prada Group | Q4 2018 | 5→21 | -28.07% |
| LVMH | Q3 2022 | 5→15 | +9.22% |
| Burberry | Q1 2019 | 10→21 | +8.99% |
| Burberry | Q4 2022 | 10→18 | +5.36% |
| Burberry | Q1 2024 | 9→12 | -29.94% |
| Moncler | Q2 2018 | 7→21 | -10.97% |
| Moncler | Q1 2019 | 4→21 | +6.94% |
| Moncler | Q2 2022 | 7→18 | +14.56% |
| Moncler | Q3 2024 | 9→13 | +1.47% |
| Moncler | Q1 2025 | 8→11 | -22.04% |
| Moncler | Q3 2025 | 10→11 | -3.63% |
| Nike | Q4 2018 | 4→21 | -4.21% |
| Capri | Q1 2019 | 6→21 | -17.76% |
| Capri | Q4 2022 | 9→13 | -40.62% |
| Capri | Q3 2024 | 6→11 | +10.72% |

## S4: 连续3季上升 → 下季超额回报

- **事件数**: 9
- **平均超额回报**: +5.75%  (t=0.866, p=0.4116)
- **95% CI**: [-6.55, 17.82]
- **正超额率**: 78%

| Company | Quarter | Trajectory | Δ Rank | Excess Ret |
|---------|---------|------------|--------|------------|
| Prada Group | Q3 2022 | 21.0 → 6.1 → 4.4 → 3.0 | +17.9 | +16.19% |
| Prada Group | Q4 2022 | 6.1 → 4.4 → 3.0 → 2.0 | +4.0 | +7.03% |
| Prada Group | Q1 2023 | 4.4 → 3.0 → 2.0 → 1.4 | +3.1 | +2.21% |
| Ralph Lauren | Q3 2025 | 18.0 → 12.0 → 11.0 → 9.0 | +9.0 | +8.14% |
| Burberry | Q3 2023 | 18.0 → 14.0 → 13.0 → 10.0 | +8.0 | -28.71% |
| Burberry | Q4 2023 | 14.0 → 13.0 → 10.0 → 9.0 | +5.0 | -16.68% |
| Tapestry | Q4 2024 | 21.0 → 20.0 → 15.0 → 5.0 | +16.0 | +6.97% |
| Tapestry | Q1 2025 | 20.0 → 15.0 → 5.0 → 4.0 | +16.0 | +41.18% |
| Capri | Q3 2022 | 21.0 → 14.0 → 11.0 → 9.0 | +12.0 | +15.39% |

## S5: 截面多空组合

**Train (2018-2021)** 累计 L/S: +13.3% (27 quarters)
**Test (2022-2025)** 累计 L/S: +49.2% (27 quarters)
**Overall** 累计 L/S: +82.5% (30 quarters)

- **平均季度多空回报**: +2.66% (t=1.258, p=0.2182)
- **95% CI**: [-1.43, 6.81]

| Quarter | Long | Short | L/S Return |
|---------|------|-------|------------|
| Q2 2018 | Capri, Nike, Prada Group | Tapestry, H&M Group, Moncler | -7.30% |
| Q3 2018 | Nike, Prada Group, Capri | Tapestry, H&M Group, Kering | -1.61% |
| Q4 2018 | Moncler, Burberry, Kering | Capri, Prada Group, Nike | +17.88% |
| Q1 2019 | Prada Group, LVMH, Ralph Lauren | Capri, Moncler, Kering | +7.98% |
| Q2 2019 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | -4.64% |
| Q3 2019 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +9.02% |
| Q4 2019 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +17.46% |
| Q1 2020 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +7.15% |
| Q2 2020 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | -18.71% |
| Q3 2020 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | -18.24% |
| Q4 2020 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +2.74% |
| Q1 2021 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +5.73% |
| Q2 2021 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | -6.83% |
| Q3 2021 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +0.65% |
| Q4 2021 | Kering, Prada Group, LVMH | Nike, H&M Group, Capri | +3.72% |
| Q1 2022 | Kering, LVMH, Prada Group | Ralph Lauren, Tapestry, H&M Group | +0.24% |
| Q2 2022 | Nike, Capri, Burberry | H&M Group, LVMH, Moncler | -2.36% |
| Q3 2022 | Capri, Prada Group, Moncler | H&M Group, Nike, LVMH | +3.91% |
| Q4 2022 | Moncler, Tapestry, Nike | Kering, Capri, Burberry | +7.66% |
| Q1 2023 | Capri, Burberry, LVMH | H&M Group, Tapestry, Kering | -15.58% |
| Q2 2023 | Capri, Kering, LVMH | Prada Group, Moncler, Nike | +11.54% |
| Q3 2023 | Burberry, Moncler, Prada Group | Capri, Nike, LVMH | -5.72% |
| Q4 2023 | Moncler, Burberry, Prada Group | H&M Group, LVMH, Capri | +18.10% |
| Q1 2024 | LVMH, Kering, Ralph Lauren | Prada Group, Moncler, Burberry | +10.48% |
| Q2 2024 | Kering, Tapestry, Capri | LVMH, Burberry, Moncler | -8.95% |
| Q3 2024 | Ralph Lauren, Tapestry, Kering | Moncler, Capri, Burberry | +3.86% |
| Q4 2024 | Tapestry, Moncler, H&M Group | Capri, Kering, Ralph Lauren | +26.68% |
| Q1 2025 | H&M Group, Ralph Lauren, Tapestry | Prada Group, Moncler, Kering | +23.69% |
| Q2 2025 | Burberry, Prada Group, Ralph Lauren | Tapestry, H&M Group, Capri | -11.19% |
| Q3 2025 | Kering, Burberry, H&M Group | Nike, Moncler, Prada Group | +2.52% |

### Train/Test 分割
- **Train (2018-2021)**: avg=+1.02%, t=0.493, p=0.6248, n=27
- **Test (2022-2025)**: avg=+2.19%, t=0.936, p=0.3578, n=27

## S6: ΔRank × 起始排名交互

**Top 8** (n=50): r=+0.161, t=1.13, p=0.258
**Mid 9-15** (n=46): r=-0.024, t=-0.16, p=0.876
**Bottom 15+** (n=204): r=+0.076, t=1.09, p=0.276

**交互项 (ΔRank × StartRank) → Excess Return**: r=+0.077, t=1.34, p=0.180, n=300

## 信号汇总

| Signal | Description | Key Metric | t-stat | p-value | Significant? |
|--------|-------------|-----------|--------|---------|-------------|
| S1 | ΔRank → Excess Ret | r=0.0901 | 1.56 | 0.118 | ✗ |
| S3 | Top-10 Entry | avg=+0.50% | 0.18 | 0.849 | ✗ |
| S3b | Top-10 Exit | avg=-7.20% | -1.92 | 0.072 | ✗ |
| S5 | Cross-sectional L/S | avg=+2.66% | 1.26 | 0.218 | ✗ |

## 结论与投资启示

*v3 自动生成 — 所有回报为 USD 超额回报。*
*v3 关键变更: LVMH=LV only, Kering=Gucci only, 32 季度完整数据 (2018-2025, 无缺口)。*

---

数据: lyst-index-tracker | v2: [[lyst-backtest-v2-results]] | v1: [[lyst-backtest-results]]

## Related
- [[CPRI]]
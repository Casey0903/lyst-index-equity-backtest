# Lyst Index 股票回测

> **Lyst Index → 奢侈品 / 时尚股票超额回报** 的可重复回测项目。
>
> 输入：Lyst 季度品牌热度榜（Q1 2018 – Q1 2026，33 个季度）
> 输出：单股相关性（S1）、Top-10 进出（S3 / S3b）、动量（S4）、截面多空（S5）、起始排名交互（S6）

🔗 **[在线 Dashboard](https://robinlllll.github.io/lyst-index-equity-backtest/)** — 33 季度品牌轨迹 + 回测结论

---

## 数据源

Lyst 公司每季度发布 [The Lyst Index](https://www.lyst.com/data/the-lyst-index/)，对全球时尚品牌按搜索量、媒体提及、社交关注等综合打分排名。本项目把这些公开榜单整理成可回测的结构化数据。

| 文件 | 内容 | 来源 |
|---|---|---|
| `data/lyst-index-tracker.csv` | Q1 2019 – Q1 2026 完整排名（每季 Top 20） | Lyst.com 公开发布，整理 |
| `data/lyst-historical-2018.csv` | 2018 年榜单（早期数据格式不同，单独存档） | Lyst.com 公开发布 |

> ⚠️ Lyst 的榜单本身是 Lyst Inc. 的产品；本项目仅整理排名数据并附 attribution，不重发布 Lyst 的原始报告。

## 运行回测

```bash
pip install -r backtest/requirements.txt
python backtest/backtest.py
```

脚本会自动检测 `data/lyst-index-tracker.csv` 里的最新季度，输出报告到 `results/v3.1-results.md`。下个季度 Lyst 发新榜后只需更新 tracker CSV，重跑即可。

## 方法论

**研究问题**：品牌热度排名能否预测下一季度母公司股价的相对表现？

**做法**：
1. 把每个上市公司用其代表性品牌的 Lyst 排名作为代理（详见下表）
2. 对每个连续季度对 (q1, q2)，用 q1 期排名 / 排名变化作为信号
3. q1 publish 日（约 quarter_end + 25 天）→ q2 publish 日的股价回报（USD），减去 GLUX（标普全球奢侈品指数）作为 excess return
4. 计算 6 类信号的统计显著性 + train (2018-2021) / test (2022+) 划分

**公司 → 品牌映射（v3 改进）**：

| 公司 | Ticker | Lyst 品牌代理 | 说明 |
|---|---|---|---|
| Kering | KER.PA | Gucci only | Gucci ~50% 营收占比 |
| LVMH | MC.PA | Louis Vuitton only | LV ~60% Fashion & Leather 营收 |
| Prada Group | 1913.HK | Prada (0.65) + Miu Miu (0.35) | 营收加权 |
| Moncler | MONC.MI | Moncler | Stone Island 暂未纳入 |
| Tapestry | TPR | Coach | 主品牌 |
| Capri | CPRI | (已剔除) | Michael Kors 大众线，从未上 Lyst |
| H&M Group | HM-B.ST | (已剔除) | H&M 主线非渴望性品牌 |
| Burberry | BRBY.L | Burberry | 单品牌 |
| Ralph Lauren | RL | Ralph Lauren | 单品牌 |
| Nike | NKE | Nike | 单品牌 |

**双季 unranked 过滤（v3.1）**：品牌连续两季都不在 Lyst 榜（rank=21 哨兵）时，该公司在该 pair 不参与统计 — ΔRank=0 是噪音不是信号。

## v3.1 关键修订（重要）

v3 → v3.1 之间发现了一个 **train/test 切分 bug**：使用 `q <= "Q4 2021"` 字符串比较时，Python 把 `"Q1 2022"` 判为 `<= "Q4 2021"`（因为 `'1' < '4'` lex 上为真），导致 26 季度 + 26 季度的 train/test 在 31 个总配对里互相重叠 21 季度。

bug 让 v3 的 S5 累计 L/S 显示为 **+236%**，**这是注水的结果**。v3.1 修正后用 `(year, qtr)` 元组比较，干净的样本外（test, 2022+）累计 L/S 实际是 **−20.0% / 16 季 / avg −0.67% / t = −0.22 / p = 0.82** — **没有显著的截面 alpha**。

## 信号表现摘要（v3.1，累计期 Q1 2018 – Q1 2026）

| 信号 | 描述 | 关键指标 | t / p | 显著? |
|---|---|---|---|---|
| S1 | ΔRank → 下季 excess return | r=0.122 | 1.60 / 0.109 | ✗ |
| **S1 (Prada Group only)** | 单股相关 | **r=0.426** | **2.53 / 0.017** | ✓ |
| **S1 (Ralph Lauren only)** | 单股相关（n 小） | **r=0.929** | **5.03 / 0.007** | ✓ (n=6 谨慎) |
| S3 | Top-10 进入 → 下季 | avg +1.0% | 0.38 / 0.71 | ✗ |
| S3b | Top-10 跌出 → 下季 | avg −5.8% | −1.98 / 0.062 | ✗ (接近) |
| S5 | 截面多空 | overall +19.7% / avg +1.23% | 0.54 / 0.59 | ✗ |
| S5 Test (2022+) | 样本外 | **−20.0% / avg −0.67%** | **−0.22 / 0.82** | **✗** |

完整结果见 [`results/v3.1-results.md`](results/v3.1-results.md)。

## 结论

1. **S5 截面多空策略不稳健** — 之前看似强的 +236% 来自 bug + 数据不全；干净样本外实际为负
2. **Prada Group 是唯一可靠的单股信号** — Lyst 榜单变化对 1913.HK 有显著预测力（n=31, p=0.017）
3. **S3b "跌出 Top 10" 可作为风险标记** — 接近显著，可作为减仓 trigger 而非选股 alpha 源
4. **品牌代理选择影响巨大** — v2 用了 5 个 Kering 品牌、Loewe 代理 LVMH，结果与营收 mix 错配；v3 单品牌代理后才看到清晰的信号

## 局限与免责

- 样本量小（每信号 n=21~173），统计 power 弱
- Survivorship bias：只看活到 2026 的奢侈品上市公司
- Lyst 排名定义随年份变化（榜单大小 10 → 20）
- 信号实施有交易成本、税收、汇率摩擦未计入

**本仓库不构成投资建议**。代码 / 数据按 MIT 许可发布，欢迎复现和挑战。

## 仓库结构

```
.
├── index.html                    # 在线 Dashboard（GitHub Pages）
├── data/
│   ├── lyst-index-tracker.csv    # 主数据（2019-latest）
│   └── lyst-historical-2018.csv  # 2018 数据
├── backtest/
│   ├── backtest.py               # v3.1 回测脚本
│   └── requirements.txt          # 依赖
└── results/
    ├── v3.1-results.md           # 最新（截止 Q1 2026）
    ├── v3-results.md             # v3（含 lex bug，仅供对照）
    └── v2-results.md             # v2 历史
```

## License

[MIT](LICENSE)

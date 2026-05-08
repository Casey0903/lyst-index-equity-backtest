#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard for company-level Lyst scores."""

import json
from company_scores import (
    build_quarters, load_all_brands, compute_brand_scores,
    compute_company_scores, get_company_weights, parse_q,
    COMPANIES, UNRANKED,
)
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_HTML = str(REPO_ROOT / "results" / "company-dashboard.html")


def main():
    quarters = build_quarters()
    quarters_set = set(quarters)
    brand_data = load_all_brands(quarters_set)
    brand_scores = compute_brand_scores(brand_data, quarters)
    company_scores = compute_company_scores(brand_scores, quarters)

    show_qs = [q for q in quarters if parse_q(q) >= (2018, 4)]

    co_scores_js = {}
    for co in COMPANIES:
        co_scores_js[co] = {
            "ticker": COMPANIES[co]["ticker"],
            "scores": {q: company_scores[co][q]["score"] for q in show_qs},
        }

    latest_q = show_qs[-1]
    breakdown_js = {}
    for co in COMPANIES:
        cs = company_scores[co][latest_q]
        brands = {}
        for brand, bd in cs["brands"].items():
            brands[brand] = {
                "weight": bd["weight"],
                "rank": bd["rank"] if bd["rank"] < UNRANKED else None,
                "brand_score": bd["brand_score"],
                "contribution": bd["contribution"],
            }
        breakdown_js[co] = {
            "score": cs["score"],
            "coverage": cs["total_weight"],
            "brands": brands,
        }

    brand_ranks_js = {}
    tracked_brands = set()
    for co in COMPANIES:
        year, _ = parse_q(latest_q)
        weights = get_company_weights(co, year)
        for b in weights:
            tracked_brands.add(b)
    for brand in tracked_brands:
        brand_ranks_js[brand] = {}
        for q in show_qs:
            bs = brand_scores.get(brand, {}).get(q)
            if bs:
                brand_ranks_js[brand][q] = {
                    "rank": bs["rank"] if bs["rank"] < UNRANKED else None,
                    "score": bs["score"],
                }

    data_json = json.dumps({
        "quarters": show_qs,
        "latest_quarter": latest_q,
        "companies": co_scores_js,
        "breakdown": breakdown_js,
        "brand_ranks": brand_ranks_js,
    }, ensure_ascii=False)

    html = build_html(data_json)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard saved to: {OUTPUT_HTML}")


def build_html(data_json):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Company Lyst Scores Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;
  --text:#e8e4dc;--text-dim:#8a8578;--gold:#c9a96e;
  --prada:#4a8ef5;--tapestry:#f59e0b;--rl:#10b981;--burberry:#ef4444;
  --kering:#e85d50;--lvmh:#9b6dff;--capri:#ec4899;--moncler:#06b6d4;
}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;padding:24px 32px;max-width:1500px;margin:0 auto}}
header{{text-align:center;padding:32px 0 24px}}
h1{{font-size:2.2rem;font-weight:700;letter-spacing:0.03em}}
h1 span{{color:var(--gold)}}
.subtitle{{color:var(--text-dim);font-size:0.95rem;margin-top:6px}}
.meta{{color:var(--text-dim);font-size:0.82rem;margin-top:4px;font-family:'JetBrains Mono',monospace}}

.controls{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:16px 0 8px}}
.co-btn{{
  padding:6px 16px;border-radius:20px;border:1px solid var(--border);
  background:transparent;color:var(--text-dim);cursor:pointer;font-size:0.82rem;
  font-family:'DM Sans',sans-serif;transition:all 0.2s;
}}
.co-btn:hover{{border-color:var(--gold);color:var(--text)}}
.co-btn.active{{border-color:var(--btn-color,var(--gold));color:var(--text);background:rgba(255,255,255,0.04)}}

.section{{margin:40px 0}}
.section-title{{font-size:1.3rem;font-weight:600;margin-bottom:16px;padding-left:4px}}
.section-title span{{color:var(--gold);font-family:'JetBrains Mono',monospace;font-size:0.9rem;margin-right:8px}}

.chart-wrapper{{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 24px;overflow:hidden}}
.chart-wrapper svg{{width:100%;height:auto;display:block}}
.y-label{{position:absolute;left:6px;top:50%;transform:rotate(-90deg) translateX(-50%);font-size:0.75rem;color:var(--text-dim);font-family:'JetBrains Mono',monospace;letter-spacing:0.1em;transform-origin:center center}}

.tooltip{{
  position:fixed;pointer-events:none;z-index:100;
  background:rgba(18,18,26,0.95);border:1px solid var(--border);border-radius:8px;
  padding:10px 14px;font-size:0.8rem;display:none;
  backdrop-filter:blur(8px);min-width:160px;
}}
.tooltip .co-name{{font-weight:700;font-size:0.9rem;margin-bottom:4px}}
.tooltip .detail{{color:var(--text-dim);font-size:0.78rem;line-height:1.5}}
.tooltip .score-val{{color:var(--gold);font-weight:600}}

.breakdown-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}}
.breakdown-card{{
  background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;
}}
.breakdown-card h3{{font-size:1rem;font-weight:600;margin-bottom:2px}}
.breakdown-card .ticker{{color:var(--text-dim);font-size:0.78rem;font-family:'JetBrains Mono',monospace}}
.breakdown-card .co-score{{font-size:1.6rem;font-weight:700;margin:8px 0}}
.breakdown-card .coverage{{font-size:0.78rem;color:var(--text-dim);margin-bottom:10px}}

.bar-row{{display:flex;align-items:center;margin:4px 0;font-size:0.78rem}}
.bar-label{{width:160px;min-width:160px;text-align:right;padding-right:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar-track{{flex:1;height:18px;background:rgba(255,255,255,0.03);border-radius:4px;position:relative;overflow:hidden}}
.bar-fill{{height:100%;border-radius:4px;transition:width 0.5s ease}}
.bar-val{{width:60px;text-align:right;padding-left:8px;font-family:'JetBrains Mono',monospace;color:var(--text-dim);font-size:0.75rem}}

.heatmap-wrap{{overflow-x:auto;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}}
table.heatmap{{border-collapse:collapse;min-width:100%;font-size:0.78rem;font-family:'JetBrains Mono',monospace}}
table.heatmap th{{padding:6px 10px;color:var(--text-dim);font-weight:500;text-align:center;white-space:nowrap}}
table.heatmap td{{padding:6px 10px;text-align:center;border-radius:4px;white-space:nowrap}}
table.heatmap td.co-label{{text-align:left;font-family:'DM Sans',sans-serif;font-weight:600;color:var(--text);font-size:0.82rem}}

.legend-row{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin:10px 0 0}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:0.78rem;color:var(--text-dim)}}
.legend-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
</style>
</head>
<body>
<header>
  <h1>Company <span>Lyst Scores</span></h1>
  <div class="subtitle">Revenue-Weighted Brand Composite Scores &mdash; Q4 2018 to Q1 2026</div>
  <div class="meta">8 companies &middot; 15 brands tracked &middot; Score = &Sigma;(brand_weight &times; brand_score)</div>
</header>

<div class="controls" id="controls"></div>
<div class="legend-row" id="legend"></div>

<div class="section">
  <div class="section-title"><span>01</span>Score Trajectories</div>
  <div class="chart-wrapper">
    <div class="y-label">SCORE</div>
    <svg id="chart" viewBox="0 0 1400 520"></svg>
  </div>
</div>

<div class="section">
  <div class="section-title"><span>02</span>Brand Contribution Breakdown</div>
  <div class="breakdown-grid" id="breakdown"></div>
</div>

<div class="section">
  <div class="section-title"><span>03</span>Score Heatmap (Last 12 Quarters)</div>
  <div class="heatmap-wrap">
    <table class="heatmap" id="heatmap"></table>
  </div>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
const DATA = {data_json};

const CO_COLORS = {{
  'Prada Group':'var(--prada)','Tapestry':'var(--tapestry)',
  'Ralph Lauren':'var(--rl)','Burberry':'var(--burberry)',
  'Kering':'var(--kering)','LVMH':'var(--lvmh)',
  'Capri Holdings':'var(--capri)','Moncler':'var(--moncler)',
}};
const CO_HEX = {{
  'Prada Group':'#4a8ef5','Tapestry':'#f59e0b',
  'Ralph Lauren':'#10b981','Burberry':'#ef4444',
  'Kering':'#e85d50','LVMH':'#9b6dff',
  'Capri Holdings':'#ec4899','Moncler':'#06b6d4',
}};
const CO_ORDER = ['Prada Group','Tapestry','Ralph Lauren','Burberry','Kering','LVMH','Capri Holdings','Moncler'];

const quarters = DATA.quarters;
const tooltip = document.getElementById('tooltip');
let activeCompany = null;

// ────── Controls ──────
(function buildControls() {{
  const wrap = document.getElementById('controls');
  const allBtn = document.createElement('button');
  allBtn.className = 'co-btn active';
  allBtn.textContent = 'All';
  allBtn.onclick = () => {{ activeCompany = null; updateChart(); updateBtns(); }};
  wrap.appendChild(allBtn);

  CO_ORDER.forEach(co => {{
    const btn = document.createElement('button');
    btn.className = 'co-btn';
    btn.textContent = co;
    btn.style.setProperty('--btn-color', CO_HEX[co]);
    btn.onclick = () => {{
      activeCompany = activeCompany === co ? null : co;
      updateChart();
      updateBtns();
    }};
    wrap.appendChild(btn);
  }});

  const legend = document.getElementById('legend');
  CO_ORDER.forEach(co => {{
    const item = document.createElement('div');
    item.className = 'legend-item';
    item.innerHTML = `<div class="legend-dot" style="background:${{CO_HEX[co]}}"></div>${{co}} (${{DATA.companies[co].ticker}})`;
    legend.appendChild(item);
  }});
}})();

function updateBtns() {{
  document.querySelectorAll('.co-btn').forEach(btn => {{
    if (btn.textContent === 'All') btn.classList.toggle('active', !activeCompany);
    else btn.classList.toggle('active', btn.textContent === activeCompany);
  }});
}}

// ────── Main Chart ──────
const SVG_W = 1400, SVG_H = 520;
const PAD = {{ left: 60, right: 140, top: 30, bottom: 50 }};
const PLOT_W = SVG_W - PAD.left - PAD.right;
const PLOT_H = SVG_H - PAD.top - PAD.bottom;

const yMin = -0.4, yMax = 1.0;
function xScale(i) {{ return PAD.left + (i / (quarters.length - 1)) * PLOT_W; }}
function yScale(v) {{ return PAD.top + (1 - (v - yMin) / (yMax - yMin)) * PLOT_H; }}

function cardinalSpline(points, tension) {{
  tension = tension || 0.4;
  if (points.length < 2) return '';
  if (points.length === 2) return 'M' + points[0].x + ',' + points[0].y + 'L' + points[1].x + ',' + points[1].y;
  var d = 'M' + points[0].x + ',' + points[0].y;
  for (var i = 0; i < points.length - 1; i++) {{
    var p0 = points[Math.max(0, i - 1)];
    var p1 = points[i];
    var p2 = points[i + 1];
    var p3 = points[Math.min(points.length - 1, i + 2)];
    var cp1x = p1.x + (p2.x - p0.x) / 6 / tension;
    var cp1y = p1.y + (p2.y - p0.y) / 6 / tension;
    var cp2x = p2.x - (p3.x - p1.x) / 6 / tension;
    var cp2y = p2.y - (p3.y - p1.y) / 6 / tension;
    d += 'C' + cp1x + ',' + cp1y + ',' + cp2x + ',' + cp2y + ',' + p2.x + ',' + p2.y;
  }}
  return d;
}}

function buildChart() {{
  const svg = document.getElementById('chart');
  svg.innerHTML = '';
  const ns = 'http://www.w3.org/2000/svg';

  // Grid lines
  const gridVals = [-0.2, 0, 0.2, 0.4, 0.6, 0.8, 1.0];
  gridVals.forEach(v => {{
    const y = yScale(v);
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', PAD.left); line.setAttribute('x2', SVG_W - PAD.right);
    line.setAttribute('y1', y); line.setAttribute('y2', y);
    line.setAttribute('stroke', v === 0 ? '#333' : '#1a1a24');
    line.setAttribute('stroke-width', v === 0 ? 1.5 : 1);
    svg.appendChild(line);

    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', PAD.left - 8); label.setAttribute('y', y + 4);
    label.setAttribute('text-anchor', 'end');
    label.setAttribute('fill', '#8a8578'); label.setAttribute('font-size', '11');
    label.setAttribute('font-family', 'JetBrains Mono, monospace');
    label.textContent = v.toFixed(1);
    svg.appendChild(label);
  }});

  // X-axis labels
  quarters.forEach((q, i) => {{
    const isLast = i === quarters.length - 1;
    const isGrid = i % 4 === 0;
    const tooCloseToEnd = (quarters.length - 1 - i) < 3 && !isLast;
    if ((isGrid && !tooCloseToEnd) || isLast) {{
      const x = xScale(i);
      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', x); label.setAttribute('y', SVG_H - PAD.bottom + 25);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#8a8578'); label.setAttribute('font-size', '11');
      label.setAttribute('font-family', 'JetBrains Mono, monospace');
      label.textContent = q;
      svg.appendChild(label);

      const tick = document.createElementNS(ns, 'line');
      tick.setAttribute('x1', x); tick.setAttribute('x2', x);
      tick.setAttribute('y1', PAD.top); tick.setAttribute('y2', SVG_H - PAD.bottom);
      tick.setAttribute('stroke', '#1a1a24'); tick.setAttribute('stroke-width', 1);
      tick.setAttribute('stroke-dasharray', '3,4');
      svg.appendChild(tick);
    }}
  }});

  // Company lines + dots
  CO_ORDER.forEach(co => {{
    const scores = DATA.companies[co].scores;
    const points = [];
    quarters.forEach((q, i) => {{
      const s = scores[q];
      if (s !== undefined) points.push({{ x: xScale(i), y: yScale(s), q: q, s: s, idx: i }});
    }});

    // Draw segments (break if gap > 2 quarters)
    let seg = [];
    points.forEach((p, pi) => {{
      if (pi > 0 && p.idx - points[pi - 1].idx > 2) {{
        drawSegment(svg, ns, seg, co);
        seg = [];
      }}
      seg.push(p);
    }});
    if (seg.length) drawSegment(svg, ns, seg, co);

    // Dots
    points.forEach(p => {{
      const dot = document.createElementNS(ns, 'circle');
      dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y);
      dot.setAttribute('r', 3.5);
      dot.setAttribute('fill', CO_HEX[co]);
      dot.setAttribute('stroke', 'var(--bg)'); dot.setAttribute('stroke-width', 1.5);
      dot.setAttribute('data-co', co); dot.setAttribute('data-q', p.q);
      dot.setAttribute('class', 'co-dot');
      dot.style.cursor = 'pointer';
      dot.style.transition = 'opacity 0.3s, r 0.15s';
      dot.addEventListener('mouseenter', (e) => showTooltip(e, co, p.q, p.s));
      dot.addEventListener('mouseleave', hideTooltip);
      dot.addEventListener('click', () => {{
        activeCompany = activeCompany === co ? null : co;
        updateChart(); updateBtns();
      }});
      svg.appendChild(dot);
    }});

    // End-of-line label
    if (points.length > 0) {{
      const last = points[points.length - 1];
      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', last.x + 10);
      label.setAttribute('y', last.y + 4);
      label.setAttribute('fill', CO_HEX[co]);
      label.setAttribute('font-size', '12');
      label.setAttribute('font-weight', '600');
      label.setAttribute('font-family', 'DM Sans, sans-serif');
      label.setAttribute('data-co', co);
      label.setAttribute('class', 'co-label-end');
      label.style.transition = 'opacity 0.3s';
      label.textContent = co;
      svg.appendChild(label);
    }}
  }});

  // ────── Event Annotations ──────
  const EVENTS = [
    {{ q: 'Q4 2020', score: 'Kering', label: 'Gucci peak', align: 'above' }},
    {{ q: 'Q4 2022', score: 'Kering', label: 'Balenciaga scandal', align: 'below' }},
    {{ q: 'Q2 2024', score: 'Tapestry', label: 'Coach re-entry', align: 'above' }},
    {{ q: 'Q3 2024', score: 'Ralph Lauren', label: 'RL debut', align: 'above' }},
    {{ q: 'Q3 2024', score: 'Burberry', label: 'Burberry negative', align: 'below' }},
    {{ q: 'Q1 2025', score: 'Kering', label: 'Kering trough', align: 'below' }},
    {{ q: 'Q4 2025', score: 'Ralph Lauren', label: 'RL peak 0.815', align: 'above' }},
  ];
  EVENTS.forEach(ev => {{
    const qi = quarters.indexOf(ev.q);
    if (qi < 0) return;
    const s = DATA.companies[ev.score].scores[ev.q];
    if (s === undefined) return;
    const x = xScale(qi), y = yScale(s);
    const above = ev.align === 'above';

    // Diamond marker
    const diamond = document.createElementNS(ns, 'polygon');
    const d = 5;
    diamond.setAttribute('points', x+','+( y-d)+' '+(x+d)+','+y+' '+x+','+(y+d)+' '+(x-d)+','+y);
    diamond.setAttribute('fill', '#c9a96e');
    diamond.setAttribute('stroke', '#0a0a0f');
    diamond.setAttribute('stroke-width', '1');
    diamond.setAttribute('class', 'evt-marker');
    svg.appendChild(diamond);

    // Annotation line
    const lineY = above ? y - 8 : y + 8;
    const textY = above ? y - 14 : y + 20;
    const aLine = document.createElementNS(ns, 'line');
    aLine.setAttribute('x1', x); aLine.setAttribute('x2', x);
    aLine.setAttribute('y1', lineY); aLine.setAttribute('y2', textY);
    aLine.setAttribute('stroke', '#c9a96e'); aLine.setAttribute('stroke-width', 0.5);
    aLine.setAttribute('class', 'evt-marker');
    svg.appendChild(aLine);

    // Annotation text
    const txt = document.createElementNS(ns, 'text');
    txt.setAttribute('x', x); txt.setAttribute('y', above ? textY - 3 : textY + 10);
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('fill', '#c9a96e'); txt.setAttribute('font-size', '9');
    txt.setAttribute('font-family', 'JetBrains Mono, monospace');
    txt.setAttribute('class', 'evt-marker');
    txt.textContent = ev.label;
    svg.appendChild(txt);
  }});
}}

function drawSegment(svg, ns, pts, co) {{
  if (pts.length < 2) return;
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', cardinalSpline(pts));
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', CO_HEX[co]);
  path.setAttribute('stroke-width', 2.5);
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('data-co', co);
  path.setAttribute('class', 'co-line');
  path.style.transition = 'opacity 0.3s, stroke-width 0.15s';
  svg.appendChild(path);
}}

function updateChart() {{
  document.querySelectorAll('.co-line').forEach(el => {{
    const co = el.getAttribute('data-co');
    if (!activeCompany) {{
      el.style.opacity = 0.85; el.setAttribute('stroke-width', 2.5);
    }} else if (co === activeCompany) {{
      el.style.opacity = 1; el.setAttribute('stroke-width', 4);
      el.style.filter = 'drop-shadow(0 0 6px ' + CO_HEX[co] + ')';
    }} else {{
      el.style.opacity = 0.08; el.setAttribute('stroke-width', 2);
      el.style.filter = 'none';
    }}
  }});
  document.querySelectorAll('.co-dot').forEach(el => {{
    const co = el.getAttribute('data-co');
    if (!activeCompany) {{
      el.style.opacity = 0.9; el.setAttribute('r', 3.5);
    }} else if (co === activeCompany) {{
      el.style.opacity = 1; el.setAttribute('r', 5);
    }} else {{
      el.style.opacity = 0.07; el.setAttribute('r', 2.5);
    }}
  }});
  document.querySelectorAll('.co-label-end').forEach(el => {{
    const co = el.getAttribute('data-co');
    if (!activeCompany) {{
      el.style.opacity = 0.85;
    }} else if (co === activeCompany) {{
      el.style.opacity = 1;
    }} else {{
      el.style.opacity = 0.07;
    }}
  }});
  document.querySelectorAll('.evt-marker').forEach(el => {{
    el.style.opacity = activeCompany ? 0.15 : 0.9;
  }});
}}

function showTooltip(e, co, q, score) {{
  const bd = DATA.breakdown[co];
  let brandsHtml = '';
  if (q === DATA.latest_quarter && bd) {{
    const sorted = Object.entries(bd.brands).sort((a, b) => b[1].contribution - a[1].contribution);
    sorted.forEach(([b, d]) => {{
      const r = d.rank ? '#' + d.rank : 'off';
      brandsHtml += b + '(' + r + ') ' + (d.contribution >= 0 ? '+' : '') + d.contribution.toFixed(3) + '<br>';
    }});
  }}
  tooltip.innerHTML = '<div class="co-name" style="color:' + CO_HEX[co] + '">' + co + '</div>'
    + '<div class="detail">' + q + '<br>Score: <span class="score-val">' + score.toFixed(3) + '</span>'
    + (brandsHtml ? '<br><br>' + brandsHtml : '') + '</div>';
  tooltip.style.display = 'block';
  tooltip.style.left = (e.clientX + 16) + 'px';
  tooltip.style.top = (e.clientY - 10) + 'px';
}}

function hideTooltip() {{ tooltip.style.display = 'none'; }}

// ────── Breakdown Cards ──────
function buildBreakdown() {{
  const wrap = document.getElementById('breakdown');
  CO_ORDER.forEach(co => {{
    const bd = DATA.breakdown[co];
    const card = document.createElement('div');
    card.className = 'breakdown-card';

    const maxContrib = Math.max(...Object.values(bd.brands).map(b => Math.abs(b.contribution)), 0.01);
    const sorted = Object.entries(bd.brands).sort((a, b) => b[1].contribution - a[1].contribution);

    let barsHtml = '';
    sorted.forEach(([brand, d]) => {{
      const pct = Math.max(0, d.contribution / maxContrib * 100);
      const r = d.rank ? '#' + d.rank : 'off';
      const w = (d.weight * 100).toFixed(0) + '%';
      barsHtml += '<div class="bar-row">'
        + '<div class="bar-label">' + brand + ' <span style="color:var(--text-dim);font-size:0.7rem">(' + w + ', ' + r + ')</span></div>'
        + '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + CO_HEX[co] + ';opacity:0.7"></div></div>'
        + '<div class="bar-val">' + (d.contribution >= 0 ? '+' : '') + d.contribution.toFixed(3) + '</div>'
        + '</div>';
    }});

    card.innerHTML = '<h3 style="color:' + CO_HEX[co] + '">' + co + '</h3>'
      + '<div class="ticker">' + DATA.companies[co].ticker + '</div>'
      + '<div class="co-score" style="color:' + CO_HEX[co] + '">' + bd.score.toFixed(3) + '</div>'
      + '<div class="coverage">Coverage: ' + (bd.coverage * 100).toFixed(0) + '% of revenue</div>'
      + barsHtml;
    wrap.appendChild(card);
  }});
}}

// ────── Heatmap ──────
function buildHeatmap() {{
  const table = document.getElementById('heatmap');
  const showQs = quarters.slice(-12);

  function scoreColor(s) {{
    if (s === null || s === undefined) return 'transparent';
    if (s < -0.1) return 'rgba(239,68,68,0.35)';
    if (s < 0.05) return 'rgba(239,68,68,0.15)';
    if (s < 0.2) return 'rgba(255,255,255,0.04)';
    if (s < 0.4) return 'rgba(16,185,129,0.12)';
    if (s < 0.6) return 'rgba(16,185,129,0.25)';
    if (s < 0.8) return 'rgba(16,185,129,0.40)';
    return 'rgba(201,169,110,0.50)';
  }}

  let html = '<thead><tr><th></th>';
  showQs.forEach(q => {{ html += '<th>' + q + '</th>'; }});
  html += '</tr></thead><tbody>';

  CO_ORDER.forEach(co => {{
    html += '<tr><td class="co-label" style="color:' + CO_HEX[co] + '">' + co + '</td>';
    showQs.forEach(q => {{
      const s = DATA.companies[co].scores[q];
      const bg = scoreColor(s);
      const txt = s !== undefined ? (Math.abs(s) < 0.001 ? '0' : s.toFixed(2)) : '';
      html += '<td style="background:' + bg + '">' + txt + '</td>';
    }});
    html += '</tr>';
  }});
  html += '</tbody>';
  table.innerHTML = html;
}}

// ────── Init ──────
buildChart();
buildBreakdown();
buildHeatmap();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()

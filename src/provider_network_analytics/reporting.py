from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .scoring import ScoreOutputs


def render_dashboard(
    base_tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    score_outputs: ScoreOutputs,
    quality_report: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _payload(base_tables, marts, score_outputs, quality_report)
    output_path.write_text(TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, default=str)), encoding="utf-8")


def write_executive_summary(
    base_tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    score_outputs: ScoreOutputs,
    quality_report: pd.DataFrame,
    output_path: Path,
) -> None:
    provider = marts["mart_provider_peer_benchmark"]
    contracting = marts["mart_contracting_opportunity"]
    aco = marts["mart_aco_performance"]
    hospital = marts["mart_hospital_quality_scorecard"]
    failures = int((quality_report["status"] == "FAIL").sum())
    lines = [
        "# Executive Summary",
        "",
        f"- Providers analyzed: {len(base_tables['dim_provider']):,}",
        f"- Facilities analyzed: {len(base_tables['dim_facility']):,}",
        f"- ACOs analyzed: {len(base_tables['dim_aco']):,}",
        f"- Total Medicare payment: ${base_tables['fact_provider_year']['total_payment'].sum():,.0f}",
        f"- Provider intervention tier: {(provider['performance_tier'].astype(str) == 'Intervention').sum():,}",
        f"- Preferred VBC candidates: {(contracting['opportunity_tier'].astype(str) == 'Preferred value-based contract candidate').sum():,}",
        f"- ACO earned shared savings: ${aco['earned_shared_savings'].sum():,.0f}",
        f"- Average hospital quality composite: {hospital['quality_composite_score'].mean():.2f}",
        f"- Quality failures: {failures}",
        "",
        "## Recommended Actions",
        "",
        "1. Use the contracting queue to prioritize value-based care candidates.",
        "2. Review intervention-tier providers with provider relations and payment integrity teams.",
        "3. Use the hospital quality scorecard to focus quality improvement planning.",
        "4. Use market opportunity scores for network expansion and access strategy.",
        "",
    ]
    for name, metrics in score_outputs.metrics.items():
        lines.append(f"### {name}")
        for key, value in metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _payload(
    base_tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    score_outputs: ScoreOutputs,
    quality_report: pd.DataFrame,
) -> dict[str, object]:
    provider = marts["mart_provider_peer_benchmark"]
    contracting = marts["mart_contracting_opportunity"]
    hospital = marts["mart_hospital_quality_scorecard"]
    aco = marts["mart_aco_performance"]
    market = marts["mart_market_opportunity"]
    outlier = marts["mart_provider_outlier_queue"]
    specialty = provider.groupby("specialty_group", as_index=False).agg(total_payment=("total_payment", "sum"), providers=("provider_key", "nunique")).sort_values("total_payment", ascending=False)
    kpis = {
        "providers": int(len(base_tables["dim_provider"])),
        "facilities": int(len(base_tables["dim_facility"])),
        "acos": int(len(base_tables["dim_aco"])),
        "payment": float(base_tables["fact_provider_year"]["total_payment"].sum()),
        "interventions": int((provider["performance_tier"].astype(str) == "Intervention").sum()),
        "vbcCandidates": int((contracting["opportunity_tier"].astype(str) == "Preferred value-based contract candidate").sum()),
        "acoSavings": float(aco["earned_shared_savings"].sum()),
        "avgQuality": float(hospital["quality_composite_score"].mean()),
        "qualityFailures": int((quality_report["status"] == "FAIL").sum()),
    }
    return {
        "kpis": kpis,
        "specialty": _records(specialty),
        "providerChart": _records(provider.head(220)),
        "acoChart": _records(aco),
        "marketChart": _records(market.head(12)),
        "providers": _records(provider.head(400)),
        "contracting": _records(contracting.head(400)),
        "hospitals": _records(hospital.head(300)),
        "acos": _records(aco.head(300)),
        "markets": _records(market.head(300)),
        "outliers": _records(outlier.head(300)),
        "quality": _records(quality_report),
        "metrics": score_outputs.metrics,
    }


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    clean = frame.copy()
    for col in clean.select_dtypes(include=["category"]).columns:
        clean[col] = clean[col].astype(str)
    clean = clean.replace({pd.NA: None})
    return clean.to_dict(orient="records")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Provider Network Performance & Value-Based Care Analytics</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111f;
      --panel: rgba(255,255,255,.08);
      --strong: rgba(255,255,255,.14);
      --text: #f8fbff;
      --muted: rgba(226,236,255,.70);
      --line: rgba(255,255,255,.15);
      --cyan: #67e8f9;
      --violet: #a78bfa;
      --green: #34d399;
      --amber: #fbbf24;
      --shadow: 0 28px 86px rgba(0,0,0,.34);
      --radius: 8px;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    [data-theme="light"] {
      color-scheme: light;
      --bg: #f1f7ff;
      --panel: rgba(255,255,255,.72);
      --strong: rgba(255,255,255,.92);
      --text: #0d1726;
      --muted: rgba(30,41,59,.72);
      --line: rgba(15,23,42,.12);
      --shadow: 0 28px 86px rgba(15,23,42,.15);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at 10% 5%, rgba(103,232,249,.20), transparent 30rem),
        radial-gradient(circle at 82% 12%, rgba(167,139,250,.20), transparent 32rem),
        radial-gradient(circle at 50% 90%, rgba(52,211,153,.13), transparent 30rem),
        linear-gradient(135deg, var(--bg), #101827 52%, var(--bg));
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
      background-size: 56px 56px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,.72), transparent);
    }
    .shell { width: min(1480px, calc(100% - 32px)); margin: 0 auto; }
    header { position: sticky; top: 0; z-index: 20; backdrop-filter: blur(22px); border-bottom: 1px solid var(--line); background: rgba(7,17,31,.68); }
    [data-theme="light"] header { background: rgba(241,247,255,.76); }
    .nav { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 74px; }
    .brand { display: flex; align-items: center; gap: 12px; font-weight: 900; }
    .mark { width: 38px; height: 38px; border-radius: 8px; background: linear-gradient(135deg, var(--cyan), var(--violet), var(--green)); box-shadow: 0 0 34px rgba(103,232,249,.35); }
    .links { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
    .links a, button, .chip {
      border: 1px solid var(--line); color: var(--text); background: var(--panel); border-radius: var(--radius); padding: 10px 12px; text-decoration: none; font: inherit; cursor: pointer; backdrop-filter: blur(18px); transition: transform .18s ease, background .18s ease, border-color .18s ease;
    }
    .links a:hover, button:hover { transform: translateY(-1px); background: var(--strong); border-color: rgba(103,232,249,.58); }
    .hero { padding: 52px 0 24px; display: grid; grid-template-columns: minmax(0,1.08fr) minmax(340px,.92fr); gap: 24px; }
    .hero-copy, .panel, .metric { border: 1px solid var(--line); background: linear-gradient(145deg, var(--strong), var(--panel)); border-radius: var(--radius); box-shadow: var(--shadow); backdrop-filter: blur(24px); }
    .hero-copy { padding: clamp(24px, 5vw, 56px); }
    .eyebrow { color: var(--cyan); text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 900; }
    h1 { margin: 14px 0 18px; font-size: clamp(36px, 6vw, 76px); line-height: .96; letter-spacing: 0; }
    .subtitle { color: var(--muted); font-size: clamp(16px, 2vw, 20px); line-height: 1.6; max-width: 760px; }
    .hero-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 24px; }
    .primary { background: linear-gradient(135deg, rgba(103,232,249,.96), rgba(167,139,250,.92)); color: #06101e; font-weight: 900; }
    .grid { display: grid; gap: 14px; }
    .metrics { grid-template-columns: repeat(4, minmax(0,1fr)); margin: 18px 0 24px; }
    .metric { padding: 18px; min-height: 118px; }
    .metric span { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; font-weight: 900; }
    .metric strong { display: block; margin-top: 12px; font-size: clamp(24px,3vw,36px); }
    .metric small { color: var(--muted); display: block; margin-top: 8px; }
    .section { padding: 30px 0; }
    .section-head { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 14px; }
    h2 { margin: 0; font-size: clamp(24px,3vw,38px); }
    .section-head p { color: var(--muted); max-width: 780px; line-height: 1.6; margin: 8px 0 0; }
    .two { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .panel { padding: 18px; overflow: hidden; }
    .panel h3 { margin: 0 0 12px; font-size: 18px; }
    .chart { height: 360px; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; align-items: center; }
    input { width: min(100%, 360px); border: 1px solid var(--line); background: rgba(255,255,255,.08); color: var(--text); border-radius: var(--radius); padding: 11px 12px; font: inherit; outline: none; }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: var(--radius); max-height: 520px; }
    table { width: 100%; border-collapse: collapse; min-width: 980px; }
    th, td { padding: 12px 13px; text-align: left; border-bottom: 1px solid var(--line); font-size: 13px; vertical-align: top; }
    th { position: sticky; top: 0; z-index: 1; color: var(--muted); background: rgba(15,23,42,.84); backdrop-filter: blur(12px); text-transform: uppercase; letter-spacing: .08em; font-size: 11px; cursor: pointer; }
    [data-theme="light"] th { background: rgba(255,255,255,.9); }
    tr:hover td { background: rgba(103,232,249,.06); }
    .pill { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; background: rgba(255,255,255,.08); white-space: nowrap; }
    .modal { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; z-index: 50; background: rgba(3,7,18,.62); padding: 18px; }
    .modal.open { display: flex; }
    .modal-card { width: min(780px,100%); max-height: min(730px,92vh); overflow: auto; background: rgba(12,23,40,.94); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); padding: 20px; backdrop-filter: blur(24px); }
    [data-theme="light"] .modal-card { background: rgba(255,255,255,.94); }
    .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
    .detail { border: 1px solid var(--line); border-radius: var(--radius); padding: 10px; }
    .detail span { color: var(--muted); display: block; font-size: 12px; margin-bottom: 4px; }
    footer { padding: 36px 0 48px; color: var(--muted); text-align: center; }
    @media (max-width: 980px) {
      .hero, .two, .metrics { grid-template-columns: 1fr; }
      .nav { flex-direction: column; align-items: flex-start; padding: 14px 0; }
      .links { justify-content: flex-start; }
      table { min-width: 860px; }
    }
  </style>
</head>
<body>
  <script>const DATA = __PAYLOAD__;</script>
  <header>
    <div class="shell nav">
      <div class="brand"><div class="mark"></div><div>Provider Network VBC Analytics</div></div>
      <nav class="links">
        <a href="#overview">Overview</a><a href="#providers">Providers</a><a href="#contracting">Contracting</a><a href="#quality">Quality</a><a href="#markets">Markets</a><a href="#governance">Governance</a>
        <button id="themeToggle" type="button">Light Mode</button>
      </nav>
    </div>
  </header>
  <main class="shell">
    <section class="hero" id="overview">
      <div class="hero-copy">
        <div class="eyebrow">Provider network and value-based care command center</div>
        <h1>Benchmark providers, markets, ACOs, and contract opportunities.</h1>
        <p class="subtitle">A deployable analytics product for provider peer comparison, quality intervention, ACO performance, market strategy, and value-based contracting decisions.</p>
        <div class="hero-actions"><a class="chip primary" href="#contracting">Open Contract Queue</a><a class="chip" href="#governance">View Governance</a></div>
      </div>
      <article class="panel"><h3>Specialty Payment Mix</h3><div id="specialtyChart" class="chart"></div></article>
    </section>
    <section class="grid metrics" id="metrics"></section>
    <section class="section" id="providers">
      <div class="section-head"><div><h2>Provider Peer Benchmarking</h2><p>Compare providers by cost, utilization, quality, and outlier score within network context.</p></div></div>
      <div class="grid two">
        <article class="panel"><h3>Cost vs Utilization Matrix</h3><div id="providerChart" class="chart"></div></article>
        <article class="panel"><h3>Provider Benchmark Table</h3><div class="toolbar"><input id="providerSearch" type="search" placeholder="Search provider, specialty, market"><button data-export="providerTable">Export CSV</button></div><div class="table-wrap"><table id="providerTable"></table></div></article>
      </div>
    </section>
    <section class="section" id="contracting">
      <div class="section-head"><div><h2>Contracting Opportunity</h2><p>Rank providers by volume, quality, efficiency, market need, and stability.</p></div></div>
      <article class="panel"><div class="toolbar"><input id="contractSearch" type="search" placeholder="Search provider, tier, action"><button data-export="contractTable">Export CSV</button></div><div class="table-wrap"><table id="contractTable"></table></div></article>
    </section>
    <section class="section" id="quality">
      <div class="section-head"><div><h2>ACO And Hospital Quality</h2><p>Balance savings, quality, readmissions, and intervention priorities.</p></div></div>
      <div class="grid two">
        <article class="panel"><h3>ACO Savings vs Quality</h3><div id="acoChart" class="chart"></div></article>
        <article class="panel"><h3>Market Opportunity Leaders</h3><div id="marketChart" class="chart"></div></article>
      </div>
      <div class="grid two" style="margin-top:14px;">
        <article class="panel"><h3>Hospital Quality Scorecard</h3><div class="toolbar"><input id="hospitalSearch" type="search" placeholder="Search facility, state, action"><button data-export="hospitalTable">Export CSV</button></div><div class="table-wrap"><table id="hospitalTable"></table></div></article>
        <article class="panel"><h3>ACO Performance</h3><div class="toolbar"><input id="acoSearch" type="search" placeholder="Search ACO, quadrant, tier"><button data-export="acoTable">Export CSV</button></div><div class="table-wrap"><table id="acoTable"></table></div></article>
      </div>
    </section>
    <section class="section" id="markets">
      <div class="section-head"><div><h2>Market Strategy</h2><p>Surface high-cost markets, quality gaps, density gaps, and network strategy priorities.</p></div></div>
      <div class="grid two">
        <article class="panel"><h3>Market Opportunity</h3><div class="toolbar"><input id="marketSearch" type="search" placeholder="Search market, state, action"><button data-export="marketTable">Export CSV</button></div><div class="table-wrap"><table id="marketTable"></table></div></article>
        <article class="panel"><h3>Provider Outlier Queue</h3><div class="toolbar"><input id="outlierSearch" type="search" placeholder="Search provider, reason, action"><button data-export="outlierTable">Export CSV</button></div><div class="table-wrap"><table id="outlierTable"></table></div></article>
      </div>
    </section>
    <section class="section" id="governance">
      <div class="section-head"><div><h2>Governance</h2><p>Quality checks and scoring model cards.</p></div></div>
      <div class="grid two">
        <article class="panel"><h3>Data Quality</h3><div class="table-wrap"><table id="qualityTable"></table></div></article>
        <article class="panel"><h3>Score Metrics</h3><div id="scoreMetrics"></div></article>
      </div>
    </section>
  </main>
  <div class="modal" id="detailModal" role="dialog" aria-modal="true"><div class="modal-card"><div class="section-head"><h2 id="modalTitle">Details</h2><button id="closeModal">Close</button></div><div id="modalBody" class="detail-grid"></div></div></div>
  <footer class="shell">Synthetic or de-identified data only. Do not publish confidential provider contracts or regulated data.</footer>
  <script>
    const fmt = new Intl.NumberFormat("en-US");
    const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
    const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
    const tableState = {};
    const triageKey = "provider-network-vbc-triage";
    const triage = JSON.parse(localStorage.getItem(triageKey) || "{}");
    function saveTriage(){ localStorage.setItem(triageKey, JSON.stringify(triage)); }
    function pretty(k){ return k.replaceAll("_"," ").replace(/([A-Z])/g," $1").replace(/\b\w/g,c=>c.toUpperCase()); }
    function formatValue(k,v){ if(v===null||v===undefined||v==="") return "NA"; if(/amount|payment|expenditure|savings|allowed|submitted/i.test(k)) return money.format(Number(v)||0); if(/rate|percentile|score|index/i.test(k)) return Number(v)<=1.5 ? pct.format(Number(v)||0) : Number(v).toFixed(2); return String(v); }
    function renderMetrics(){
      const items = [["Providers", fmt.format(DATA.kpis.providers), "network entities"], ["Facilities", fmt.format(DATA.kpis.facilities), "quality scorecards"], ["ACOs", fmt.format(DATA.kpis.acos), "value-based groups"], ["Medicare Payment", money.format(DATA.kpis.payment), "synthetic reimbursement"], ["Interventions", fmt.format(DATA.kpis.interventions), "provider tier"], ["VBC Candidates", fmt.format(DATA.kpis.vbcCandidates), "preferred contract tier"], ["ACO Savings", money.format(DATA.kpis.acoSavings), "earned shared savings"], ["Avg Quality", Number(DATA.kpis.avgQuality).toFixed(2), "hospital composite"]];
      document.querySelector("#metrics").innerHTML = items.map(([a,b,c]) => `<article class="metric"><span>${a}</span><strong>${b}</strong><small>${c}</small></article>`).join("");
    }
    function table(id, rows, columns, searchId, keyField){
      tableState[id] = { rows, columns, filtered: rows, sortKey: null, dir: 1, keyField };
      const search = searchId ? document.querySelector(`#${searchId}`) : null;
      if(search) search.addEventListener("input", () => drawTable(id));
      drawTable(id);
    }
    function drawTable(id){
      const state = tableState[id];
      const search = document.querySelector(`#${id.replace("Table","Search")}`);
      const needle = search ? search.value.trim().toLowerCase() : "";
      let rows = state.rows.filter(row => !needle || Object.values(row).join(" ").toLowerCase().includes(needle));
      if(state.sortKey) rows = [...rows].sort((a,b) => String(a[state.sortKey]).localeCompare(String(b[state.sortKey]), undefined, {numeric:true}) * state.dir);
      state.filtered = rows;
      const head = `<thead><tr>${state.columns.map(c => `<th data-sort="${c.key}">${c.label}</th>`).join("")}<th>Actions</th></tr></thead>`;
      const body = rows.map(row => {
        const rowKey = state.keyField ? row[state.keyField] : Object.values(row)[0];
        const t = triage[rowKey] || {};
        const cells = state.columns.map(c => `<td>${c.pill ? `<span class="pill">${formatValue(c.key,row[c.key])}</span>` : formatValue(c.key,row[c.key])}</td>`).join("");
        return `<tr>${cells}<td><button data-detail="${id}" data-key="${rowKey}">Details</button> <button data-flag="${rowKey}">${t.flagged ? "Unflag" : "Flag"}</button> <button data-resolve="${rowKey}">${t.resolved ? "Reopen" : "Resolve"}</button></td></tr>`;
      }).join("");
      document.querySelector(`#${id}`).innerHTML = head + `<tbody>${body}</tbody>`;
      document.querySelectorAll(`#${id} th[data-sort]`).forEach(th => th.addEventListener("click", () => { const key = th.dataset.sort; state.dir = state.sortKey === key ? state.dir * -1 : 1; state.sortKey = key; drawTable(id); }));
      document.querySelectorAll(`#${id} [data-detail]`).forEach(btn => btn.addEventListener("click", () => openDetail(id, btn.dataset.key)));
      document.querySelectorAll(`#${id} [data-flag]`).forEach(btn => btn.addEventListener("click", () => { triage[btn.dataset.flag] = { ...(triage[btn.dataset.flag] || {}), flagged: !(triage[btn.dataset.flag] || {}).flagged }; saveTriage(); drawTable(id); }));
      document.querySelectorAll(`#${id} [data-resolve]`).forEach(btn => btn.addEventListener("click", () => { triage[btn.dataset.resolve] = { ...(triage[btn.dataset.resolve] || {}), resolved: !(triage[btn.dataset.resolve] || {}).resolved }; saveTriage(); drawTable(id); }));
    }
    function openDetail(id,key){
      const state = tableState[id];
      const row = state.rows.find(r => String(r[state.keyField]) === String(key)) || {};
      document.querySelector("#modalTitle").textContent = `${pretty(id.replace("Table",""))} Details`;
      document.querySelector("#modalBody").innerHTML = Object.entries(row).map(([k,v]) => `<div class="detail"><span>${pretty(k)}</span><strong>${formatValue(k,v)}</strong></div>`).join("");
      document.querySelector("#detailModal").classList.add("open");
    }
    function exportTable(id){
      const state = tableState[id]; const rows = state.filtered || state.rows; const cols = state.columns.map(c => c.key);
      const csv = [cols.join(","), ...rows.map(row => cols.map(c => `"${String(row[c] ?? "").replaceAll('"','""')}"`).join(","))].join("\n");
      const blob = new Blob([csv], {type:"text/csv"}); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${id}.csv`; a.click(); URL.revokeObjectURL(a.href);
    }
    function charts(){
      const layout = { paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,0)", font:{ color:getComputedStyle(document.documentElement).getPropertyValue("--text") }, margin:{t:18,r:18,b:48,l:62}, xaxis:{gridcolor:"rgba(148,163,184,.18)"}, yaxis:{gridcolor:"rgba(148,163,184,.18)"} };
      Plotly.newPlot("specialtyChart", [{ labels: DATA.specialty.map(d=>d.specialty_group), values: DATA.specialty.map(d=>d.total_payment), type:"pie", hole:.62, marker:{colors:["#67e8f9","#a78bfa","#34d399","#fbbf24","#fb7185","#60a5fa","#c084fc","#2dd4bf"]} }], {...layout, showlegend:true}, {responsive:true, displayModeBar:false});
      Plotly.newPlot("providerChart", [{ x: DATA.providerChart.map(d=>d.payment_per_beneficiary), y: DATA.providerChart.map(d=>d.services_per_beneficiary), text: DATA.providerChart.map(d=>d.provider_name), type:"scatter", mode:"markers", marker:{ color: DATA.providerChart.map(d=>d.provider_outlier_score), colorscale:"Turbo", size:11, opacity:.86, line:{color:"rgba(255,255,255,.55)",width:1} } }], {...layout, xaxis:{title:"Payment per beneficiary"}, yaxis:{title:"Services per beneficiary"}}, {responsive:true, displayModeBar:false});
      Plotly.newPlot("acoChart", [{ x: DATA.acoChart.map(d=>d.savings_rate), y: DATA.acoChart.map(d=>d.quality_score), text: DATA.acoChart.map(d=>d.aco_name), type:"scatter", mode:"markers", marker:{ size: DATA.acoChart.map(d=>Math.max(8, Math.log(Number(d.assigned_beneficiaries)||1)*1.8)), color: DATA.acoChart.map(d=>d.earned_shared_savings), colorscale:"Viridis", opacity:.86 } }], {...layout, xaxis:{title:"Savings rate"}, yaxis:{title:"Quality score"}}, {responsive:true, displayModeBar:false});
      Plotly.newPlot("marketChart", [{ x: DATA.marketChart.map(d=>d.market_opportunity_score), y: DATA.marketChart.map(d=>d.market), type:"bar", orientation:"h", marker:{color:"#34d399"} }], {...layout, margin:{t:18,r:18,b:48,l:150}}, {responsive:true, displayModeBar:false});
    }
    function initTables(){
      table("providerTable", DATA.providers, [{key:"provider_name",label:"Provider"}, {key:"specialty_group",label:"Specialty",pill:true}, {key:"market",label:"Market"}, {key:"payment_per_beneficiary",label:"Pay/beneficiary"}, {key:"peer_cost_percentile",label:"Cost pct"}, {key:"provider_outlier_score",label:"Outlier"}, {key:"performance_tier",label:"Tier",pill:true}, {key:"recommended_action",label:"Action"}], "providerSearch", "provider_id");
      table("contractTable", DATA.contracting, [{key:"provider_name",label:"Provider"}, {key:"specialty_group",label:"Specialty",pill:true}, {key:"network_value_score",label:"Value score"}, {key:"opportunity_tier",label:"Tier",pill:true}, {key:"market_opportunity_score",label:"Market need"}, {key:"recommended_contract_action",label:"Action"}], "contractSearch", "provider_id");
      table("hospitalTable", DATA.hospitals, [{key:"facility_name",label:"Facility"}, {key:"state_code",label:"State",pill:true}, {key:"overall_star_rating",label:"Stars"}, {key:"readmission_score",label:"Readmit"}, {key:"quality_composite_score",label:"Quality"}, {key:"quality_tier",label:"Tier",pill:true}, {key:"network_action",label:"Action"}], "hospitalSearch", "ccn");
      table("acoTable", DATA.acos, [{key:"aco_name",label:"ACO"}, {key:"state_code",label:"State",pill:true}, {key:"assigned_beneficiaries",label:"Beneficiaries"}, {key:"savings_rate",label:"Savings rate"}, {key:"quality_score",label:"Quality"}, {key:"aco_performance_tier",label:"Tier",pill:true}], "acoSearch", "aco_id");
      table("marketTable", DATA.markets, [{key:"market",label:"Market"}, {key:"state_code",label:"State",pill:true}, {key:"per_capita_cost",label:"Per capita"}, {key:"provider_density",label:"Density"}, {key:"avg_hospital_quality",label:"Quality"}, {key:"market_opportunity_score",label:"Opportunity"}, {key:"recommended_market_action",label:"Action"}], "marketSearch", "geo_key");
      table("outlierTable", DATA.outliers, [{key:"provider_name",label:"Provider"}, {key:"specialty_group",label:"Specialty",pill:true}, {key:"payment_per_beneficiary",label:"Pay/beneficiary"}, {key:"services_per_beneficiary",label:"Services/beneficiary"}, {key:"provider_outlier_score",label:"Outlier"}, {key:"performance_tier",label:"Tier",pill:true}, {key:"recommended_action",label:"Action"}], "outlierSearch", "provider_id");
      table("qualityTable", DATA.quality, [{key:"check_name",label:"Check"}, {key:"status",label:"Status",pill:true}, {key:"value",label:"Value"}, {key:"threshold",label:"Threshold"}], "", "check_name");
    }
    function scoreMetrics(){
      document.querySelector("#scoreMetrics").innerHTML = Object.entries(DATA.metrics).map(([name, metrics]) => `<div class="panel" style="margin-bottom:12px;box-shadow:none;"><h3>${pretty(name)}</h3>${Object.entries(metrics).map(([k,v]) => `<div class="detail"><span>${pretty(k)}</span><strong>${formatValue(k,v)}</strong></div>`).join("")}</div>`).join("");
    }
    document.querySelector("#themeToggle").addEventListener("click", () => { const light = document.documentElement.dataset.theme !== "light"; document.documentElement.dataset.theme = light ? "light" : "dark"; document.querySelector("#themeToggle").textContent = light ? "Dark Mode" : "Light Mode"; setTimeout(charts,0); });
    document.querySelector("#closeModal").addEventListener("click", () => document.querySelector("#detailModal").classList.remove("open"));
    document.querySelector("#detailModal").addEventListener("click", e => { if(e.target.id==="detailModal") e.currentTarget.classList.remove("open"); });
    document.querySelectorAll("[data-export]").forEach(btn => btn.addEventListener("click", () => exportTable(btn.dataset.export)));
    renderMetrics(); charts(); initTables(); scoreMetrics();
  </script>
</body>
</html>"""


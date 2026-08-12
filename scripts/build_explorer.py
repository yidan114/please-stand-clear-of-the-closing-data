"""
build_explorer.py  --  self-contained interactive line explorer (Plotly).

Reads data/processed/panel_features.parquet (produced by run_pipeline.py) and
writes output/subway_explorer.html: pick a line, see its monthly Customer
Journey Time Performance, a 3-month smoothed trend, and -- for the two CBTC
lines -- a marker at the month signalling was switched on.

Built for a non-technical reader: one line at a time, plain-language labels,
no jargon on the surface. Double-click the HTML to open (needs internet for the
Plotly CDN).
"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "output" / "subway_explorer.html"

# Official MTA line colors (from code/utils.py).
MTA_COLORS = {
    "1": "#EE352E", "2": "#EE352E", "3": "#EE352E",
    "4": "#00933C", "5": "#00933C", "6": "#00933C",
    "7": "#B933AD",
    "A": "#0039A6", "C": "#0039A6", "E": "#0039A6",
    "B": "#FF6319", "D": "#FF6319", "F": "#FF6319", "M": "#FF6319",
    "G": "#6CBE45",
    "JZ": "#996633",
    "L": "#A7A9AC",
    "N": "#FCCC0A", "Q": "#FCCC0A", "R": "#FCCC0A", "W": "#FCCC0A",
}
CBTC = {"L": "2012-02-01", "7": "2018-11-01"}

LINE_ORDER = ["1", "2", "3", "4", "5", "6", "7", "A", "B", "C", "D", "E",
              "F", "G", "JZ", "L", "M", "N", "Q", "R", "W"]


def build_payload() -> dict:
    # Read via DuckDB (already a dependency) so no parquet engine is needed.
    pq = (PROCESSED / "panel_features.parquet").as_posix()
    df = duckdb.sql(f"SELECT * FROM read_parquet('{pq}')").df()
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m-%d")
    data = {}
    for line in LINE_ORDER:
        sub = df[df["line"] == line].sort_values("month")
        if sub.empty:
            continue
        data[line] = {
            "months": sub["month"].tolist(),
            "cjtp": [round(v, 4) if pd.notna(v) else None for v in sub["cjtp"]],
            "ma3": [round(v, 4) if pd.notna(v) else None for v in sub["cjtp_ma3"]],
        }
    return {"lines": [l for l in LINE_ORDER if l in data],
            "colors": MTA_COLORS, "cbtc": CBTC, "data": data}


HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>NYC Subway Reliability Explorer</title>
<script charset="utf-8">__PLOTLY_JS__</script>
<style>
  :root{
    --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
    --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  }
  html[data-theme="dark"]{
    --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--plane);color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:940px;margin:0 auto;padding:32px 24px 56px}
  h1{font-size:24px;line-height:1.25;margin:0 0 6px;font-weight:650;letter-spacing:-.01em}
  .sub{color:var(--ink2);font-size:15px;line-height:1.5;margin:0 0 22px;max-width:660px}
  .controls{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
  label{font-size:13px;color:var(--ink2)}
  select{font:inherit;font-size:14px;padding:7px 12px;border-radius:9px;
    border:1px solid var(--border);background:var(--surface);color:var(--ink);cursor:pointer}
  .toggle{margin-left:auto;font-size:13px;color:var(--ink2);background:none;
    border:1px solid var(--border);border-radius:9px;padding:7px 12px;cursor:pointer}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:14px;
    padding:10px 8px 4px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
  #chart{width:100%;height:460px}
  .note{color:var(--muted);font-size:12.5px;line-height:1.5;margin:16px 2px 0}
  .kpis{display:flex;gap:26px;margin:18px 2px 0;flex-wrap:wrap}
  .kpi .v{font-size:22px;font-weight:650;letter-spacing:-.01em}
  .kpi .l{font-size:12px;color:var(--ink2);margin-top:2px}
</style>
</head>
<body>
<div class="wrap">
  <h1>Which subway line actually shows up on time?</h1>
  <p class="sub">Customer Journey Time Performance is the share of rides that finish within
  five minutes of schedule &mdash; the MTA's own answer to the question a rider actually asks.
  Higher is better. Pick a line to see its month-by-month record since 2015.</p>

  <div class="controls">
    <label for="line">Subway line</label>
    <select id="line"></select>
    <button class="toggle" id="themeBtn">Dark mode</button>
  </div>

  <div class="card"><div id="chart"></div></div>

  <div class="kpis">
    <div class="kpi"><div class="v" id="kNow">&mdash;</div><div class="l">latest month (smoothed)</div></div>
    <div class="kpi"><div class="v" id="kAvg">&mdash;</div><div class="l">2022&ndash;present average</div></div>
    <div class="kpi"><div class="v" id="kCbtc">&mdash;</div><div class="l">modern signalling (CBTC)</div></div>
  </div>

  <p class="note" id="note"></p>
</div>

<script>
const PAYLOAD = __PAYLOAD__;
const fmtPct = v => (v==null? "&mdash;" : (v*100).toFixed(1) + "%");

function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}

function draw(line){
  const d = PAYLOAD.data[line];
  const color = PAYLOAD.colors[line] || "#2a78d6";
  const cbtc = PAYLOAD.cbtc[line];

  const raw = {
    x:d.months, y:d.cjtp, type:"scatter", mode:"lines", name:"monthly",
    line:{color:color, width:1, shape:"linear"}, opacity:0.28,
    hoverinfo:"skip"
  };
  const ma = {
    x:d.months, y:d.ma3, type:"scatter", mode:"lines", name:"3-month trend",
    line:{color:color, width:2.4},
    hovertemplate:"%{x|%b %Y}<br><b>%{y:.1%}</b> on-time<extra></extra>"
  };

  const shapes = [
    // pandemic band
    {type:"rect", xref:"x", yref:"paper", x0:"2020-03-01", x1:"2020-12-01",
     y0:0, y1:1, fillcolor:"rgba(210,60,60,0.06)", line:{width:0}, layer:"below"}
  ];
  const anns = [
    {x:"2020-07-15", y:0.02, xref:"x", yref:"paper", text:"pandemic", showarrow:false,
     font:{size:11, color:"#b04a3a"}}
  ];
  if(cbtc){
    shapes.push({type:"line", xref:"x", yref:"paper", x0:cbtc, x1:cbtc, y0:0, y1:1,
      line:{color:css('--ink2'), width:1.4, dash:"dot"}, layer:"below"});
    anns.push({x:cbtc, y:1.03, xref:"x", yref:"paper", yanchor:"bottom",
      text:"CBTC switched on", showarrow:false, font:{size:11.5, color:css('--ink2')}});
  }

  const layout = {
    paper_bgcolor:css('--surface'), plot_bgcolor:css('--surface'),
    margin:{l:52,r:18,t:26,b:38},
    font:{family:'system-ui,-apple-system,"Segoe UI",sans-serif', color:css('--ink2'), size:12.5},
    showlegend:false, shapes, annotations:anns,
    hovermode:"x unified",
    xaxis:{gridcolor:"rgba(0,0,0,0)", linecolor:css('--axis'), tickcolor:css('--axis'),
      showspikes:true, spikecolor:css('--muted'), spikethickness:1, spikedash:"solid",
      spikemode:"across", tickfont:{color:css('--muted')}},
    yaxis:{tickformat:".0%", gridcolor:css('--grid'), zeroline:false,
      linecolor:"rgba(0,0,0,0)", tickcolor:css('--axis'), range:[0.55,1.0],
      tickfont:{color:css('--muted')}, title:{text:"on-time rate", font:{color:css('--muted'),size:12}}}
  };
  Plotly.react("chart", [raw, ma], layout,
    {displayModeBar:false, responsive:true});

  // KPIs
  const lastMa = [...d.ma3].reverse().find(v=>v!=null);
  const recent = d.months.map((m,i)=>[m,d.cjtp[i]]).filter(([m,v])=>m>="2022-01-01"&&v!=null);
  const avg = recent.length? recent.reduce((s,[,v])=>s+v,0)/recent.length : null;
  document.getElementById("kNow").innerHTML = fmtPct(lastMa);
  document.getElementById("kAvg").innerHTML = fmtPct(avg);
  document.getElementById("kCbtc").innerHTML = cbtc? "Yes &middot; "+new Date(cbtc)
      .toLocaleDateString("en-US",{year:"numeric",month:"short"}) : "No";
  document.getElementById("note").innerHTML = cbtc
    ? "The dotted line marks when this line switched to Communications-Based Train Control (CBTC), "
      + "a modern signalling system that lets trains run closer together and more predictably."
    : "This line still runs on legacy fixed-block signalling &mdash; no CBTC upgrade within the data window.";
}

// populate dropdown
const sel = document.getElementById("line");
PAYLOAD.lines.forEach(l=>{
  const o=document.createElement("option"); o.value=l;
  o.textContent = (l==="JZ"?"J/Z":l) + " train"; sel.appendChild(o);
});
sel.value = PAYLOAD.lines.includes("7") ? "7" : PAYLOAD.lines[0];
sel.addEventListener("change", ()=>draw(sel.value));

// theme toggle
const btn = document.getElementById("themeBtn");
btn.addEventListener("click", ()=>{
  const dark = document.documentElement.getAttribute("data-theme")==="dark";
  document.documentElement.setAttribute("data-theme", dark?"light":"dark");
  btn.textContent = dark? "Dark mode":"Light mode";
  draw(sel.value);
});

draw(sel.value);
</script>
</body>
</html>
"""


def _plotly_js() -> str:
    """Inline the Plotly bundle shipped with the plotly package -> offline HTML."""
    js = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    return js.read_text(encoding="utf-8")


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = (HTML
            .replace("__PLOTLY_JS__", _plotly_js())
            .replace("__PAYLOAD__", json.dumps(payload)))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024/1024:.1f} MB, {len(payload['lines'])} lines, offline)")


if __name__ == "__main__":
    main()

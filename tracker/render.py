"""Render docs/index.html (served by GitHub Pages)."""
from __future__ import annotations

import json
from pathlib import Path

from . import config

SECTIONS = [
    ("match", f"Matches up to {config.MAX_EFFECTIVE} €", "matches",
     "Every criterion confirmed. Total = rent + energies + provision ÷ 12."),
    ("near", f"Near misses, {config.MAX_EFFECTIVE}–{config.NEAR_MISS_MAX} €", "near misses",
     "Worth a negotiation attempt, especially if listed for weeks."),
    ("check", "Needs a manual check", "to check",
     "Price fits, but the ad doesn't say something we need. The missing facts are listed per row."),
    ("rooms15", "1,5-room flats", "1,5-room",
     "Smaller than you asked for, but passing every other rule. Missing facts are listed per row."),
    ("removed", "Recently removed", "recently removed",
     "Gone from the portal, most likely rented. Shows how long good offers last."),
    ("excluded", "Excluded", "excluded",
     "Candidates that failed a rule. Use this to spot filter mistakes."),
]

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>2-room rentals, Bratislava</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏠</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#E9ECEA; --panel:#F6F7F5; --ink:#1E2629; --muted:#5B666A; --rule:#CBD2CF;
  --teal:#1F5F66; --amber:#C98A12; --red:#A33B2B; --bar-bg:#D6DCD9;
  box-sizing:border-box;
  padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#161B1D; --panel:#1E2528; --ink:#E4E9E7; --muted:#9AA6A9; --rule:#33403F;
    --teal:#6FB3B8; --amber:#E2A83A; --red:#E07A6A; --bar-bg:#2C3638;
  }
}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 "Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header h1{font-size:2rem;line-height:1.15;margin:0 0 6px;font-weight:700;letter-spacing:-.01em}
header p{margin:0;color:var(--muted);max-width:70ch}
.counts{display:flex;flex-wrap:wrap;gap:8px 22px;margin:18px 0 8px;padding:0;list-style:none}
.counts a{color:var(--ink);text-decoration:none;border-bottom:2px solid var(--rule)}
.counts a:hover,.counts a:focus-visible{border-color:var(--teal)}
.counts b{font-size:1.25rem}
section{margin-top:40px}
section h2{font-size:1.3rem;margin:0 0 2px}
section>p{margin:0 0 12px;color:var(--muted);font-size:.93rem;max-width:75ch}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--rule);border-radius:6px}
table{border-collapse:collapse;width:100%;min-width:1120px;table-layout:fixed;font-size:.93rem}
th,td{text-align:left;padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--rule)}
tr:last-child td{border-bottom:0}
th{font-weight:700;font-size:.85rem;color:var(--muted);white-space:nowrap;position:sticky;top:0;background:var(--panel)}
th button{all:unset;cursor:pointer}
th button:focus-visible,a:focus-visible{outline:2px solid var(--teal);outline-offset:2px;border-radius:2px}
th[aria-sort="ascending"] button::after{content:" ▲"}
th[aria-sort="descending"] button::after{content:" ▼"}
td.num{text-align:right}
.eff{white-space:nowrap}
.eff{font-size:1.1rem;font-weight:700}
.sub{display:block;color:var(--muted);font-size:.82rem}
a{color:var(--teal)}
.title a{font-weight:700;text-decoration:none}
.title a:hover{text-decoration:underline}
.age{min-width:120px}
.bar{height:6px;background:var(--bar-bg);border-radius:3px;margin-top:5px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal)}
.bar.stale i{background:var(--amber)}
.stale-note{color:var(--amber);font-weight:700}
.flag{display:block;font-size:.82rem;color:var(--amber)}
.sub.warn{color:var(--amber)}
.unk{color:var(--red);font-weight:700}
th.numh{text-align:right}
.miss{display:block;font-size:.82rem;color:var(--red)}
.drop{color:var(--teal);font-weight:700}
.rise{color:var(--red)}
details summary{cursor:pointer;font-size:1.3rem;font-weight:700}
.empty{padding:18px;color:var(--muted)}
@media (max-width:640px){header h1{font-size:1.6rem}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>2-room rentals in Bratislava</h1>
  <p>Petržalka, Ružinov, Karlova Ves, Nové Mesto, Rača. Renovated, balcony, 2nd floor or higher.
  Updated __UPDATED__. Sources: nehnutelnosti.sk, bazos.sk.</p>
  <ul class="counts" id="counts"></ul>
</header>
<main id="sections"></main>
</div>
<script>
const DATA = __DATA__;
const SECTIONS = __SECTIONS__;
const STALE = 21;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cond = {renovated:"Renovated",partial:"Partly renovated","new":"New build",original:"Original"};

const ESRC = {portal:"portal field", separate:"from text", total:"from stated total", guessed:"guessed", included:"", unknown:""};
const PSRC = {stated:"stated", assumed:"assumed 1× rent", none:"none", "private":"private owner"};
function moneyCells(r){
  let energy;
  if (r.energy_status === "included") energy = `incl.<span class="sub">in rent</span>`;
  else if (r.energy == null) energy = `<span class="unk">?</span>`;
  else energy = `${Math.round(r.energy)} €<span class="sub${r.energy_status === "guessed" ? " warn" : ""}">${ESRC[r.energy_status] ?? ""}</span>`;
  const prov = r.provision
    ? `${Math.round(r.provision / 12)} €<span class="sub${r.provision_source === "assumed" ? " warn" : ""}">${PSRC[r.provision_source] ?? ""}</span>`
    : `0 €<span class="sub">${PSRC[r.provision_source] ?? ""}</span>`;
  const lb = r.energy == null && r.energy_status !== "included" ? "≥ " : "";
  return `<td class="num">${r.rent != null ? Math.round(r.rent) + " €" : "?"}</td>
    <td class="num">${energy}</td>
    <td class="num">${prov}</td>
    <td class="num"><span class="eff">${r.effective != null ? lb + r.effective + " €" : "?"}</span></td>`;
}
function historyCell(h){
  const p = h.map(x => x[1]).filter(x => x != null);
  if (p.length < 2) return "";
  const cls = p[p.length-1] < p[p.length-2] ? "drop" : "rise";
  return `<span class="sub ${cls}">${p.map(Math.round).join(" → ")}</span>`;
}
function row(r, sec){
  const days = r.days;
  const w = Math.min(100, days / 45 * 100);
  const stale = days >= STALE;
  const links = r.links.map(l => `<a href="${esc(l.url)}" rel="noopener" target="_blank">${esc(l.source)}</a>`).join(", ");
  const notes = sec === "excluded" ? r.excluded.map(x => `<span class="miss">${esc(x)}</span>`).join("")
              : r.unknown.map(x => `<span class="miss">unknown: ${esc(x)}</span>`).join("");
  return `<tr>
    <td class="title"><a href="${esc(r.links[0].url)}" rel="noopener" target="_blank">${esc(r.title)}</a>
      <span class="sub">${esc(r.district ?? "?")}${r.area ? ", " + r.area + " m²" : ""}, on ${links}</span></td>
    ${moneyCells(r)}
    <td class="num">${r.floor ?? "?"}</td>
    <td>${r.balcony === true ? "Yes" : r.balcony === false ? "No" : "?"}</td>
    <td>${cond[r.condition] ?? "?"}</td>
    <td class="age">${days} days${sec === "removed" ? " until removed" : ""}${stale && sec !== "removed" ? ' <span class="stale-note">negotiable</span>' : ""}
      <div class="bar${stale ? " stale" : ""}"><i style="width:${w}%"></i></div>${historyCell(r.history)}</td>
    <td>${r.flags.filter(f => !/^(energies guessed|provision assumed)/.test(f)).map(f => `<span class="flag">${esc(f)}</span>`).join("")}${notes}</td>
  </tr>`;
}
const COLS = [["Listing","title",20],["Rent","rent",7],["Energies","energy",9],["Provision /12","provision",11],["Total","effective",8],
  ["Floor","floor",5],["Balcony",null,7],["Condition",null,9],["Listed","days",11],["Notes",null,13]];

function table(sec, rows){
  if (!rows.length) return `<div class="scroll"><p class="empty">Nothing here right now.</p></div>`;
  const cols = COLS.map(c => `<col style="width:${c[2]}%">`).join("");
  const right = new Set(["rent","energy","provision","effective","floor"]);
  const head = COLS.map(([label,key]) => key ? `<th data-key="${key}"${right.has(key) ? ' class="numh"' : ""}><button>${label}</button></th>` : `<th>${label}</th>`).join("");
  return `<div class="scroll"><table data-sec="${sec}"><colgroup>${cols}</colgroup><thead><tr>${head}</tr></thead><tbody>${rows.map(r => row(r, sec)).join("")}</tbody></table></div>`;
}
function render(){
  const main = document.getElementById("sections");
  const counts = document.getElementById("counts");
  main.innerHTML = ""; counts.innerHTML = "";
  for (const [key, title, short, desc] of SECTIONS){
    const rows = DATA.filter(r => r.section === key).sort((a,b) => (a.effective ?? 1e9) - (b.effective ?? 1e9));
    if (key !== "excluded") counts.insertAdjacentHTML("beforeend", `<li><a href="#${key}"><b>${rows.length}</b> ${esc(short)}</a></li>`);
    const body = `<p>${esc(desc)}</p>${table(key, rows)}`;
    main.insertAdjacentHTML("beforeend", key === "excluded"
      ? `<section id="${key}"><details><summary>${esc(title)} (${rows.length})</summary>${body}</details></section>`
      : `<section id="${key}"><h2>${esc(title)}</h2>${body}</section>`);
  }
  document.querySelectorAll("th[data-key] button").forEach(b => b.addEventListener("click", sortBy));
}
function sortBy(e){
  const th = e.currentTarget.parentElement, key = th.dataset.key;
  const tbl = th.closest("table"), sec = tbl.dataset.sec;
  const dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
  const rows = DATA.filter(r => r.section === sec).sort((a,b) => {
    const x = a[key] ?? (typeof b[key] === "string" ? "" : 1e9), y = b[key] ?? (typeof a[key] === "string" ? "" : 1e9);
    return (x > y ? 1 : x < y ? -1 : 0) * dir;
  });
  tbl.querySelector("tbody").innerHTML = rows.map(r => row(r, sec)).join("");
  tbl.querySelectorAll("th").forEach(t => t.removeAttribute("aria-sort"));
  th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
}
render();
</script>
</body>
</html>
"""


def render(rows: list[dict], updated: str, out: Path = Path("docs/index.html")) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__SECTIONS__", json.dumps(SECTIONS, ensure_ascii=False))
            .replace("__UPDATED__", updated))
    out.write_text(html, encoding="utf-8")

"""The lab in a browser. Reading ranked chunks in a bar beats reading a terminal.

    uv run python -m workshop.app

Serves on http://localhost:8000. Standard library only, one process per
participant, no framework.

The first screen is the agent. A question goes in, the answer comes back, and
the chunks the answer was built from sit under it with their client, their
dates, and their source marked. That order is the argument of the evening: the
answer looks the same whether or not the evidence was safe, so a person has to
read the evidence. The playbook panel is the other reason this exists, because
the applicability rules render here and appear nowhere in the repository.

Measurement is one click away, not first. The board scores every supplied case,
including the two challenges nothing has solved yet, so the ceiling it reports
sits below 100 and says so. A row opens on the client's question and the chunks
that came back for it. It re-reads lab.py on every run, so an edit lands without
restarting the server.
"""

import datetime
import http.server
import html
import json
import os
import urllib.parse
from . import agent
from .display import client_name
from .client import collection, connect, lab, representations
from .playbook import SECTIONS
from .questions import CALIBRATION, CHALLENGE_IDS, MATTERS
from .score import remember, score_all, K

PORT = int(os.getenv("PORT", "8000"))

CASE_TITLES = {
    "harbor-cure-before": "Cure Period Before the Amendment",
    "harbor-liability-cap": "Patient Data Liability Cap",
    "harbor-retention": "Patient Record Retention",
    "cedar-service-credit": "Planned Maintenance Outage",
    "atlas-rejection-before": "Rejected Parts Before the Amendment",
    "atlas-rejection-boundary": "Rejected Parts on the Changeover Date",
    "atlas-substitution-approved": "Connector Approval",
    "harbor-retention-earlier": "The Earlier Retention Schedule",
    "harbor-dispute-pauses-cure": "Does a Dispute Stop the Cure Clock?",
    "cedar-credit-deadline": "Late Service Credit Claim",
    "cedar-exit-midterm": "Leaving Midterm",
    "cedar-subcontractor": "Using a Subcontractor",
    "atlas-substitution-conditions": "Conditions on Connector Approval",
    "atlas-inspection-result": "First-Article Inspection Result",
}

COLUMNS = [
    ("Score", "This case out of 100: its evidence found and its graded ranking, over the share of the "
              "five slots a lawyer could rely on."),
    ("Evidence Found", "Controlling chunks you retrieved. The largest part of the score."),
    ("Graded Ranking (NDCG@5)", "Normalized discounted cumulative gain over the graded results at rank 5. It falls when a controlling chunk is missing, so it moves with Evidence Found."),
    ("Wrong Client", "Chunks from another client's files."),
    ("Not in Effect", "This client's chunks that were not in effect on the question date."),
    ("Duplicate", "Rank slots taken by a repeat copy of a document you already returned."),
]
# The counts say how many slots a case wasted. They never say which chunk wasted
# them, so the diagnosis is still reading the five chunks.

STYLE = """
:root {
  --amaranth: #DC244C; --neon: #6047FF; --ink: #0B0B19; --paper: #FFFFFF;
  --muted: #5A5A6E; --line: #E4E4EC; --wash: #F7F7FA; --good: #147A4A;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: "Mona Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-weight: 400; line-height: 1.55;
}
header { background: var(--ink); color: var(--paper); padding: 16px 24px 18px; }
header h1 { font-size: 21px; font-weight: 500; margin: 0; letter-spacing: -0.02em; }
header h1::before { content: ""; display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; background: var(--amaranth); margin-right: 10px; vertical-align: middle; }
header .frame { color: #9B9BB0; font-size: 12.5px; margin: 7px 0 0; max-width: 780px; }
main { display: grid; grid-template-columns: minmax(0, 1fr) 310px; gap: 26px;
  padding: 22px 24px; max-width: 1240px; margin: 0 auto; }
@media (max-width: 900px) { main { grid-template-columns: 1fr; } }
h2 { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted); margin: 0 0 10px; }
label { display: block; font-size: 12px; color: var(--muted); margin: 0 0 4px; }
input, select, button, textarea {
  font: inherit; padding: 9px 12px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--paper); color: var(--ink);
}
input, select, textarea { width: 100%; }
textarea { min-height: 64px; resize: vertical; line-height: 1.4; }
.field { margin-bottom: 10px; }
.field-row { display: grid; grid-template-columns: 1fr 170px; gap: 10px; }
@media (max-width: 620px) { .field-row { grid-template-columns: 1fr; } }
button { background: var(--ink); color: var(--paper); border-color: var(--ink); cursor: pointer;
  font-weight: 500; width: auto; }
button.ghost { background: var(--paper); color: var(--ink); border-color: var(--line); }
button:hover { background: var(--neon); border-color: var(--neon); color: var(--paper); }
button[disabled] { opacity: .45; cursor: default; }
.micro { color: var(--muted); font-size: 12.5px; margin: 6px 0 0; }
.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.msg { border-radius: 12px; padding: 12px 15px; margin-bottom: 10px; }
.msg .who { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .07em;
  color: var(--muted); margin-bottom: 5px; }
.msg.user { background: var(--wash); }
.msg.user p { margin: 0; font-size: 15px; }
.parties { display: flex; gap: 26px; flex-wrap: wrap; margin-bottom: 11px;
  padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.parties span { font-size: 13.5px; }
.parties em { display: block; font-style: normal; font-size: 10.5px; text-transform: uppercase;
  letter-spacing: .07em; color: var(--muted); margin-bottom: 2px; }
.msg.bot { border: 1px solid var(--line); }
.msg.bot .answer { white-space: pre-wrap; font-size: 14.5px; }
.msg.bot cite { font-style: normal; background: #EFECFF; border-radius: 4px; padding: 0 4px;
  color: var(--neon); font-weight: 500; }
.msg.bot cite.ghosted { background: #FFE4EA; color: var(--amaranth); }
.warn { color: var(--amaranth); font-size: 12.5px; margin-top: 9px; }
.evhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  flex-wrap: wrap; margin: 20px 0 10px; }
.evhead h3 { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 0; }
.chunk { border: 1px solid var(--line); border-left: 3px solid var(--line);
         border-radius: 8px; padding: 12px 14px; margin-bottom: 9px; background: var(--paper); }
.chunk.cited { border-left-color: var(--neon); }
.chunk .head { display: flex; gap: 9px; align-items: baseline; flex-wrap: wrap; }
.chunk .rank { color: var(--muted); font-variant-numeric: tabular-nums; font-size: 13px; }
.chunk .title { font-weight: 500; }
.chunk .meta { color: var(--muted); font-size: 12.5px; margin: 3px 0 7px; }
.chunk .owner { color: var(--ink); font-weight: 500; }
.chunk p { margin: 0; font-size: 14px; }
.tag { font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase;
       padding: 2px 7px; border-radius: 100px; border: 1px solid var(--line); color: var(--muted); }
.tag.old { background: var(--wash); }
.tag.used { background: var(--neon); border-color: var(--neon); color: var(--paper); }
.cta { border-top: 1px solid var(--line); margin-top: 24px; padding-top: 16px;
  display: flex; gap: 14px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.cta span { color: var(--muted); font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-weight: 500; color: var(--muted); font-size: 11.5px;
     text-transform: uppercase; letter-spacing: 0.05em; padding: 6px 8px; vertical-align: bottom; }
td { padding: 8px; border-top: 1px solid var(--line); font-variant-numeric: tabular-nums;
     vertical-align: top; }
tr.case { cursor: pointer; }
tr.case:hover td, tr.case.open td { background: var(--wash); }
tr.total td { border-top: 2px solid var(--line); font-weight: 600; }
td.q { font-variant-numeric: normal; }
td.q strong { display: block; font-weight: 500; }
td.q strong::before { content: "\\25B8  "; color: var(--muted); }
tr.case.open td.q strong::before { content: "\\25BE  "; }
td.q small { color: var(--muted); display: block; line-height: 1.35; margin-top: 2px; }
td.full { color: var(--good); font-weight: 600; }
td.none { color: var(--good); }
td.bad { color: var(--amaranth); font-weight: 600; }
td.detail { background: var(--wash); padding: 14px 16px 6px; }
.scorecards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 14px;
  max-width: 340px; }
.scorecard { border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.scorecard b { display: block; font-size: 19px; }
.scorecard span { color: var(--muted); font-size: 11px; }
.delta.up { color: #1B7F4B; } .delta.down { color: var(--amaranth); }
aside { border-left: 1px solid var(--line); padding-left: 22px; }
@media (max-width: 900px) { aside { border-left: 0; padding-left: 0; border-top: 1px solid var(--line); padding-top: 22px; } }
aside .intro { color: var(--muted); font-size: 13px; margin: 0 0 12px; }
.principle { border-top: 1px solid var(--line); padding: 11px 0 7px; }
.principle h3 { font-size: 14px; margin: 0 0 3px; }
.principle > p { font-size: 12.5px; color: var(--muted); margin: 0 0 8px; }
.rule { padding: 6px 0; }
.rule b { font-size: 13px; font-weight: 500; display: block; }
.rule p { margin: 2px 0 0; color: var(--muted); font-size: 12.5px; }
.diag { font-size: 12px; color: var(--muted); border-top: 1px solid var(--line);
        margin-top: 18px; padding-top: 12px; }
.empty { color: var(--muted); font-size: 14px; }
"""

PAGE = """<title>Legal Retrieval Lab</title>
<style>%(style)s</style>
<header>
  <h1>Qdrant Legal Retrieval Lab</h1>
  <p class="frame">You run retrieval at a law firm that keeps every client's files in one collection.</p>
</header>
<main>
  <section>
    <div id="askview">
      <div class="field"><select id="case">%(cases)s<option value="">Write your own question</option></select></div>
      <div id="own" hidden>
        <div class="field-row">
          <div class="field"><label for="m">Client file</label><select id="m">%(matters)s</select></div>
          <div class="field"><label for="d">As of</label><input type="date" id="d" value="%(today)s" /></div>
        </div>
        <div class="field"><textarea id="q" placeholder="Ask about this client's contracts"></textarea></div>
        <p class="micro">Your own questions are not scored.</p>
      </div>
      <div id="thread"></div>
      <div class="actions"><button id="go">Ask the Agent</button></div>
      <div id="out"></div>
      <div class="cta">
        <button id="run">Run All %(count)s Cases</button>
      </div>
    </div>
    <div id="boardview" hidden>
      <div class="actions" style="margin:0 0 16px">
        <button class="ghost" id="back">Back</button>
        <button id="rerun">Run Again</button>
        <span class="micro" id="runnote">Open a case to read its chunks.</span>
      </div>
      <div id="cards"></div>
      <table id="board"></table>
      <div id="note"></div>
    </div>
    <div class="diag" id="diag"></div>
  </section>
  <aside>
    <h2>Evidence Playbook</h2>
    <p class="intro">What safe evidence looks like.</p>
    %(rules)s
  </aside>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = t => String(t).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const CASES = %(case_data)s;
const COLUMNS = %(columns)s;
const state = {};   // question_id -> {chunks, agent, running}
let scores = null;

/* ---------- the answer, then what it was built from ---------- */

function bubble(s) {
  if (s.running) return '<div class="msg bot"><span class="who">Agent</span><div class="answer">Answering...</div></div>';
  if (!s.agent) return '';
  if (s.agent.error) return `<div class="msg bot"><span class="who">Agent</span><div class="warn">${esc(s.agent.error)}</div></div>`;
  const marked = esc(s.agent.reply).replace(/\\[(\\d+)\\]/g, (m, n) =>
    `<cite class="${s.agent.cited.includes(+n) ? '' : 'ghosted'}">[${n}]</cite>`);
  const warn = s.agent.invented.length
    ? `<div class="warn">Cites ${s.agent.invented.map(n => '[' + n + ']').join(', ')}, which was never retrieved.</div>`
    : '';
  return `<div class="msg bot"><span class="who">Agent</span>
    <div class="answer">${marked}</div>${warn}</div>`;
}

function chunks(s) {
  const cited = (s.agent && s.agent.cited) || [];
  return s.chunks.map((r, i) => {
    const tags = [];
    if (cited.includes(i + 1)) tags.push('<span class="tag used">cited</span>');
    if (r.superseded) tags.push(`<span class="tag old">superseded ${esc(r.effective_to)}</span>`);
    tags.push(`<span class="tag">${esc(r.instrument_type)}</span>`);
    const klass = cited.includes(i + 1) ? 'cited' : '';
    return `<div class="chunk ${klass}">
      <div class="head"><span class="rank">${i + 1}</span>
      <span class="title">${esc(r.document_title)} s.${esc(r.section_id)}</span>${tags.join(' ')}</div>
      <div class="meta"><span class="owner">${esc(r.client)}</span> &middot; ${esc(r.heading)}
      &middot; in effect from ${esc(r.effective_from)}</div>
      <p>${esc(r.text)}</p></div>`;
  }).join('');
}

function evidence(s) {
  if (!s || !s.chunks) return '';
  if (!s.chunks.length) return '<p class="empty">Nothing came back.</p>';
  return '<div class="evhead"><h3>Chunks returned</h3></div>' + chunks(s);
}

/* ---------- the ask view ---------- */

let view = null;

function picked() {
  const c = CASES[$('#case').value];
  if (c) return {question: c.question, matter_id: c.matter_id, matter_name: c.matter_name,
                 counterparty: c.counterparty, as_of: c.as_of};
  const select = $('#m'), any = Object.values(CASES).find(x => x.matter_id === select.value);
  return {question: $('#q').value.trim(), matter_id: select.value,
          matter_name: select.selectedOptions[0].text,
          counterparty: any ? any.counterparty : '', as_of: $('#d').value};
}

function asked(c) {
  return `<div class="msg user">
    <div class="parties">
      <span><em>Client asking</em>${esc(c.matter_name)}</span>
      <span><em>About their supplier</em>${esc(c.counterparty)}</span>
      <span><em>As of</em>${esc(c.as_of)}</span>
    </div>
    <p>${esc(c.question)}</p></div>`;
}

function render() {
  if (!view) { $('#thread').innerHTML = ''; $('#out').innerHTML = ''; return; }
  $('#thread').innerHTML = asked(view) + bubble(view);
  $('#out').innerHTML = view.error ? `<p class="empty">${esc(view.error)}</p>` : evidence(view);
  $('#go').textContent = view.agent ? 'Ask Again' : 'Ask the Agent';
  $('#go').disabled = !!view.running;
}

$('#case').onchange = () => {
  const c = CASES[$('#case').value];
  $('#own').hidden = !!c;
  view = c ? picked() : null;
  if (!c) $('#q').focus();
  render();
};

$('#go').onclick = async () => {
  const next = picked();
  if (!next.question) return $('#q').focus();
  view = next;
  view.running = true;
  render();
  const d = await (await fetch('/api/ask?answer=1&q=' + encodeURIComponent(view.question)
    + '&m=' + view.matter_id + '&d=' + view.as_of)).json();
  view.running = false;
  if (d.error) view.error = d.error;
  else { view.chunks = d.chunks; view.agent = d.agent; }
  $('#diag').textContent = d.diagnostics || '';
  render();
};

/* ---------- the calibration board ---------- */

function header() {
  return '<tr><th>Case</th>' + COLUMNS.map(c =>
    `<th title="${esc(c[1])}">${esc(c[0])}</th>`).join('') + '</tr>';
}

const COUNTS = ['tenant_leaks', 'temporal_violations', 'duplicate_families'];

function countCells(r) {
  return COUNTS.map(k => `<td class="${r[k] ? 'bad' : 'none'}">${r[k]}</td>`).join('');
}

function cells(id) {
  const r = scores && scores.rows[id];
  if (!r) return COLUMNS.map(() => '<td>&mdash;</td>').join('');
  const was = scores.previous && scores.previous[id];
  const arrow = was !== undefined && was !== null && Math.abs(r.score - was) > 0.5
    ? `<span class="delta ${r.score > was ? 'up' : 'down'}">${
        r.score > was ? '\\u25B2' : '\\u25BC'}</span>` : '';
  return `<td class="${r.score === 100 ? 'full' : ''}"><b>${r.score}</b> ${arrow}</td>`
    + `<td class="${r.found === r.controlling ? 'full' : ''}">${r.found} of ${r.controlling}</td>`
    + `<td>${r.ranking.toFixed(2)}</td>` + countCells(r);
}

function totalRow() {
  if (!scores) return '';
  return `<tr class="total"><td class="q"><strong>All ${
    Object.keys(CASES).length} cases</strong></td>
    <td><b>${scores.score}</b></td><td>${Math.round(scores.coverage * 100)}%%</td>
    <td>${scores.ranking.toFixed(2)}</td>`
    + COUNTS.map(k => `<td class="${scores[k] ? 'bad' : 'none'}">${scores[k]}</td>`).join('')
    + '</tr>';
}

function board() {
  const row = id => `<tr class="case" data-id="${id}"><td class="q">
      <strong>${esc(CASES[id].title)}</strong>${
        CASES[id].probe ? ' <span class="tag">challenge</span>' : ''}
      <small>${esc(CASES[id].matter_name)}, about ${esc(CASES[id].counterparty)}
      &middot; as of ${CASES[id].as_of}</small></td>
    ${cells(id)}</tr>
    <tr class="detail-row" data-for="${id}" hidden><td class="detail" colspan="7"></td></tr>`;
  // One list, the client's cases together, and the two challenges last.
  const ids = Object.keys(CASES).sort((a, b) =>
    (CASES[a].probe ? 1 : 0) - (CASES[b].probe ? 1 : 0)
    || CASES[a].matter_name.localeCompare(CASES[b].matter_name)
    || CASES[a].title.localeCompare(CASES[b].title));
  $('#board').innerHTML = header() + ids.map(row).join('') + totalRow();
  $('#note').innerHTML = '<p class="micro">A challenge case is scored like the rest. '
    + 'Nobody has reached its evidence yet.</p>';
}

function cards() {
  if (!scores) return;
  $('#cards').innerHTML = `<div class="scorecards">
    <div class="scorecard"><b>${scores.score}</b><span>Score out of 100</span></div>
    <div class="scorecard"><b>${scores.solved}/${scores.questions}</b><span>Cases Solved</span></div>
  </div><p class="micro">An unscoped search returns a slightly different set each run, so the
  starter's score moves a point or two on its own.</p>`;
}

function paint(id) {
  const cell = document.querySelector(`tr.detail-row[data-for="${id}"] td`);
  if (!cell) return;
  const s = state[id] || {};
  cell.innerHTML = s.error ? `<p class="empty">${esc(s.error)}</p>`
    : (s.chunks ? asked(CASES[id]) + evidence(s)
      : '<p class="empty">Retrieving...</p>');
}

async function load(id) {
  state[id] = {};
  paint(id);
  const d = await (await fetch('/api/ask?case=' + encodeURIComponent(id))).json();
  state[id] = d.error ? {error: d.error} : {chunks: d.chunks};
  $('#diag').textContent = d.diagnostics || $('#diag').textContent;
  paint(id);
}

document.addEventListener('click', e => {
  const row = e.target.closest('tr.case');
  if (!row) return;
  const id = row.dataset.id;
  const detailRow = document.querySelector(`tr.detail-row[data-for="${id}"]`);
  detailRow.hidden = !detailRow.hidden;
  row.classList.toggle('open', !detailRow.hidden);
  if (!detailRow.hidden && !state[id]) load(id);
});

async function runAll(button) {
  const started = Date.now();
  button.disabled = true;
  const timer = setInterval(() => {
    $('#runnote').textContent = `Scoring ${Object.keys(CASES).length} cases \\u00B7 ${Math.floor((Date.now() - started) / 1000)}s`;
  }, 1000);
  const d = await (await fetch('/api/score')).json();
  clearInterval(timer);
  button.disabled = false;
  $('#runnote').textContent = d.error || 'Open a case to read its chunks.';
  if (d.error) return;
  scores = d;
  $('#diag').textContent = d.diagnostics || '';
  cards();
  board();
}

$('#run').onclick = e => {
  $('#askview').hidden = true;
  $('#boardview').hidden = false;
  runAll(e.target);
};
$('#rerun').onclick = e => runAll(e.target);
$('#back').onclick = () => { $('#boardview').hidden = true; $('#askview').hidden = false; };

$('#case').onchange();
board();
</script>
"""


def diagnostics(qc, name):
    """Explain what the code executed, never whether the answers are right."""
    return f"Qdrant {qc.info().version}. {representations(qc, name)}."


CASES = {
    x["question_id"]: {
        "title": CASE_TITLES.get(x["question_id"], x["question_id"]),
        "question": x["question"],
        "matter_id": x["matter_id"],
        "matter_name": MATTERS[x["matter_id"]]["name"],
        "counterparty": MATTERS[x["matter_id"]]["counterparty"],
        "as_of": x["as_of"],
        "probe": x["question_id"] in CHALLENGE_IDS,
    }
    for x in CALIBRATION
}

def _order(item):
    """Sort key. A challenge sits at the end of every list it appears in."""
    qid, case = item
    return (case["probe"], case["matter_name"], case["title"])


PAYLOAD_FIELDS = (
    "document_title", "section_id", "heading", "text", "instrument_type",
    "effective_from", "effective_to",
)


class Handler(http.server.BaseHTTPRequestHandler):
    qc = None
    name = None

    def log_message(self, *args):
        pass

    def send(self, payload, kind="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Every path answers with a body. A dropped connection leaves the page
        waiting on a promise that never resolves, and says nothing on screen."""
        route = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(route.query)
        try:
            if route.path == "/":
                return self.send(self.index(), "text/html")
            if route.path == "/api/ask":
                return self.send(self.ask(query))
            if route.path == "/api/score":
                return self.send(self.score())
        except Exception as exc:
            return self.send({"error": f"{type(exc).__name__}: {exc}"})
        self.send_error(404)

    def index(self):
        rules = "".join(
            '<section class="principle">'
            f"<h3>{html.escape(title)}</h3><p>{html.escape(summary)}</p>"
            + "".join(
                f'<div class="rule"><b>{html.escape(rule_title)}</b>'
                f"<p>{html.escape(body)}</p></div>"
                for rule_title, body in items
            )
            + "</section>"
            for title, summary, items in SECTIONS
        )
        matters = "".join(
            f'<option value="{k}">{v["name"]}</option>' for k, v in MATTERS.items()
        )
        cases = "".join(
            f'<option value="{html.escape(qid)}">{html.escape(case["title"])}</option>'
            for qid, case in sorted(CASES.items(), key=_order)
        )
        return (PAGE % {
            "style": STYLE,
            "rules": rules,
            "columns": json.dumps(COLUMNS),
            "case_data": json.dumps(CASES).replace("</", "<\\/"),
            "cases": cases,
            "matters": matters,
            "today": datetime.date.today().isoformat(),
            "count": len(CASES),
        }).encode()

    def ask(self, query):
        """Retrieve for one case or one typed question, and optionally answer it."""
        one = lambda key, default=None: (query.get(key) or [default])[0]
        case = CASES.get(one("case", ""))
        if case:
            question, matter, as_of = case["question"], case["matter_id"], case["as_of"]
        else:
            question = (one("q", "") or "").strip()
            matter, as_of = one("m", "harbor"), one("d", "2026-01-20")
            if not question:
                return {"error": "Type a question."}
            if matter not in MATTERS:
                return {"error": "Unknown client matter."}
        try:
            points = lab().retrieve(self.qc, self.name, question, matter, as_of)
        except RuntimeError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"lab.py raised: {type(exc).__name__}: {exc}"}

        payload = {
            "chunks": [
                dict(
                    {k: p.payload[k] for k in PAYLOAD_FIELDS},
                    client=client_name(p.payload),
                    superseded=p.payload["effective_to"] != "9999-12-31",
                )
                for p in points
            ],
            "diagnostics": diagnostics(self.qc, self.name),
        }
        if one("answer"):
            try:
                reply, cited, invented = agent.answer(points, question, matter, as_of)
                payload["agent"] = {"reply": reply, "cited": cited, "invented": invented}
            except RuntimeError as exc:
                payload["agent"] = {"error": str(exc)}
        return payload

    def score(self):
        try:
            current = lab()
            run = lambda q, m, d: [
                p.payload for p in current.retrieve(self.qc, self.name, q, m, d, limit=K)
            ]
            result = score_all(CALIBRATION, run, k=K)
        except RuntimeError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"lab.py raised: {type(exc).__name__}: {exc}"}

        keep = ("score", "coverage", "found", "controlling", "ranking", "tenant_leaks",
                "temporal_violations", "duplicate_families")
        previous = remember(result)
        payload = {
            "rows": {r["question_id"]: {k: r[k] for k in keep} for r in result["rows"]},
            "score": result["score"],
            "solved": result["solved"], "questions": result["questions"],
            "coverage": result["coverage"], "ranking": result["ranking"],
            "tenant_leaks": result["tenant_leaks"],
            "temporal_violations": result["temporal_violations"],
            "duplicate_families": result["duplicate_families"],
            "diagnostics": diagnostics(self.qc, self.name),
        }
        if previous:
            payload["previous"] = previous
        return payload


def main():
    Handler.qc, Handler.name = connect(), collection()
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        raise SystemExit(
            f"Port {PORT} is busy. Run: PORT={PORT + 1} uv run python -m workshop.app"
        )
    with server:
        print(f"Legal Retrieval Lab on http://localhost:{PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()

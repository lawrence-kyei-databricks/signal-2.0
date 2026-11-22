"""Export executed notebook outputs to evidence/notebooks/*.md as plain text.

The FE Bar evaluator reads text only, so every cell's printed output and displayed tables are written as
markdown. Identifying values (emails, workspace host, Salesforce domain, personal role names) are scrubbed.

Run from the repo root on Databricks:  python scripts/export_evidence.py
"""
import base64, html, json, os, re, sys
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ExportFormat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOKS = {   # repo path -> evidence title
    "01_data/03_govern_unity_catalog": "Unity Catalog: classification, lineage, grants, model registry",
    "02_ml/01_build_training_history": "ML: synthetic training history anchored to real account levels",
    "02_ml/02_train_risk_model": "ML: training, out-of-time validation, drift check, gated promotion",
    "02_ml/03_score_and_brief": "ML + Gen AI: scoring, AI briefings, Salesforce writeback, Lakebase and metric view refresh",
    "04_lakebase_app/01_lakebase_setup": "Lakebase: operational schema, synced tables, app queries, latency",
    "04_lakebase_app/02_app_grants": "Lakebase: least-privilege grants for the app service principal",
}
MAX_ROWS = 30
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SCRUB = [
    (re.compile(r"[A-Za-z0-9._%+-]+@databricks\.com"), "<redacted-email>"),
    (re.compile(r"https://[A-Za-z0-9.-]+\.azuredatabricks\.net[^\s)]*"), "<workspace-url>"),
    (re.compile(r"[A-Za-z0-9-]+\.database\.[a-z0-9]+\.azuredatabricks\.net"), "<lakebase-host>"),
    (re.compile(r"[A-Za-z0-9-]+\.(?:develop\.)?my\.salesforce\.com"), "<redacted-salesforce-domain>"),
    (re.compile(r"[A-Za-z0-9-]+\.(?:develop\.)?lightning\.force\.com"), "<redacted-salesforce-domain>"),
    (re.compile(r"/Users/[^/\s]+@[^/\s]+"), "/Users/<redacted-email>"),
    (re.compile(r"\blawrence-kyei\b"), "<user-role>"),
]


def scrub(text):
    text = ANSI.sub("", text)
    for pat, rep in SCRUB:
        text = pat.sub(rep, text)
    return text


def html_table_to_md(markup):
    """Convert the HTML table Databricks emits for display() into a markdown table."""
    heads = [html.unescape(re.sub("<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", markup, re.S)]
    rows = [[html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            for r in re.findall(r"<tr>(.*?)</tr>", markup, re.S) if "<td" in r]
    if not heads:
        return None
    out = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    out += ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows[:MAX_ROWS]]
    out.append(f"\n({len(rows)} rows" + (f", first {MAX_ROWS} shown)" if len(rows) > MAX_ROWS else ")"))
    return "\n".join(out)


def text_of(value):
    return "".join(value) if isinstance(value, list) else (value or "")


def export(w, rel_path, title):
    ws_path = os.path.join(REPO, rel_path).replace("/Workspace", "", 1)
    nb = json.loads(base64.b64decode(w.workspace.export(ws_path, format=ExportFormat.JUPYTER).content))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Run evidence: {title}", "",
             f"Source notebook: `{rel_path}`. Outputs exported {stamp} from the executed notebook "
             "(no images; tables and logs as text).", ""]
    n_out = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code" or not cell.get("outputs"):
            continue
        meta = cell.get("metadata", {}).get("application/vnd.databricks.v1+cell", {})
        blocks = []
        for o in cell["outputs"]:
            kind = o.get("output_type")
            if kind == "stream":
                t = scrub(text_of(o.get("text"))).strip()
                if t and "you may need to restart the kernel" not in t:
                    blocks.append("```text\n" + t + "\n```")
            elif kind in ("display_data", "execute_result"):
                data = o.get("data", {})
                md = html_table_to_md(text_of(data.get("text/html"))) if "text/html" in data else None
                if md:
                    blocks.append(scrub(md))
                elif "text/plain" in data and "application/vnd.jupyter.widget-view+json" not in data:
                    t = scrub(text_of(data["text/plain"])).strip()
                    if t:
                        blocks.append("```text\n" + t + "\n```")
            elif kind == "error":
                blocks.append("```text\nERROR: " + scrub(o.get("ename", "") + ": " + o.get("evalue", "")) + "\n```")
        if blocks:
            n_out += 1
            lines += [f"## {meta.get('title') or 'Cell output'}", ""] + [b + "\n" for b in blocks]
    target = os.path.join(REPO, "evidence", "notebooks", rel_path.replace("/", "__") + ".md")
    with open(target, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return target, n_out


if __name__ == "__main__":
    w = WorkspaceClient()
    for rel, title in NOTEBOOKS.items():
        path, n = export(w, rel, title)
        print(f"{rel:40s} -> {os.path.relpath(path, REPO)} ({n} cells with output)")
    sys.exit(0)

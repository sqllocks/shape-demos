# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "jupyter",
# META     "jupyter_kernel_name": "python3.12"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "<lakehouse-id>",
# META       "default_lakehouse_name": "shape_demo",
# META       "default_lakehouse_workspace_id": "<workspace-id>",
# META       "known_lakehouses": [
# META         {
# META           "id": "<lakehouse-id>"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Shape finale: profile a day's load, gate it, keep the history
# 
# `layer = "lakehouse"`: reads the day from `finale_order_landing` (what the pipeline's Copy just loaded), profiles it,
# checks the normal contract, diffs it against the same weekday a week earlier, appends the day to `finale_order`
# (bronze history), writes the metrics to `shape_profile_history` and any findings to `shape_findings`, saves the
# `.shape` artifact and commits its **share-safe** form to Git.
# 
# `layer = "warehouse"`: reads the same day from the Warehouse table, does the same, and also reconciles it against
# the lakehouse profile of that day, which catches a load defect that row counts miss.
# 
# `mode = "backfill"`: does all of that for every day in the table at once (history seeding).

# CELL ********************

# MAGIC %%configure
# MAGIC {"vCores": 8}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

%pip install "sqllocks-shape[domains,excel]==0.9.3"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# PARAMETERS CELL ********************

# Parameters cell
loadDate = "2026-10-06"
layer = "lakehouse"            # "lakehouse" or "warehouse"
mode = "day"                   # "day" or "backfill"
contractPath = "/lakehouse/default/Files/contracts/finale_orders.json"
workspace = "<workspace-name>"
lakehouse = "shape_demo"
warehouse = "shape_wh"
commitToGit = True
gitRepo = "<owner>/<profiles-repo>"
vaultUrl = "https://<your-key-vault>.vault.azure.net/"
secretName = "<your-secret-name>"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

# Finale profiling core. Uses only public Shape APIs.
import datetime as dt, json, warnings
import pyarrow as pa, pyarrow.compute as pc
import shape
from shape.privacy.safe_profile import SafeConfig, to_safe_profile

IGNORE = {"order_id", "promotion_id", "load_date"}   # ids: new values every day by design
SEVERE = ("medium", "high")

def day_table(t: pa.Table, day: str) -> pa.Table:
    col = t.column("load_date")
    if pa.types.is_dictionary(col.type):
        col = col.cast(pa.string())
    return t.filter(pc.equal(col.cast(pa.string()), day)).drop_columns(["load_date"])

def profile_day(t: pa.Table, name: str = "order"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return shape.profile(t, name=name)

def findings(baseline, current) -> list[dict]:
    if baseline is None:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = shape.diff(baseline, current)
    return [c for c in d.changes if c.get("severity") in SEVERE and c.get("column") not in IGNORE]

def metrics(prof, t: pa.Table, day: str, layer: str) -> list[dict]:
    s = prof.summary()
    rows = [dict(load_date=day, layer=layer, column="(table)", metric="row_count", value=float(s["row_count"]))]
    for col, c in s["columns"].items():
        if col in IGNORE:
            continue
        for m in ("null_rate", "mean", "std", "cardinality"):
            if isinstance(c.get(m), (int, float)):
                rows.append(dict(load_date=day, layer=layer, column=col, metric=m, value=float(c[m])))
    if "status" in t.column_names:                       # category mix, straight from the data
        vc = pc.value_counts(t.column("status")).to_pylist()
        n = max(t.num_rows, 1)
        for v in vc:
            rows.append(dict(load_date=day, layer=layer, column="status", metric=f"share:{v['values']}", value=v["counts"] / n))
    return rows

def finding_rows(fs: list[dict], day: str, layer: str, baseline_day: str | None) -> list[dict]:
    return [dict(load_date=day, layer=layer, baseline_date=baseline_day or "", column=str(f.get("column")),
                 kind=str(f.get("kind")), severity=str(f.get("severity")),
                 baseline=json.dumps(f.get("baseline"), default=str)[:400],
                 current=json.dumps(f.get("current"), default=str)[:400]) for f in fs]

def safe_json(prof) -> str:
    return to_safe_profile(prof, SafeConfig(k=5)).to_json()

def baseline_day(day: str) -> str:
    return (dt.date.fromisoformat(day) - dt.timedelta(days=7)).isoformat()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

import base64, datetime as dt, json, os, time
from pathlib import Path
import pyarrow as pa, pyarrow.compute as pc
from deltalake import DeltaTable, write_deltalake

LOCAL = os.environ.get("FINALE_LOCAL")            # set only by the local test harness
if LOCAL:
    BASE, FILES, OPTS = LOCAL, f"{LOCAL}/Files", None
    LH_TABLES, WH_TABLES = f"{LOCAL}/Tables", f"{LOCAL}/wh"
else:
    import notebookutils
    OPTS = {"bearer_token": notebookutils.credentials.getToken("storage"), "use_fabric_endpoint": "true"}
    ONELAKE = f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com"
    LH_TABLES = f"{ONELAKE}/{lakehouse}.Lakehouse/Tables"   # write Delta through OneLake, not the mount
    WH_TABLES = f"{ONELAKE}/{warehouse}.Warehouse/Tables/dbo"
    FILES = "/lakehouse/default/Files"

def read_delta(uri):
    return DeltaTable(uri, storage_options=OPTS).to_pyarrow_table()

def upsert(uri, rows: pa.Table, dates: list[str], extra_pred: str = ""):
    """Delete the given load dates (and layer), then append: a rerun never doubles a day."""
    try:
        dtb = DeltaTable(uri, storage_options=OPTS)
    except Exception:                                    # first write: the table does not exist yet
        write_deltalake(uri, rows, mode="append", storage_options=OPTS)
        return
    quoted = ", ".join(f"'{d}'" for d in dates)
    dtb.delete(f"{DATE_COL[uri]} IN ({quoted})" + (f" AND {extra_pred}" if extra_pred else ""))
    write_deltalake(uri, rows, mode="append", storage_options=OPTS)

DATE_COL = {}
def with_date_col(uri, col):
    DATE_COL[uri] = col
    return uri

def git_commit(path_in_repo: str, content: str, message: str) -> str:
    """Commit one file to GitHub. Paced (GitHub allows about 80 content writes a minute) and retried once on a limit."""
    import requests
    token = notebookutils.credentials.getSecret(vaultUrl, secretName)
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{gitRepo}/contents/{path_in_repo}"
    for attempt in range(3):
        r = requests.get(url, headers=h, timeout=30)
        sha = r.json().get("sha") if r.status_code == 200 else None
        body = {"message": message, "content": base64.b64encode(content.encode()).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=h, json=body, timeout=30)
        if r.status_code in (403, 409, 429) and attempt < 2:      # rate limit or a racing sha: wait and retry
            time.sleep(int(r.headers.get("retry-after", 60)) if r.status_code != 409 else 2)
            continue
        r.raise_for_status()
        time.sleep(1.0)
        return r.json()["commit"]["html_url"]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

t0 = time.time()
ID_COLS = ("order_id", "customer_id", "store_id", "shipping_address_id", "promotion_id")

def normalize(t: pa.Table) -> pa.Table:
    """Compare values, not engine types: the same logical types on both layers."""
    want = {**{c: pa.int64() for c in ID_COLS}, "order_date": pa.timestamp("us"), "status": pa.string(),
            "order_total": pa.float64(), "load_date": pa.string()}
    cols = []
    for name in t.column_names:
        col = t.column(name)
        if name in want and col.type != want[name]:
            if pa.types.is_timestamp(col.type) and col.type.tz is not None:
                col = pc.cast(col, pa.timestamp(col.type.unit, tz="UTC")).cast(pa.timestamp("us", tz="UTC"))
                col = pa.chunked_array([c.view(pa.timestamp("us")) for c in col.chunks], pa.timestamp("us"))
            else:
                col = pc.cast(col, want[name])
        cols.append(col)
    return pa.table(cols, names=t.column_names)

if layer == "lakehouse":
    src = with_date_col(f"{LH_TABLES}/finale_order_landing", "load_date")
    raw = read_delta(src)
else:  # the Warehouse, read through its own SQL engine (its Delta files use deletion vectors + column mapping)
    src = f"{warehouse}.dbo.finale_order"
    where = "" if mode == "backfill" else f" WHERE load_date = '{loadDate}'"
    if LOCAL:
        raw = read_delta(f"{WH_TABLES}/finale_order")
    else:
        conn = notebookutils.data.connect_to_artifact(warehouse)
        raw = pa.Table.from_pandas(conn.query(f"SELECT * FROM dbo.finale_order{where}"), preserve_index=False)
norm = normalize(raw)   # for profiling only; raw keeps its stored types for the bronze table
all_days = sorted(set(norm.column("load_date").to_pylist()))
days = all_days if mode == "backfill" else [str(loadDate)]
art = Path(FILES) / "shape" / "finale" / layer / "order"
art.mkdir(parents=True, exist_ok=True)
lh_art = Path(FILES) / "shape" / "finale" / "lakehouse" / "order"
M, F, out = [], [], []
for d in days:
    t = day_table(norm, d)
    if t.num_rows == 0:
        raise ValueError(f"no rows for load_date {d} in {src}")
    prof = profile_day(t)
    violations = list(shape.check(prof, contractPath).violations)
    b = baseline_day(d)
    base = shape.load(str(art / f"{b}.shape")) if (art / f"{b}.shape").exists() else None
    fs = findings(base, prof)
    fr = finding_rows(fs, d, layer, b if base is not None else None)
    if layer == "warehouse" and (lh_art / f"{d}.shape").exists():   # the same day, one layer up
        rec = findings(shape.load(str(lh_art / f"{d}.shape")), prof)
        fr += [dict(r, baseline_date=f"lakehouse {d}", kind="reconcile:" + r["kind"]) for r in finding_rows(rec, d, layer, d)]
    shape.save(prof, str(art / f"{d}.shape"))
    M += metrics(prof, t, d, layer)
    F += fr
    out.append({"loadDate": d, "rows": t.num_rows, "contractPassed": not violations, "violations": violations[:20],
                "findingCount": len(fr), "findings": [f"{r['column']}: {r['kind']} ({r['severity']})" for r in fr][:20]})
    if commitToGit and not LOCAL:
        out[-1]["gitCommit"] = git_commit(f"profiles/{layer}/order.safe.json", safe_json(prof),
                                          f"{layer} order {d}: {len(fr)} finding(s), contract {'pass' if not violations else 'FAIL'}")
print(f"profiled {len(days)} day(s) in {time.time()-t0:.1f}s")

# The promotions workbook that arrived the same day: Shape reads the .xlsx itself, before anything loads it
if layer == "lakehouse":
    import glob as _glob
    wb_art = Path(FILES) / "shape" / "finale" / "lakehouse" / "promotion"
    wb_art.mkdir(parents=True, exist_ok=True)
    landing = os.environ.get("FINALE_LANDING") or "/lakehouse/default/Files/shape-landing"
    def _workbook(day):
        hits = sorted(_glob.glob(f"{landing}/promotion/ingest_date={day}/*.xlsx"))
        return shape.profile(f"{hits[0]}#promotion") if hits else None
    def _kinds(p):
        return {(f["kind"], f.get("column")) for f in (p.summary().get("findings") or [])} if p is not None else set()
    for o in out:
        d = o["loadDate"]
        wp = _workbook(d)
        if wp is None:
            o["workbook"] = "missing"
            continue
        shape.save(wp, str(wb_art / f"{d}.shape"))
        bp = _workbook(baseline_day(d))
        found = wp.summary().get("findings") or []
        new = [f for f in found if bp is not None and (f["kind"], f.get("column")) not in _kinds(bp)]
        drift = [c for c in findings(bp, wp) if c.get("column") != "load_date"] if bp is not None else []
        rows = [dict(load_date=d, layer=layer, baseline_date=baseline_day(d), column=f"promotion.{f.get('column')}",
                     kind="excel:" + f["kind"], severity="high", baseline="",
                     current=json.dumps({k: f.get(k) for k in ("count", "cells", "examples")}, default=str)[:400]) for f in new]
        rows += [dict(r, column="promotion." + r["column"]) for r in finding_rows(drift, d, layer, baseline_day(d))]
        F += rows
        M += [dict(load_date=d, layer=layer, column="(promotion workbook)", metric="excel_findings", value=float(len(found))),
              dict(load_date=d, layer=layer, column="(promotion workbook)", metric="row_count", value=float(wp.summary()["row_count"]))]
        o["workbookFindings"] = [f"{r['column']}: {r['kind']}" for r in rows][:20]
        o["findingCount"] += len(rows)
        o["findings"] = (o["findings"] + o["workbookFindings"])[:20]
    print(f"workbooks checked in {time.time()-t0:.1f}s (cumulative)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

t1 = time.time()
hist = with_date_col(f"{LH_TABLES}/shape_profile_history", "load_date")
upsert(hist, pa.Table.from_pylist(M), days, f"layer = '{layer}'")
fnd = with_date_col(f"{LH_TABLES}/shape_findings", "load_date")
if F:
    upsert(fnd, pa.Table.from_pylist(F), days, f"layer = '{layer}'")
else:                                         # a clean rerun clears the day's earlier findings too
    try:
        quoted = ", ".join(f"'{d}'" for d in days)
        DeltaTable(fnd, storage_options=OPTS).delete(f"load_date IN ({quoted}) AND layer = '{layer}'")
    except Exception as exc:
        if "not" not in str(exc).lower() and "no files" not in str(exc).lower():
            raise
if layer == "lakehouse":                      # bronze history: every day that landed, gated or not
    bronze = with_date_col(f"{LH_TABLES}/finale_order", "load_date")
    upsert(bronze, raw.filter(pc.is_in(raw.column("load_date"), pa.array(days))), days)
print(f"history tables written in {time.time()-t1:.1f}s")
last = out[-1]
result = {"layer": layer, "mode": mode, "days": len(days), "loadDate": last["loadDate"], "rows": last["rows"],
          "contractPassed": last["contractPassed"], "findingCount": last["findingCount"],
          "passed": bool(last["contractPassed"] and last["findingCount"] == 0),
          "findings": last["findings"], "violations": last["violations"], "gitCommit": last.get("gitCommit")}
print(json.dumps(result, indent=2, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

import notebookutils
notebookutils.notebook.exit(json.dumps(result, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

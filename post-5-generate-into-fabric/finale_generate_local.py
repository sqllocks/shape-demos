"""finale_generate, run locally on Shape 0.9.3 (SQLBites "Shape in practice", post 5).

The code cell below is copied unchanged from the Fabric notebook in notebook/finale_generate.notebook.py.
Only these lines differ from the notebook:
  - the %%configure and %pip cells are dropped (packages come from the local venv: Shape 0.9.3 from PyPI);
  - the parameters point at local folders instead of /lakehouse/default/Files/...;
  - the last cell (notebookutils.notebook.exit) is replaced by print(json.dumps(result)).
Usage: python finale_generate_local.py OUT_DIR [BATCH_DATE] [chaos 0|1]
"""
import sys
OUT = sys.argv[1]
batchDate = sys.argv[2] if len(sys.argv) > 2 else "2026-10-07"
chaos = (sys.argv[3] != "0") if len(sys.argv) > 3 else True
workbooksThrough = ""
landingRoot = f"{OUT}/shape-landing"
truthDir = f"{OUT}/shape/finale/chaos"

# ---- notebook code cell, unchanged ----
import datetime as dt, json, os, random, time, warnings
import numpy as np, pyarrow as pa, openpyxl
from shape.cli.generation import load_target
from shape.generation.batches import BatchGenerator
from shape.generation.drift_plan import DriftPlan
from shape.generation.landing import write_landing
from shape.chaos.groundtruth import Corruption, corrupt_tables, write_ground_truth
from shape.integrations.fabric import generation
from shape.builtins.sinks.workbook import write_workbook
warnings.simplefilter("ignore")

START, GEN_START, SEED = dt.date(2026, 7, 8), dt.date(2026, 4, 1), 42
MAX_ROWS = {"customer": 200, "order": 4200, "order_line": 10500}
SALE = (dt.date(2026, 8, 29), dt.date(2026, 9, 8))
PLAN = DriftPlan.from_dict(json.loads("""{"start": "2026-07-08", "days": 92, "events": [{"id": "basket_growth", "kind": "distribution", "table": "order_line", "column": "quantity", "start": "2026-07-20", "ramp_days": 60, "params": {"p": {"set": 0.5}}}, {"id": "returns_creep", "kind": "category_weights", "table": "order", "column": "status", "start": "2026-08-15", "ramp_days": 40, "weights": {"completed": 0.71, "shipped": 0.08, "processing": 0.02, "cancelled": 0.05, "returned": 0.14}}, {"id": "labor_day_sale", "kind": "null_rate", "table": "order", "column": "promotion_id", "start": "2026-08-29", "end": "2026-09-09", "ramp_days": 2, "to": 0.35}, {"id": "loyalty_upgrade", "kind": "category_weights", "table": "customer", "column": "loyalty_tier", "start": "2026-09-01", "ramp_days": 30, "weights": {"Basic": 0.45, "Silver": 0.28, "Gold": 0.17, "Platinum": 0.1}}]}"""))
CHAOS = ["orphan_keys=0.03@order.customer_id",
         "date_shift=0.05@order.order_date:days=10,direction=early",
         "null_creep=0.15@order.store_id",
         "duplicates=0.02@order_line"]

def volume(day):
    i = (day - START).days
    growth = 1800 * (1 + 0.20 * i / 90)
    weekly = {0: 0.92, 1: 0.90, 2: 0.95, 3: 1.00, 4: 1.12, 5: 1.22, 6: 1.08}[day.weekday()]
    sale = 1.35 if SALE[0] <= day <= SALE[1] else 1.0
    return growth * weekly * sale * np.random.default_rng([SEED, i]).normal(1.0, 0.05)

PROMO = generation.generate_domain("retail", scale="small", seed=SEED).tables["promotion"]   # marketing's reference list

def write_promotions(day, edited):
    """The promotions workbook marketing sends every day; edited=True is someone's hand edits on the chaos day."""
    t = PROMO.append_column("promo_code", pa.array([f"{i:05d}" for i in PROMO.column("promotion_id").to_pylist()]))
    t = t.append_column("load_date", pa.array([day] * t.num_rows, pa.date32()))
    folder = f"{landingRoot}/promotion/ingest_date={day}"
    os.makedirs(folder, exist_ok=True)
    path = f"{folder}/promotions_{day:%Y%m%d}.xlsx"
    write_workbook(path, {"promotion": t}, meta={"domain": "retail", "seed": SEED},
                   identifier_columns_by_table={"promotion": ["promo_code"]})
    edits = {}
    if edited:
        wb = openpyxl.load_workbook(path)
        ws = wb["promotion"]
        col = {c.value: c.column_letter for c in ws[1]}
        rng = random.Random(7)
        rows = list(range(2, ws.max_row + 1))
        edits["promo_code_as_number"] = rng.sample(rows, 15)
        for r in edits["promo_code_as_number"]:
            c = ws[f"{col['promo_code']}{r}"]; c.value = int(c.value); c.number_format = "General"
        edits["discount_ref_error"] = rng.sample(rows, 3)
        for r in edits["discount_ref_error"]:
            c = ws[f"{col['discount_pct']}{r}"]; c.value = "#REF!"; c.data_type = "e"
        edits["end_date_9999"] = rng.sample(rows, 6)
        for r in edits["end_date_9999"]:
            ws[f"{col['end_date']}{r}"].value = dt.datetime(9999, 12, 31)
        edits["start_date_as_text"] = rng.sample(rows, 4)
        for r in edits["start_date_as_text"]:
            c = ws[f"{col['start_date']}{r}"]; c.value = c.value.strftime("%m/%d/%Y"); c.number_format = "@"
        edits["hidden_column"] = ["promo_type"]
        ws.column_dimensions[col["promo_type"]].hidden = True
        wb.save(path)
    return path, t.num_rows, edits

t0 = time.time()
day = dt.date.fromisoformat(str(batchDate))
if workbooksThrough:                                   # one-time: the workbook history only
    last, n = dt.date.fromisoformat(str(workbooksThrough)), 0
    while day <= last:
        write_promotions(day, False); n += 1; day += dt.timedelta(days=1)
    print(f"{n} promotions workbook(s) written in {time.time()-t0:.1f}s")
    result = {"workbooks": n, "seconds": round(time.time() - t0, 2)}
else:
    schema = PLAN.schema_at(load_target("retail", None), day)
    gen = BatchGenerator(schema, MAX_ROWS, start_date=GEN_START, seed=SEED, date_columns={"order": "order_date"})
    tables = dict(gen.generate(day).tables)
    frac = min(1.0, volume(day) / MAX_ROWS["order"])
    rng = np.random.default_rng([SEED, (day - START).days, 1])
    for name in ("order", "order_line", "customer"):
        tables[name] = tables[name].filter(pa.array(rng.random(tables[name].num_rows) < frac))
    if chaos:
        res = corrupt_tables(tables, [Corruption.parse(s) for s in CHAOS], seed=7, batch=(day - START).days)
        tables = dict(res.tables)
        os.makedirs(truthDir, exist_ok=True)
        write_ground_truth(f"{truthDir}/_chaos_ground_truth_{day:%Y%m%d}.jsonl", res)
    for name in tables:                      # the load date travels inside every file, not only in its folder name
        tables[name] = tables[name].append_column("load_date", pa.array([str(day)] * tables[name].num_rows, pa.string()))
    landed = write_landing(tables, landingRoot, default_format="parquet", batch_date=day, formats={"customer": "csv"})
    wb_path, wb_rows, edits = write_promotions(day, bool(chaos))
    if edits:
        os.makedirs(truthDir, exist_ok=True)
        with open(f"{truthDir}/_excel_edits_{day:%Y%m%d}.json", "w") as fh:
            json.dump(edits, fh, indent=1)
    elapsed = time.time() - t0
    for f in landed:
        print(f"  {f.table:<11} {f.rows:>6,} rows  {f.format:<8} shape-landing{str(f.path).split('shape-landing', 1)[-1]}")
    print(f"  {'promotion':<11} {wb_rows:>6,} rows  {'xlsx':<8} shape-landing{wb_path.split('shape-landing', 1)[-1]}"
          + (f"   hand edits: {', '.join(edits)}" if edits else ""))
    print(f"{'CHAOS ' if chaos else ''}day {day} written in {elapsed:.1f}s")
    result = {"batchDate": str(day), "chaos": bool(chaos),
              "files": [{"table": f.table, "rows": f.rows} for f in landed] + [{"table": "promotion", "rows": wb_rows}],
              "seconds": round(elapsed, 2)}
# ---- end of notebook code cell ----

print(json.dumps(result))

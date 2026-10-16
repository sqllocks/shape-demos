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

# CELL ********************

# Parameters cell
keepThrough = "2026-10-06"   # keep every day up to and including this date; remove everything after it
dryRun = True                 # True: only list what would be removed. Set False to remove it.

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

# Reset the finale to the state "history through keepThrough": removes later days from ADLS, the lakehouse tables,
# the .shape artifacts and the chaos answer keys. The warehouse is only checked (later days never reach it unless
# they passed the lakehouse gate; a rerun of a day replaces it there anyway).
import glob, os, re, shutil, datetime as dt
LOCAL = os.environ.get("FINALE_LOCAL")
FILES = f"{LOCAL}/Files" if LOCAL else "/lakehouse/default/Files"
LANDING = os.environ.get("FINALE_LANDING") or f"{FILES}/shape-landing"
dt.date.fromisoformat(keepThrough)                      # refuse a malformed date
from deltalake import DeltaTable
if LOCAL:
    OPTS, TABLES = None, f"{LOCAL}/Tables"
else:
    import notebookutils
    OPTS = {"bearer_token": notebookutils.credentials.getToken("storage"), "use_fabric_endpoint": "true"}
    TABLES = "abfss://<workspace-name>@onelake.dfs.fabric.microsoft.com/<lakehouse-name>.Lakehouse/Tables"
verb = "would remove" if dryRun else "removed"

# 1. landing files (ADLS through the shortcut): one folder per table per day
folders = [p for p in glob.glob(f"{LANDING}/*/ingest_date=*") if p.rsplit("=", 1)[1][:10] > keepThrough]
for p in sorted(folders):
    if not dryRun:
        shutil.rmtree(p)
print(f"landing: {verb} {len(folders)} day folder(s)", sorted({p.rsplit('=', 1)[1][:10] for p in folders}))

# 2. .shape artifacts and chaos answer keys
files = [p for p in glob.glob(f"{FILES}/shape/finale/*/*/*.shape") if os.path.basename(p)[:10] > keepThrough]
for p in glob.glob(f"{FILES}/shape/finale/chaos/*"):
    m = re.search(r"_(\d{8})\.", os.path.basename(p))
    if m and dt.datetime.strptime(m.group(1), "%Y%m%d").date().isoformat() > keepThrough:
        files.append(p)
for p in files:
    if not dryRun:
        os.remove(p)
print(f"artifacts: {verb} {len(files)} file(s)")

# 3. lakehouse Delta tables
for name in ("shape_profile_history", "shape_findings", "finale_order"):
    try:
        t = DeltaTable(f"{TABLES}/{name}", storage_options=OPTS)
    except Exception:
        print(f"{name}: not there, skipped"); continue
    n = sum(1 for d in t.to_pyarrow_table(columns=["load_date"]).column("load_date").to_pylist() if str(d) > keepThrough)
    if n and not dryRun:
        t.delete(f"load_date > '{keepThrough}'")
    print(f"{name}: {verb} {n} row(s)")

# 4. warehouse: check only
if not LOCAL:
    conn = notebookutils.data.connect_to_artifact("shape_wh")
    later = conn.query(f"SELECT COUNT(*) AS n FROM dbo.finale_order WHERE load_date > '{keepThrough}'").iloc[0]["n"]
    print(f"warehouse: {later} row(s) after {keepThrough}" + ("" if later == 0 else
          "  <- these stay; rerun those days through the pipeline, or delete them from dbo.finale_order by hand"))
print("DRY RUN: nothing was changed. Set dryRun = False and run again to apply." if dryRun else "Reset done.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

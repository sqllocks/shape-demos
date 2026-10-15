# Post 5: Good Test Data Breaks on Purpose

The runnable material from SQLBites post 5 of "Shape in practice": generate reproducible test data with Shape 0.9.3,
land it the way a source system would, plant known faults with a ground-truth log, and send it to a Fabric Lakehouse.
All the data is synthetic.

## The files

| File | Article section | What it is |
|---|---|---|
| [`commands.sh`](commands.sh) | every section with a shell command, in article order | Every shell command block in the article, each under a comment naming its section. It stops before the Fabric sections unless `RUN_FABRIC=1`. |
| [`landing_query.py`](landing_query.py) | Walkthrough, 4. Land it like a source system would | Reads the landing folder with DuckDB, taking `ingest_date` from the folder name. |
| [`compare_status.py`](compare_status.py) | Walkthrough, 5. Generate from a profile | Compares the `status` column of the domain output with the output generated from its profile. |
| [`score_checks.py`](score_checks.py) | Walkthrough, 6. Break it on purpose, and keep the answer key | Runs two SQL checks and scores them against the chaos ground-truth log (precision and recall). |
| [`customer_ids.py`](customer_ids.py) | Into Fabric: the shape_finale demo, Run the same code on your machine | Shows why the orphan check over-flags on a `BatchGenerator` day. |
| [`finale_generate_local.py`](finale_generate_local.py) | Into Fabric: the shape_finale demo, Run the same code on your machine | The `finale_generate` notebook's code cell, unchanged, as a local script. |
| [`notebook/finale_generate.notebook.py`](notebook/finale_generate.notebook.py) | Into Fabric: the shape_finale demo, The notebook, piece by piece | The `finale_generate` Fabric notebook, in Fabric's notebook source format, with the 0.9.3 `%pip` cell from "What changed between 0.9.0 and 0.9.3". |

The four helper scripts and the shell commands are copied byte for byte from the article's code blocks.
The article shows the notebook piece by piece; each piece it shows appears unchanged in `notebook/finale_generate.notebook.py`,
and `finale_generate_local.py` holds the same code cell.

## Run the local parts

You need Python 3.11 or later, Bash, and [jq](https://jqlang.org/). Nothing in the local parts touches Azure or Fabric.
Run them in an empty folder, because they write `demo/`, `landing/`, `chaos/`, `finale/` and more next to the scripts:

```bash
python -m venv .venv
. .venv/bin/activate
pip install "sqllocks-shape[domains,azure]==0.9.3"
pip install duckdb "openpyxl>=3.1" "defusedxml>=0.7"   # the helper scripts; openpyxl and defusedxml for the notebook's workbook

mkdir ~/shape-post5
cp commands.sh *.py ~/shape-post5/
cd ~/shape-post5
./commands.sh
```

`[domains]` brings the retail domain; `[azure]` brings the storage libraries for the OneLake targets and isn't needed
for the local steps. The article's step 1 installs `sqllocks-shape[domains]==0.9.3`, which is already satisfied.

What to expect (from the article; timings vary):

- `shape generate retail --scale small --seed 42` plans 21,750 rows in 9 tables, and `--format parquet -o demo/` writes them.
- Seed 42 twice gives identical folders; `demo/order.parquet` has sha256 `193fa2dd643324d2b41be3603628606a814b10a4555ada56435fd46ced71e566`.
- `shape chaos` plants 150 orphan keys, 250 date shifts, 750 null stores and 250 duplicate order lines: 1400 changes in the log.
- `shape diff order_clean.shape order_chaos.shape --fail-on-drift` exits 1. The script carries on: it has no `set -e`.
- `finale_generate_local.py` writes 2,078 orders; the chaos day has 5,320 order lines against 5,216 on the clean day.
- `score_checks.py` on the finale day: orphan check precision 0.030, recall 1.000. The article explains why.

## The Fabric parts

These need an Azure sign-in and a Lakehouse you can write to. They aren't run by default.

**From your machine.** The last two sections of `commands.sh` install the `sqllocks-shape-fabric` plugin, run `az login`
and write to `abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/...`. Replace `<workspace>`
and `<lakehouse>` with yours (use the IDs if either name has a space), then run `RUN_FABRIC=1 ./commands.sh`, or run those
commands by hand. Shape refuses a non-local target without `--yes` or `SHAPE_CONFIRM_REMOTE=1`.

**In a notebook.** `notebook/finale_generate.notebook.py` is the notebook as Fabric stores it in Git. Its metadata names
the default Lakehouse with the placeholders `<lakehouse-id>` and `<workspace-id>`; set your own, or create a Python notebook
in Fabric, attach your Lakehouse as its default, and copy the cells in, marking the parameters cell as the parameter cell.
It writes to `Files/shape-landing` (in the article, a shortcut to an ADLS container) and logs the chaos faults to
`Files/shape/finale/chaos`. A pipeline's Notebook activity can pass `batchDate` and `chaos` and read the exit value.

The notebook imports Python modules outside Shape's API stability promise, and the Fabric writers, landing and chaos are
experimental in 0.9.3. Pin the version.

## Read more

- The article: [SQLBites](https://sqlbites.net) (link to come).
- [Landing](https://docs.shapedata.ai/v0.9.3/LANDING/), [Chaos](https://docs.shapedata.ai/v0.9.3/CHAOS/),
  [Sinks](https://docs.shapedata.ai/v0.9.3/SINKS/) and [Fabric sign-in](https://docs.shapedata.ai/v0.9.3/plugins/fabric-auth/)
  in the Shape 0.9.3 documentation.

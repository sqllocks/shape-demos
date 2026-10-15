#!/usr/bin/env bash
# SQLBites "Shape in practice", post 5: Good Test Data Breaks on Purpose.
# Every shell command block in the article, in article order, each under the article section it comes from.
# Run it in an empty folder that also holds landing_query.py, compare_status.py, score_checks.py,
# customer_ids.py and finale_generate_local.py (see README.md). Needs jq and duckdb for some steps.
# There is no `set -e`: `shape diff ... --fail-on-drift` in section 6 exits 1, as the article says.
# The script stops before the Fabric sections unless RUN_FABRIC=1; those write to your Lakehouse.

# ===== Walkthrough: from nothing to a landing day > 1. Install and look around =====
pip install "sqllocks-shape[domains]==0.9.3"
shape --version
shape list
shape describe retail | head -12

# ===== Walkthrough: from nothing to a landing day > 2. Plan first, then write =====
shape generate retail --scale small --seed 42
shape generate retail --scale small --seed 42 --format parquet -o demo/
ls demo/
jq ".files[0], .seed, .shape_version" demo/_shape_provenance.json

# ===== Walkthrough: from nothing to a landing day > 3. Same seed, same bytes =====
shape generate retail --scale small --seed 42 --format parquet -o demo-again/
shape generate retail --scale small --seed 43 --format parquet -o demo-43/
sha256sum demo/order.parquet demo-again/order.parquet demo-43/order.parquet
diff -r demo demo-again && echo "demo and demo-again are identical"

# ===== Walkthrough: from nothing to a landing day > 4. Land it like a source system would =====
shape generate retail --scale small --seed 42 --format parquet \
  --table-format customer=csv --batch-date 2026-10-07 -o landing/
find landing -type f | sort
python landing_query.py

# ===== Walkthrough: from nothing to a landing day > 5. Generate from a profile =====
shape profile demo/order.parquet -o order.shape --name order
shape plan order.shape | jq .counts
shape plan order.shape --status not_modelled 2>/dev/null | jq -r '.items[] | select(.evidence | startswith("dataset")) | "\(.evidence): \(.reason)"'
shape generate --from order.shape --seed 42 --format parquet -o from-profile/
# the article shows compare_status.py and its output but not the command; this is it
python compare_status.py

# ===== Walkthrough: from nothing to a landing day > 6. Break it on purpose, and keep the answer key =====
shape chaos retail --input demo/ --seed 7 --format parquet \
  --table-format customer=csv --batch-date 2026-10-07 \
  --corrupt orphan_keys=0.03@order.customer_id \
  --corrupt "date_shift=0.05@order.order_date:days=10,direction=early" \
  --corrupt null_creep=0.15@order.store_id \
  --corrupt duplicates=0.02@order_line \
  -o chaos/
head -2 chaos/_chaos_ground_truth_20261007.jsonl
python score_checks.py chaos chaos/_chaos_ground_truth_20261007.jsonl
python score_checks.py landing chaos/_chaos_ground_truth_20261007.jsonl
shape profile landing/order/ingest_date=2026-10-07/order_20261007.parquet -o order_clean.shape --name order
shape profile chaos/order/ingest_date=2026-10-07/order_20261007.parquet -o order_chaos.shape --name order
shape diff order_clean.shape order_chaos.shape --fail-on-drift

# ===== Into Fabric: the shape_finale demo > Run the same code on your machine =====
python finale_generate_local.py finale-clean 2026-10-07 0
python finale_generate_local.py finale 2026-10-07 1
jq -r 'select(.record == "change") | "\(.table) \(.kind)"' finale/shape/finale/chaos/_chaos_ground_truth_20261007.jsonl | sort | uniq -c
python score_checks.py finale/shape-landing finale/shape/finale/chaos/_chaos_ground_truth_20261007.jsonl
python customer_ids.py finale-clean/shape-landing

if [ "${RUN_FABRIC:-0}" != "1" ]; then
  echo "Local sections done. Set RUN_FABRIC=1 to run the Fabric sections (they need Azure sign-in and a Lakehouse)."
  exit 0
fi

# ===== Into Fabric from outside: the writers as shipped =====
pip install "sqllocks-shape[domains,azure]==0.9.3" "sqllocks-shape-fabric==0.9.3"
shape plugins list | grep -E "sqllocks-shape-fabric|shape.sinks"

# ===== Into Fabric from outside: the writers as shipped > Send the landing day to OneLake =====
az login
shape generate retail --scale small --seed 42 --format parquet \
  --table-format customer=csv --batch-date 2026-10-07 \
  --to "abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/shape-landing" \
  --yes
shape generate retail --scale small --seed 42 \
  --to "delta+abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Tables" --yes

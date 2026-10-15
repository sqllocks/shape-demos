"""Score two simple data-quality checks against Shape's chaos ground-truth log.
Usage: python score_checks.py FOLDER LOG   Needs: pip install duckdb"""
import json
import sys

import duckdb

folder, log = sys.argv[1], sys.argv[2]
orders = f"read_parquet('{folder}/order/*/*.parquet')"
customers = f"read_csv('{folder}/customer/*/*.csv')"
lines = f"read_parquet('{folder}/order_line/*/*.parquet')"

checks = {
    # an order whose customer is not in the customer file
    "orphan_keys": f"""select o.order_id from {orders} o
                       where not exists (select 1 from {customers} c where c.customer_id = o.customer_id)""",
    # an order line id that arrives more than once
    "duplicates": f"""select order_line_id from {lines}
                      group by order_line_id having count(*) > 1""",
}

records = [json.loads(line) for line in open(log)]
for kind, sql in checks.items():
    flagged = {row[0] for row in duckdb.sql(sql).fetchall()}
    planted = {r["key"] for r in records if r.get("kind") == kind}
    hits = flagged & planted
    print(f"{kind:<12} planted {len(planted):>4}  flagged {len(flagged):>4}  "
          f"precision {len(hits) / max(len(flagged), 1):.3f}  recall {len(hits) / max(len(planted), 1):.3f}")

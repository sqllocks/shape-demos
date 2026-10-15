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

# CELL ********************

import shape
from pathlib import Path

BASE = Path("/lakehouse/default/Files/shape/finale")
# (layer, table, day) to turn into HTML reports; edit this list
reports = [
    ("warehouse", "order", "2026-10-06"),
    ("lakehouse", "order", "2026-10-06"),
]

for layer, table, day in reports:
    src = BASE / layer / table / f"{day}.shape"
    if not src.exists():
        print("missing:", src)
        continue
    out = BASE / "html" / f"{layer}_{table}_{day}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(shape.load(str(src)).to_html(), encoding="utf-8")
    print(out, out.stat().st_size, "bytes")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

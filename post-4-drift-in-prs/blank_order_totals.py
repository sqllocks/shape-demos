"""Blank order_total on every eighth order: the bad feed a pull request brings in.

Usage: python blank_order_totals.py data/orders.csv
order_id is the first column and order_total the last, so the edit keeps every other byte.
"""
import sys

path = sys.argv[1]
with open(path, encoding="utf-8", newline="") as f:
    lines = f.read().split("\n")
header, rows = lines[0], [line for line in lines[1:] if line]
changed = 0
out = [header]
for line in rows:
    if int(line.split(",", 1)[0]) % 8 == 0:
        line = line.rsplit(",", 1)[0] + ","
        changed += 1
    out.append(line)
with open(path, "w", encoding="utf-8", newline="") as f:
    f.write("\n".join(out) + "\n")
print(f"blanked order_total on {changed} of {len(rows)} orders")

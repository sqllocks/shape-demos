"""Why the orphan check over-flags on a BatchGenerator day: today's customer file holds only
today's new customers, while orders reference customers from earlier days.
Usage: python customer_ids.py FOLDER   Needs: pip install duckdb"""
import sys

import duckdb

folder = sys.argv[1]
print(duckdb.sql(f"""
    select (select min(customer_id) from read_csv('{folder}/customer/*/*.csv')) as first_customer_today,
           (select min(customer_id) from read_parquet('{folder}/order/*/*.parquet')) as lowest_customer_ordering_today
"""))

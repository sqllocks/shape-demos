"""Compare one column of the domain output with the output generated from its profile.
Needs: pip install duckdb"""
import duckdb

for folder in ("demo", "from-profile"):
    print(folder)
    print(duckdb.sql(f"""
        select status, count(*) as orders, round(count(*) / sum(count(*)) over (), 3) as share
        from read_parquet('{folder}/order.parquet')
        group by status order by status
    """))

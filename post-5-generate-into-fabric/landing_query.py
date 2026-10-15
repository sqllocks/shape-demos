"""Read the landing folder the way a Lakehouse reads it: every day's files of a table as one table,
with ingest_date taken from the folder name. Needs: pip install duckdb"""
import duckdb

print(duckdb.sql("""
    select ingest_date, count(*) as orders, count(distinct customer_id) as customers
    from read_parquet('landing/order/*/*.parquet', hive_partitioning = true)
    group by ingest_date
"""))
print(duckdb.sql("""
    select count(*) as customers, min(signup_date) as first_signup
    from read_csv('landing/customer/*/*.csv', hive_partitioning = true)
"""))

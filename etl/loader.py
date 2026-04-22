"""
ETL loader: reads raw CSVs → transforms → loads into SQLite.
Run: python etl/loader.py
"""

import pandas as pd
import sqlite3
import os

RAW_DIR = "data/raw"
DB_PATH = "data/lumber.db"

os.makedirs("data", exist_ok=True)


def load_raw() -> dict[str, pd.DataFrame]:
    tables = ["customers", "products", "orders", "order_items", "inventory"]
    return {t: pd.read_csv(f"{RAW_DIR}/{t}.csv") for t in tables}


def transform(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    customers  = raw["customers"].copy()
    products   = raw["products"].copy()
    orders     = raw["orders"].copy()
    items      = raw["order_items"].copy()
    inventory  = raw["inventory"].copy()

    # normalize dates
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    orders["year"]  = orders["order_date"].dt.year
    orders["month"] = orders["order_date"].dt.month
    orders["week"]  = orders["order_date"].dt.isocalendar().week.astype(int)

    # enrich items with financials
    items["revenue"] = items["quantity"] * items["unit_price"]
    items["cogs"]    = items["quantity"] * items["unit_cost"]
    items["gross_profit"] = items["revenue"] - items["cogs"]

    # join orders → items for a flat fact table
    fact = items.merge(orders[["order_id", "customer_id", "order_date",
                                "location", "status", "year", "month", "week", "sales_rep"]],
                       on="order_id")
    fact = fact.merge(products[["product_id", "name", "category"]], on="product_id")
    fact = fact.merge(
        customers[["customer_id", "type", "name"]].rename(columns={"name": "customer_name"}),
        on="customer_id",
    )

    # exclude returned orders from primary metrics
    fact_clean = fact[fact["status"] == "completed"].copy()

    # daily summary
    daily = (fact_clean
             .groupby("order_date")
             .agg(revenue=("revenue", "sum"),
                  cogs=("cogs", "sum"),
                  gross_profit=("gross_profit", "sum"),
                  orders=("order_id", "nunique"))
             .reset_index())
    daily["margin_pct"] = (daily["gross_profit"] / daily["revenue"] * 100).round(2)

    # inventory health
    inventory = inventory.merge(products[["product_id", "name", "category",
                                          "cost", "list_price"]], on="product_id")
    inventory["below_reorder"] = inventory["stock_level"] < inventory["reorder_point"]
    inventory["inventory_value"] = inventory["stock_level"] * inventory["cost"]

    return {
        "customers":   customers,
        "products":    products,
        "orders":      orders,
        "order_items": items,
        "inventory":   inventory,
        "fact_sales":  fact_clean,
        "daily_summary": daily,
    }


def write_db(tables: dict[str, pd.DataFrame], db_path: str = DB_PATH) -> None:
    con = sqlite3.connect(db_path)
    for name, df in tables.items():
        df.to_sql(name, con, if_exists="replace", index=False)
        print(f"  wrote {name:20s}  ({len(df):,} rows)")
    con.close()
    print(f"\nDatabase → {db_path}")


def run() -> None:
    """Full ETL pipeline. Safe to call programmatically."""
    print("Loading raw CSVs...")
    raw = load_raw()

    print("Transforming...")
    clean = transform(raw)

    print("Writing to SQLite...")
    write_db(clean)


if __name__ == "__main__":
    run()

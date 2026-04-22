"""
Shared test fixtures.

Strategy:
- KPI functions read from SQLite via metrics.kpis.DB_PATH.
  We patch that module-level variable to point at a temp DB populated
  with deterministic, minimal data whose expected outputs we can calculate by hand.
- ETL transform() is pure pandas — tested directly, no DB needed.

Test data math (completed orders only — O003 is returned and excluded):

  O001 / C001 / Contractor / 2024-01-15 / Yard A / Mike Torres
    P001  qty=10  price=6.99  cost=3.50  → rev=69.90  cogs=35.00  gp=34.90
    P002  qty=5   price=18.00 cost=12.00 → rev=90.00  cogs=60.00  gp=30.00

  O002 / C002 / Retail / 2024-01-20 / Yard B / Amanda Price
    P001  qty=2   price=6.99  cost=3.50  → rev=13.98  cogs=7.00   gp=6.98

  O004 / C001 / Contractor / 2024-02-15 / Yard A / Mike Torres
    P001  qty=20  price=6.50  cost=3.50  → rev=130.00 cogs=70.00  gp=60.00

  O005 / C001 / Contractor / <recent date, within 90 days of test run> / Yard A / Mike Torres
    P003  qty=5   price=8.25  cost=4.50  → rev=41.25  cogs=22.50  gp=18.75

  O006 / C003 / Contractor / 2024-01-10 / Yard A / Sarah Chen  ← inactive customer seed
    P001  qty=10  price=6.99  cost=3.50  → rev=69.90  cogs=35.00  gp=34.90

  O007 / C003 / Contractor / 2024-02-10 / Yard A / Sarah Chen  ← inactive customer seed
    P001  qty=5   price=6.99  cost=3.50  → rev=34.95  cogs=17.50  gp=17.45

Rep totals (Yard A):
  Mike Torres : O001+O004+O005 → rev=331.15  gp=143.65
  Sarah Chen  : O006+O007      → rev=104.85  gp=52.35

Inactive customer test:
  C001 — active (O005 is within 90 days of MAX order date = RECENT_DATE)
  C002 — only 1 order → excluded by HAVING total_orders >= 2
  C003 — 2 orders (Jan/Feb 2024), both older than RECENT_DATE - 90 days → INACTIVE

Monthly (core orders only, C001+C002):
  2024-01 : rev=173.88  gp=71.88  margin~=41.3%
  2024-02 : rev=130.00  gp=60.00  margin~=46.2%

Inventory:
  P001 / Yard A : stock=50,  reorder=100  → below_reorder=1
  P002 / Yard A : stock=200, reorder=50   → below_reorder=0
  P003 / Yard A : stock=500, reorder=100  → below_reorder=0  (no sales in last 90d except O005)
"""

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

# A recent date guaranteed to be within 90 days of any test run
RECENT_DATE = (date.today() - timedelta(days=10)).isoformat()


def _build_test_db(path: str) -> None:
    con = sqlite3.connect(path)

    # ── fact_sales ────────────────────────────────────────────────────────────
    # Denormalised fact table — the primary source for all KPI functions.
    con.execute("""
        CREATE TABLE fact_sales (
            order_id      TEXT,
            product_id    TEXT,
            quantity      INTEGER,
            unit_price    REAL,
            unit_cost     REAL,
            discount      REAL,
            revenue       REAL,
            cogs          REAL,
            gross_profit  REAL,
            customer_id   TEXT,
            order_date    TEXT,
            location      TEXT,
            status        TEXT,
            year          INTEGER,
            month         INTEGER,
            week          INTEGER,
            name          TEXT,
            category      TEXT,
            type          TEXT,
            sales_rep     TEXT,
            customer_name TEXT
        )
    """)

    con.executemany(
        """INSERT INTO fact_sales VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            # O001 line 1 — C001 = ProBuild LLC
            ("O001","P001",10, 6.99,3.50,0.0, 69.90, 35.00,34.90,
             "C001","2024-01-15","Yard A","completed",2024,1,3,
             "2x4x8 Lumber","Dimensional Lumber","Contractor","Mike Torres","ProBuild LLC"),
            # O001 line 2
            ("O001","P002",5, 18.00,12.00,0.0, 90.00, 60.00,30.00,
             "C001","2024-01-15","Yard A","completed",2024,1,3,
             "Plywood Sheet","Sheet Goods","Contractor","Mike Torres","ProBuild LLC"),
            # O002 — C002 = John Smith
            ("O002","P001",2, 6.99,3.50,0.0, 13.98, 7.00,6.98,
             "C002","2024-01-20","Yard B","completed",2024,1,3,
             "2x4x8 Lumber","Dimensional Lumber","Retail","Amanda Price","John Smith"),
            # O004
            ("O004","P001",20, 6.50,3.50,0.05,130.00,70.00,60.00,
             "C001","2024-02-15","Yard A","completed",2024,2,7,
             "2x4x8 Lumber","Dimensional Lumber","Contractor","Mike Torres","ProBuild LLC"),
            # O005 — recent date, used for slow-moving inventory test
            ("O005","P003",5, 8.25,4.50,0.0, 41.25,22.50,18.75,
             "C001", RECENT_DATE,"Yard A","completed",
             int(RECENT_DATE[:4]),int(RECENT_DATE[5:7]),1,
             "Cedar Decking","Decking","Contractor","Mike Torres","ProBuild LLC"),
            # O006 + O007 — C003 = SunriseDev Inc, both old orders → inactive_customers
            ("O006","P001",10, 6.99,3.50,0.0, 69.90,35.00,34.90,
             "C003","2024-01-10","Yard A","completed",2024,1,2,
             "2x4x8 Lumber","Dimensional Lumber","Contractor","Sarah Chen","SunriseDev Inc"),
            ("O007","P001",5, 6.99,3.50,0.0, 34.95,17.50,17.45,
             "C003","2024-02-10","Yard A","completed",2024,2,6,
             "2x4x8 Lumber","Dimensional Lumber","Contractor","Sarah Chen","SunriseDev Inc"),
        ],
    )

    # ── inventory ─────────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE inventory (
            product_id      TEXT,
            location        TEXT,
            stock_level     INTEGER,
            reorder_point   INTEGER,
            below_reorder   INTEGER,
            last_updated    TEXT,
            name            TEXT,
            category        TEXT,
            cost            REAL,
            list_price      REAL,
            inventory_value REAL
        )
    """)

    con.executemany(
        "INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("P001","Yard A", 50, 100,1,"2024-03-31",
             "2x4x8 Lumber","Dimensional Lumber",3.50,6.99, 175.00),
            ("P002","Yard A",200,  50,0,"2024-03-31",
             "Plywood Sheet","Sheet Goods",12.00,18.00,2400.00),
            ("P003","Yard A",500, 100,0,"2024-03-31",
             "Cedar Decking","Decking",4.50,8.25,2250.00),
        ],
    )

    con.commit()
    con.close()


@pytest.fixture()
def test_db(tmp_path, monkeypatch):
    """
    Creates a temp SQLite DB with known test data and patches
    metrics.kpis.DB_PATH so all KPI functions read from it.
    """
    db_path = str(tmp_path / "test_lumber.db")
    _build_test_db(db_path)

    import metrics.kpis as kpis_module
    monkeypatch.setattr(kpis_module, "DB_PATH", db_path)

    yield db_path


# ── reusable raw DataFrames for ETL tests ─────────────────────────────────────

@pytest.fixture()
def raw_dataframes() -> dict[str, pd.DataFrame]:
    """Minimal raw DataFrames that mirror what load_raw() produces from CSVs."""
    customers = pd.DataFrame([
        {"customer_id": "C001", "name": "ProBuild LLC", "type": "Contractor",
         "location": "Yard A", "since": "2023-01-01"},
        {"customer_id": "C002", "name": "John Smith",   "type": "Retail",
         "location": "Yard B", "since": "2023-06-01"},
    ])
    # 'name' is renamed to 'customer_name' during the ETL merge — tested in test_etl.py

    products = pd.DataFrame([
        {"product_id":"P001","name":"2x4x8 Lumber","category":"Dimensional Lumber",
         "cost":3.50,"list_price":6.99},
        {"product_id":"P002","name":"Plywood Sheet","category":"Sheet Goods",
         "cost":12.00,"list_price":18.00},
    ])

    orders = pd.DataFrame([
        {"order_id":"O001","customer_id":"C001","order_date":"2024-01-15",
         "location":"Yard A","status":"completed","sales_rep":"Mike Torres"},
        {"order_id":"O002","customer_id":"C002","order_date":"2024-01-20",
         "location":"Yard B","status":"completed","sales_rep":"Amanda Price"},
        # O003 is returned — must be excluded from fact_sales
        {"order_id":"O003","customer_id":"C001","order_date":"2024-02-01",
         "location":"Yard A","status":"returned","sales_rep":"Mike Torres"},
    ])

    order_items = pd.DataFrame([
        {"order_id":"O001","product_id":"P001","quantity":10,
         "unit_price":6.99,"unit_cost":3.50,"discount":0.0},
        {"order_id":"O001","product_id":"P002","quantity":5,
         "unit_price":18.00,"unit_cost":12.00,"discount":0.0},
        {"order_id":"O002","product_id":"P001","quantity":2,
         "unit_price":6.99,"unit_cost":3.50,"discount":0.0},
        # O003 line — should be excluded via order status filter
        {"order_id":"O003","product_id":"P002","quantity":3,
         "unit_price":18.00,"unit_cost":12.00,"discount":0.0},
    ])

    inventory = pd.DataFrame([
        {"product_id":"P001","location":"Yard A","stock_level":50,
         "reorder_point":100,"last_updated":"2024-03-31"},
        {"product_id":"P002","location":"Yard A","stock_level":200,
         "reorder_point":50,"last_updated":"2024-03-31"},
    ])

    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "inventory": inventory,
    }

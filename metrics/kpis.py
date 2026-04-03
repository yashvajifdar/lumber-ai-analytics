"""
Trusted KPI functions. Each returns a DataFrame ready for display or charting.
The chat layer calls these — the LLM never writes raw SQL.
"""

import sqlite3
import pandas as pd

DB_PATH = "data/lumber.db"


def _con() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


# ── revenue ──────────────────────────────────────────────────────────────────

def revenue_over_time(period: str = "month") -> pd.DataFrame:
    """period: 'day' | 'week' | 'month'"""
    groupby = {
        "day":   "DATE(order_date)",
        "week":  "strftime('%Y-W%W', order_date)",
        "month": "strftime('%Y-%m', order_date)",
    }[period]
    sql = f"""
        SELECT {groupby} AS period,
               SUM(revenue)       AS revenue,
               SUM(cogs)          AS cogs,
               SUM(gross_profit)  AS gross_profit,
               COUNT(DISTINCT order_id) AS orders
        FROM   fact_sales
        GROUP  BY 1
        ORDER  BY 1
    """
    df = pd.read_sql(sql, _con())
    df["margin_pct"] = (df["gross_profit"] / df["revenue"] * 100).round(2)
    return df


def margin_trend(period: str = "month") -> pd.DataFrame:
    return revenue_over_time(period)[["period", "margin_pct", "revenue", "gross_profit"]]


# ── products ─────────────────────────────────────────────────────────────────

def top_products(n: int = 10, by: str = "revenue") -> pd.DataFrame:
    """by: 'revenue' | 'gross_profit' | 'quantity' | 'margin_pct'"""
    sql = f"""
        SELECT name, category,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               SUM(quantity)     AS quantity,
               ROUND(SUM(gross_profit)/SUM(revenue)*100, 1) AS margin_pct
        FROM   fact_sales
        GROUP  BY name, category
        ORDER  BY {by} DESC
        LIMIT  {n}
    """
    return pd.read_sql(sql, _con())


def bottom_margin_products(n: int = 10) -> pd.DataFrame:
    sql = f"""
        SELECT name, category,
               SUM(revenue) AS revenue,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        GROUP  BY name, category
        HAVING SUM(revenue) > 5000
        ORDER  BY margin_pct ASC
        LIMIT  {n}
    """
    return pd.read_sql(sql, _con())


def revenue_by_category() -> pd.DataFrame:
    sql = """
        SELECT category,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        GROUP  BY category
        ORDER  BY revenue DESC
    """
    return pd.read_sql(sql, _con())


# ── customers ────────────────────────────────────────────────────────────────

def top_customers(n: int = 10) -> pd.DataFrame:
    sql = f"""
        SELECT customer_id, type,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               COUNT(DISTINCT order_id) AS orders
        FROM   fact_sales
        GROUP  BY customer_id, type
        ORDER  BY revenue DESC
        LIMIT  {n}
    """
    return pd.read_sql(sql, _con())


def customer_type_split() -> pd.DataFrame:
    sql = """
        SELECT type,
               SUM(revenue) AS revenue,
               COUNT(DISTINCT customer_id) AS customers,
               COUNT(DISTINCT order_id)    AS orders
        FROM   fact_sales
        GROUP  BY type
    """
    return pd.read_sql(sql, _con())


def repeat_customer_rate() -> pd.DataFrame:
    sql = """
        SELECT type,
               COUNT(DISTINCT customer_id) AS total_customers,
               SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers
        FROM (
            SELECT customer_id, type,
                   COUNT(DISTINCT order_id) AS orders
            FROM   fact_sales
            GROUP  BY customer_id, type
        )
        GROUP BY type
    """
    df = pd.read_sql(sql, _con())
    df["repeat_rate_pct"] = (df["repeat_customers"] / df["total_customers"] * 100).round(1)
    return df


# ── location ─────────────────────────────────────────────────────────────────

def revenue_by_location(period: str = "month") -> pd.DataFrame:
    groupby = {
        "month": "strftime('%Y-%m', order_date)",
        "week":  "strftime('%Y-W%W', order_date)",
        "total": "'all'",
    }[period]
    sql = f"""
        SELECT location, {groupby} AS period,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        GROUP  BY location, period
        ORDER  BY period, location
    """
    return pd.read_sql(sql, _con())


# ── inventory ────────────────────────────────────────────────────────────────

def inventory_health() -> pd.DataFrame:
    sql = """
        SELECT name, category, location,
               stock_level, reorder_point, below_reorder,
               ROUND(inventory_value, 2) AS inventory_value
        FROM   inventory
        ORDER  BY below_reorder DESC, stock_level ASC
    """
    return pd.read_sql(sql, _con())


def slow_moving_inventory() -> pd.DataFrame:
    """Products with high stock but low recent sales velocity."""
    sql = """
        SELECT i.name, i.category,
               SUM(i.stock_level) AS total_stock,
               COALESCE(SUM(s.quantity), 0) AS units_sold_90d,
               SUM(i.inventory_value) AS inventory_value
        FROM   inventory i
        LEFT JOIN (
            SELECT product_id, SUM(quantity) AS quantity
            FROM   fact_sales
            WHERE  order_date >= DATE('now', '-90 days')
            GROUP  BY product_id
        ) s ON i.product_id = s.product_id
        GROUP BY i.name, i.category
        HAVING total_stock > 100
        ORDER  BY units_sold_90d ASC
        LIMIT  15
    """
    return pd.read_sql(sql, _con())

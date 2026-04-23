"""
Trusted KPI functions. Each returns a DataFrame ready for display or charting.
The chat layer calls these — the LLM never writes raw SQL.
"""

import sqlite3
import pandas as pd

DB_PATH = "data/lumber.db"

_SORT_CUSTOMERS = {"revenue", "gross_profit", "orders"}
_SORT_PRODUCTS  = {"revenue", "gross_profit", "quantity", "margin_pct"}
_SORT_REPS      = {"revenue", "gross_profit", "orders"}


def _con() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _build_where(
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> tuple[str, list]:
    """Build a parameterized WHERE clause from optional filter args."""
    clauses: list[str] = []
    params: list = []
    if date_from:
        clauses.append("order_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("order_date <= ?")
        params.append(date_to)
    if location:
        clauses.append("location = ?")
        params.append(location)
    if customer_type:
        clauses.append("type = ?")
        params.append(customer_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ── revenue ──────────────────────────────────────────────────────────────────

def revenue_over_time(
    period: str = "month",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> pd.DataFrame:
    """period: 'day' | 'week' | 'month'"""
    groupby = {
        "day":   "DATE(order_date)",
        "week":  "strftime('%Y-W%W', order_date)",
        "month": "strftime('%Y-%m', order_date)",
    }[period]
    where, params = _build_where(date_from, date_to, location, customer_type)
    sql = f"""
        SELECT {groupby} AS period,
               SUM(revenue)       AS revenue,
               SUM(cogs)          AS cogs,
               SUM(gross_profit)  AS gross_profit,
               COUNT(DISTINCT order_id) AS orders
        FROM   fact_sales
        {where}
        GROUP  BY 1
        ORDER  BY 1
    """
    df = pd.read_sql(sql, _con(), params=params)
    df["margin_pct"] = (df["gross_profit"] / df["revenue"] * 100).round(2)
    return df


def margin_trend(
    period: str = "month",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> pd.DataFrame:
    return revenue_over_time(period, date_from, date_to, location, customer_type)[
        ["period", "margin_pct", "revenue", "gross_profit"]
    ]


# ── products ─────────────────────────────────────────────────────────────────

def top_products(
    n: int = 10,
    by: str = "revenue",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
    min_revenue: float | None = None,
    min_margin_pct: float | None = None,
) -> pd.DataFrame:
    """by: 'revenue' | 'gross_profit' | 'quantity' | 'margin_pct'"""
    if by not in _SORT_PRODUCTS:
        by = "revenue"
    where, params = _build_where(date_from, date_to, location, customer_type)
    having_clauses: list[str] = []
    having_params: list = []
    if min_revenue is not None:
        having_clauses.append("SUM(revenue) >= ?")
        having_params.append(min_revenue)
    if min_margin_pct is not None:
        having_clauses.append("ROUND(SUM(gross_profit)/SUM(revenue)*100, 1) >= ?")
        having_params.append(min_margin_pct)
    having = ("HAVING " + " AND ".join(having_clauses)) if having_clauses else ""
    sql = f"""
        SELECT name, category,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               SUM(quantity)     AS quantity,
               ROUND(SUM(gross_profit)/SUM(revenue)*100, 1) AS margin_pct
        FROM   fact_sales
        {where}
        GROUP  BY name, category
        {having}
        ORDER  BY {by} DESC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + having_params + [n])


def bottom_margin_products(
    n: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> pd.DataFrame:
    where, params = _build_where(date_from, date_to, location, customer_type)
    sql = f"""
        SELECT name, category,
               SUM(revenue) AS revenue,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        {where}
        GROUP  BY name, category
        HAVING SUM(revenue) > 5000
        ORDER  BY margin_pct ASC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + [n])


def revenue_by_category(
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> pd.DataFrame:
    where, params = _build_where(date_from, date_to, location, customer_type)
    sql = f"""
        SELECT category,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        {where}
        GROUP  BY category
        ORDER  BY revenue DESC
    """
    return pd.read_sql(sql, _con(), params=params)


def top_products_by_category(
    category: str,
    n: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
) -> pd.DataFrame:
    """Top products within a specific category, ranked by revenue."""
    where, params = _build_where(date_from, date_to, location)
    cat_clause = ("AND category = ?" if where else "WHERE category = ?")
    sql = f"""
        SELECT name, category,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100, 1) AS margin_pct
        FROM   fact_sales
        {where}
        {cat_clause}
        GROUP  BY name, category
        ORDER  BY revenue DESC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + [category, n])


# ── customers ────────────────────────────────────────────────────────────────

def top_customers(
    n: int = 10,
    sort_by: str = "revenue",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
    min_revenue: float | None = None,
    min_orders: int | None = None,
) -> pd.DataFrame:
    if sort_by not in _SORT_CUSTOMERS:
        sort_by = "revenue"
    where, params = _build_where(date_from, date_to, location, customer_type)
    having_clauses: list[str] = []
    having_params: list = []
    if min_revenue is not None:
        having_clauses.append("SUM(revenue) >= ?")
        having_params.append(min_revenue)
    if min_orders is not None:
        having_clauses.append("COUNT(DISTINCT order_id) >= ?")
        having_params.append(min_orders)
    having = ("HAVING " + " AND ".join(having_clauses)) if having_clauses else ""
    sql = f"""
        SELECT customer_id, customer_name, type,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               COUNT(DISTINCT order_id) AS orders
        FROM   fact_sales
        {where}
        GROUP  BY customer_id, customer_name, type
        {having}
        ORDER  BY {sort_by} DESC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + having_params + [n])


def customer_type_split(
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
) -> pd.DataFrame:
    where, params = _build_where(date_from, date_to, location)
    sql = f"""
        SELECT type,
               SUM(revenue) AS revenue,
               COUNT(DISTINCT customer_id) AS customers,
               COUNT(DISTINCT order_id)    AS orders
        FROM   fact_sales
        {where}
        GROUP  BY type
    """
    return pd.read_sql(sql, _con(), params=params)


def top_customers_by_type(
    customer_type: str,
    n: int = 10,
    sort_by: str = "revenue",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    min_revenue: float | None = None,
) -> pd.DataFrame:
    """Top customers within a specific type (Contractor or Retail), ranked by chosen metric."""
    if sort_by not in _SORT_CUSTOMERS:
        sort_by = "revenue"
    where, params = _build_where(date_from, date_to, location)
    type_clause = ("AND type = ?" if where else "WHERE type = ?")
    having_clauses: list[str] = []
    having_params: list = []
    if min_revenue is not None:
        having_clauses.append("SUM(revenue) >= ?")
        having_params.append(min_revenue)
    having = ("HAVING " + " AND ".join(having_clauses)) if having_clauses else ""
    sql = f"""
        SELECT customer_id, customer_name, type,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               COUNT(DISTINCT order_id) AS orders
        FROM   fact_sales
        {where}
        {type_clause}
        GROUP  BY customer_id, customer_name, type
        {having}
        ORDER  BY {sort_by} DESC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + [customer_type] + having_params + [n])


def repeat_customer_rate(
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
) -> pd.DataFrame:
    where, params = _build_where(date_from, date_to, location)
    sql = f"""
        SELECT type,
               COUNT(DISTINCT customer_id) AS total_customers,
               SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers
        FROM (
            SELECT customer_id, type,
                   COUNT(DISTINCT order_id) AS orders
            FROM   fact_sales
            {where}
            GROUP  BY customer_id, type
        )
        GROUP BY type
    """
    df = pd.read_sql(sql, _con(), params=params)
    df["repeat_rate_pct"] = (df["repeat_customers"] / df["total_customers"] * 100).round(1)
    return df


def inactive_customers(
    period: str = "quarter",
    location: str | None = None,
    customer_type: str | None = None,
    min_lifetime_revenue: float | None = None,
    n: int = 20,
) -> pd.DataFrame:
    """Customers with 2+ lifetime orders but none in the most recent period window.

    Anchors to MAX(order_date) in the dataset so the query works correctly against
    synthetic data whose end date may be in the past.
    """
    days = {"month": 30, "quarter": 90, "year": 365}.get(period, 90)

    outer_params: list = []
    filter_clauses: list[str] = []
    if location:
        filter_clauses.append("location = ?")
        outer_params.append(location)
    if customer_type:
        filter_clauses.append("type = ?")
        outer_params.append(customer_type)
    filter_clause = ("AND " + " AND ".join(filter_clauses)) if filter_clauses else ""

    having_clauses = ["total_orders >= 2"]
    having_params: list = []
    if min_lifetime_revenue is not None:
        having_clauses.append("SUM(revenue) >= ?")
        having_params.append(min_lifetime_revenue)
    having = "HAVING " + " AND ".join(having_clauses)

    sql = f"""
        SELECT customer_id, customer_name, type, location,
               MAX(order_date)          AS last_order_date,
               SUM(revenue)             AS lifetime_revenue,
               COUNT(DISTINCT order_id) AS total_orders
        FROM   fact_sales
        WHERE  customer_id NOT IN (
            SELECT DISTINCT customer_id
            FROM   fact_sales
            WHERE  order_date >= DATE(
                (SELECT MAX(order_date) FROM fact_sales),
                '-{days} days'
            )
        )
        {filter_clause}
        GROUP  BY customer_id, customer_name, type, location
        {having}
        ORDER  BY last_order_date ASC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=outer_params + having_params + [n])


# ── cross-sell ───────────────────────────────────────────────────────────────

def customer_cross_sell_gap(
    product_has: str,
    product_missing: str,
    customer_type: str | None = None,
    location: str | None = None,
    n: int = 20,
) -> pd.DataFrame:
    """Customers who bought product_has but never bought product_missing.

    Matches against both product name and category using case-insensitive partial
    match — 'framing' matches '2x4x8 Framing Lumber', 'Dimensional Lumber', etc.
    """
    extra_clauses: list[str] = []
    extra_params: list = []
    if location:
        extra_clauses.append("f.location = ?")
        extra_params.append(location)
    if customer_type:
        extra_clauses.append("f.type = ?")
        extra_params.append(customer_type)
    extra_where = ("AND " + " AND ".join(extra_clauses)) if extra_clauses else ""

    sql = f"""
        SELECT
            f.customer_id,
            f.customer_name,
            f.type,
            f.location,
            ROUND(SUM(CASE WHEN LOWER(f.name)     LIKE LOWER('%' || ? || '%')
                               OR LOWER(f.category) LIKE LOWER('%' || ? || '%')
                          THEN f.revenue ELSE 0 END), 2) AS revenue_on_has,
            COUNT(DISTINCT f.order_id)  AS total_orders,
            ROUND(SUM(f.revenue), 2)    AS lifetime_revenue
        FROM   fact_sales f
        WHERE  f.customer_id IN (
            SELECT DISTINCT customer_id FROM fact_sales
            WHERE  LOWER(name)     LIKE LOWER('%' || ? || '%')
               OR  LOWER(category) LIKE LOWER('%' || ? || '%')
        )
        AND    f.customer_id NOT IN (
            SELECT DISTINCT customer_id FROM fact_sales
            WHERE  LOWER(name)     LIKE LOWER('%' || ? || '%')
               OR  LOWER(category) LIKE LOWER('%' || ? || '%')
        )
        {extra_where}
        GROUP  BY f.customer_id, f.customer_name, f.type, f.location
        ORDER  BY revenue_on_has DESC
        LIMIT  ?
    """
    params = [
        product_has, product_has,           # CASE WHEN revenue_on_has
        product_has, product_has,           # IN subquery
        product_missing, product_missing,   # NOT IN subquery
        *extra_params,
        n,
    ]
    return pd.read_sql(sql, _con(), params=params)


# ── location ─────────────────────────────────────────────────────────────────

def revenue_by_location(
    period: str = "month",
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
) -> pd.DataFrame:
    groupby = {
        "month": "strftime('%Y-%m', order_date)",
        "week":  "strftime('%Y-W%W', order_date)",
        "total": "'all'",
    }[period]
    where, params = _build_where(date_from, date_to, location, customer_type)
    sql = f"""
        SELECT location, {groupby} AS period,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100,1) AS margin_pct
        FROM   fact_sales
        {where}
        GROUP  BY location, period
        ORDER  BY period, location
    """
    return pd.read_sql(sql, _con(), params=params)


# ── sales rep ─────────────────────────────────────────────────────────────────

def sales_by_rep(
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
    customer_type: str | None = None,
    sort_by: str = "revenue",
    n: int = 20,
) -> pd.DataFrame:
    """Sales performance by rep, optionally filtered by location, date range, or customer type."""
    if sort_by not in _SORT_REPS:
        sort_by = "revenue"
    where, params = _build_where(date_from, date_to, location, customer_type)
    sql = f"""
        SELECT sales_rep, location,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit,
               ROUND(SUM(gross_profit)/SUM(revenue)*100, 1) AS margin_pct,
               COUNT(DISTINCT order_id)    AS orders,
               COUNT(DISTINCT customer_id) AS customers
        FROM   fact_sales
        {where}
        GROUP  BY sales_rep, location
        ORDER  BY {sort_by} DESC
        LIMIT  ?
    """
    return pd.read_sql(sql, _con(), params=params + [n])


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
        ORDER  BY units_sold_90d ASC, i.category ASC, inventory_value DESC
        LIMIT  15
    """
    return pd.read_sql(sql, _con())

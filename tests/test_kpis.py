"""
Tests for metrics/kpis.py.

All tests use the `test_db` fixture from conftest.py which:
  1. Creates a temp SQLite DB with deterministic test data
  2. Patches metrics.kpis.DB_PATH to point at it

Expected values are computed from test data defined in conftest.py.
See the conftest module docstring for the full breakdown.
"""

import pandas as pd
import pytest

import metrics.kpis as kpis


# ── revenue_over_time ─────────────────────────────────────────────────────────

class TestRevenueOverTime:
    def test_returns_dataframe(self, test_db):
        result = kpis.revenue_over_time("month")
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.revenue_over_time("month")
        for col in ("period", "revenue", "cogs", "gross_profit", "orders", "margin_pct"):
            assert col in result.columns, f"Missing column: {col}"

    def test_monthly_period_count(self, test_db):
        # Test data spans 2024-01, 2024-02, plus one recent month → at least 3 months
        result = kpis.revenue_over_time("month")
        assert len(result) >= 3

    def test_revenue_totals_are_positive(self, test_db):
        result = kpis.revenue_over_time("month")
        assert (result["revenue"] > 0).all()

    def test_margin_pct_in_valid_range(self, test_db):
        result = kpis.revenue_over_time("month")
        assert (result["margin_pct"] >= 0).all()
        assert (result["margin_pct"] <= 100).all()

    def test_known_january_revenue(self, test_db):
        # Jan 2024: O001 (69.90+90.00) + O002 (13.98) = 173.88
        result = kpis.revenue_over_time("month")
        jan = result[result["period"] == "2024-01"]
        assert len(jan) == 1
        assert jan.iloc[0]["revenue"] == pytest.approx(173.88, abs=0.01)

    def test_known_january_gross_profit(self, test_db):
        # Jan 2024 GP: 34.90 + 30.00 + 6.98 = 71.88
        result = kpis.revenue_over_time("month")
        jan = result[result["period"] == "2024-01"]
        assert jan.iloc[0]["gross_profit"] == pytest.approx(71.88, abs=0.01)

    def test_known_february_revenue(self, test_db):
        # Feb 2024: O004 only = 130.00
        result = kpis.revenue_over_time("month")
        feb = result[result["period"] == "2024-02"]
        assert len(feb) == 1
        assert feb.iloc[0]["revenue"] == pytest.approx(130.00, abs=0.01)

    def test_day_period_returns_dataframe(self, test_db):
        result = kpis.revenue_over_time("day")
        assert isinstance(result, pd.DataFrame)
        assert "period" in result.columns

    def test_week_period_returns_dataframe(self, test_db):
        result = kpis.revenue_over_time("week")
        assert isinstance(result, pd.DataFrame)

    def test_invalid_period_raises_key_error(self, test_db):
        with pytest.raises(KeyError):
            kpis.revenue_over_time("quarter")


# ── margin_trend ──────────────────────────────────────────────────────────────

class TestMarginTrend:
    def test_returns_dataframe(self, test_db):
        result = kpis.margin_trend("month")
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.margin_trend("month")
        for col in ("period", "margin_pct", "revenue", "gross_profit"):
            assert col in result.columns

    def test_margin_pct_in_valid_range(self, test_db):
        result = kpis.margin_trend("month")
        assert (result["margin_pct"] >= 0).all()
        assert (result["margin_pct"] <= 100).all()


# ── top_products ──────────────────────────────────────────────────────────────

class TestTopProducts:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.top_products(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.top_products()
        for col in ("name", "category", "revenue", "gross_profit", "quantity", "margin_pct"):
            assert col in result.columns

    def test_respects_n_parameter(self, test_db):
        result = kpis.top_products(n=1)
        assert len(result) == 1

    def test_ordered_by_revenue_descending(self, test_db):
        result = kpis.top_products(by="revenue")
        revenues = result["revenue"].tolist()
        assert revenues == sorted(revenues, reverse=True)

    def test_ordered_by_gross_profit_descending(self, test_db):
        result = kpis.top_products(by="gross_profit")
        gp = result["gross_profit"].tolist()
        assert gp == sorted(gp, reverse=True)

    def test_top_product_by_revenue_is_lumber(self, test_db):
        # 2x4x8 Lumber: 69.90 + 13.98 + 130.00 = 213.88 (across O001, O002, O004)
        result = kpis.top_products(n=10, by="revenue")
        # Filter to non-recent data — but since test_db has O005 (Cedar Decking) too,
        # Lumber should still be #1 (213.88 vs 90.00 vs 41.25)
        assert result.iloc[0]["name"] == "2x4x8 Lumber"

    def test_margin_pct_in_valid_range(self, test_db):
        result = kpis.top_products()
        assert (result["margin_pct"] >= 0).all()
        assert (result["margin_pct"] <= 100).all()

    def test_ordered_by_margin_pct_descending(self, test_db):
        result = kpis.top_products(by="margin_pct")
        margins = result["margin_pct"].tolist()
        assert margins == sorted(margins, reverse=True)


# ── bottom_margin_products ────────────────────────────────────────────────────

class TestBottomMarginProducts:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.bottom_margin_products(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.bottom_margin_products()
        for col in ("name", "category", "revenue", "margin_pct"):
            assert col in result.columns

    def test_ordered_ascending_by_margin(self, test_db):
        result = kpis.bottom_margin_products()
        if len(result) > 1:
            margins = result["margin_pct"].tolist()
            assert margins == sorted(margins)


# ── revenue_by_category ───────────────────────────────────────────────────────

class TestRevenueByCategory:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.revenue_by_category(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.revenue_by_category()
        for col in ("category", "revenue", "gross_profit", "margin_pct"):
            assert col in result.columns

    def test_no_null_categories(self, test_db):
        result = kpis.revenue_by_category()
        assert result["category"].notna().all()

    def test_ordered_by_revenue_descending(self, test_db):
        result = kpis.revenue_by_category()
        revenues = result["revenue"].tolist()
        assert revenues == sorted(revenues, reverse=True)

    def test_dimensional_lumber_is_top_category(self, test_db):
        # Dimensional Lumber: 213.88 (O001+O002+O004 for P001)
        # Sheet Goods: 90.00 (O001 for P002)
        result = kpis.revenue_by_category()
        assert result.iloc[0]["category"] == "Dimensional Lumber"


# ── top_customers ─────────────────────────────────────────────────────────────

class TestTopCustomers:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.top_customers(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.top_customers()
        for col in ("customer_id", "type", "revenue", "gross_profit", "orders"):
            assert col in result.columns

    def test_respects_n_parameter(self, test_db):
        result = kpis.top_customers(n=1)
        assert len(result) == 1

    def test_ordered_by_revenue_descending(self, test_db):
        result = kpis.top_customers()
        revenues = result["revenue"].tolist()
        assert revenues == sorted(revenues, reverse=True)

    def test_top_customer_is_c001(self, test_db):
        # C001 (Contractor): O001 + O004 + O005 > C002: O002
        result = kpis.top_customers(n=1)
        assert result.iloc[0]["customer_id"] == "C001"


# ── customer_type_split ───────────────────────────────────────────────────────

class TestCustomerTypeSplit:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.customer_type_split(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.customer_type_split()
        for col in ("type", "revenue", "customers", "orders"):
            assert col in result.columns

    def test_both_customer_types_present(self, test_db):
        result = kpis.customer_type_split()
        types = set(result["type"].values)
        assert "Contractor" in types
        assert "Retail" in types

    def test_contractor_revenue_greater_than_retail(self, test_db):
        result = kpis.customer_type_split().set_index("type")
        assert result.loc["Contractor", "revenue"] > result.loc["Retail", "revenue"]


# ── repeat_customer_rate ──────────────────────────────────────────────────────

class TestRepeatCustomerRate:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.repeat_customer_rate(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.repeat_customer_rate()
        for col in ("type", "total_customers", "repeat_customers", "repeat_rate_pct"):
            assert col in result.columns

    def test_repeat_rate_pct_in_valid_range(self, test_db):
        result = kpis.repeat_customer_rate()
        assert (result["repeat_rate_pct"] >= 0).all()
        assert (result["repeat_rate_pct"] <= 100).all()

    def test_contractor_c001_is_repeat_customer(self, test_db):
        # C001 has O001, O004, O005 → repeat
        result = kpis.repeat_customer_rate().set_index("type")
        assert result.loc["Contractor", "repeat_customers"] >= 1

    def test_repeat_customers_lte_total_customers(self, test_db):
        result = kpis.repeat_customer_rate()
        assert (result["repeat_customers"] <= result["total_customers"]).all()


# ── revenue_by_location ───────────────────────────────────────────────────────

class TestRevenueByLocation:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.revenue_by_location("month"), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.revenue_by_location("month")
        for col in ("location", "period", "revenue", "gross_profit", "margin_pct"):
            assert col in result.columns

    def test_both_locations_present(self, test_db):
        result = kpis.revenue_by_location("total")
        locations = set(result["location"].values)
        assert "Yard A" in locations
        assert "Yard B" in locations

    def test_margin_pct_in_valid_range(self, test_db):
        result = kpis.revenue_by_location("month")
        assert (result["margin_pct"] >= 0).all()
        assert (result["margin_pct"] <= 100).all()

    def test_invalid_period_raises_key_error(self, test_db):
        with pytest.raises(KeyError):
            kpis.revenue_by_location("quarter")


# ── inventory_health ──────────────────────────────────────────────────────────

class TestInventoryHealth:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.inventory_health(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.inventory_health()
        for col in ("name","category","location","stock_level",
                    "reorder_point","below_reorder","inventory_value"):
            assert col in result.columns

    def test_p001_is_below_reorder(self, test_db):
        result = kpis.inventory_health()
        p001 = result[result["name"] == "2x4x8 Lumber"].iloc[0]
        assert p001["below_reorder"] == 1

    def test_p002_is_not_below_reorder(self, test_db):
        result = kpis.inventory_health()
        p002 = result[result["name"] == "Plywood Sheet"].iloc[0]
        assert p002["below_reorder"] == 0

    def test_below_reorder_rows_sorted_first(self, test_db):
        result = kpis.inventory_health()
        # below_reorder DESC means 1s come before 0s
        assert result.iloc[0]["below_reorder"] == 1

    def test_inventory_value_positive(self, test_db):
        result = kpis.inventory_health()
        assert (result["inventory_value"] > 0).all()


# ── slow_moving_inventory ─────────────────────────────────────────────────────

class TestSlowMovingInventory:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.slow_moving_inventory(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.slow_moving_inventory()
        for col in ("name", "category", "total_stock", "units_sold_90d", "inventory_value"):
            assert col in result.columns

    def test_only_returns_high_stock_items(self, test_db):
        # HAVING total_stock > 100 — P001 stock=50 should be excluded
        result = kpis.slow_moving_inventory()
        assert (result["total_stock"] > 100).all()

    def test_p001_excluded_due_to_low_stock(self, test_db):
        # P001 has total_stock=50 which fails the HAVING total_stock > 100 threshold
        result = kpis.slow_moving_inventory()
        assert "2x4x8 Lumber" not in result["name"].values

    def test_cedar_decking_has_recent_sales(self, test_db):
        # O005 used RECENT_DATE so Cedar Decking should show units_sold_90d > 0
        result = kpis.slow_moving_inventory()
        cedar = result[result["name"] == "Cedar Decking"]
        assert len(cedar) == 1
        assert cedar.iloc[0]["units_sold_90d"] > 0

    def test_plywood_has_no_recent_sales(self, test_db):
        # P002 sales are from 2024-01-15 — older than 90 days
        result = kpis.slow_moving_inventory()
        plywood = result[result["name"] == "Plywood Sheet"]
        assert len(plywood) == 1
        assert plywood.iloc[0]["units_sold_90d"] == 0

    def test_ordered_by_units_sold_ascending(self, test_db):
        result = kpis.slow_moving_inventory()
        if len(result) > 1:
            sold = result["units_sold_90d"].tolist()
            assert sold == sorted(sold)

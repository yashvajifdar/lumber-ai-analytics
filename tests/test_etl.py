"""
Tests for etl/loader.py — transform() function.

These are pure pandas tests. No database required.
Every assertion maps to a specific calculation or business rule.
"""

import pandas as pd
import pytest

from etl.loader import transform


class TestFinancialColumnComputation:
    """Revenue, COGS, and gross profit are computed from quantity × price/cost."""

    def test_revenue_equals_quantity_times_unit_price(self, raw_dataframes):
        result = transform(raw_dataframes)
        items = result["order_items"]
        expected = items["quantity"] * items["unit_price"]
        pd.testing.assert_series_equal(items["revenue"], expected, check_names=False)

    def test_cogs_equals_quantity_times_unit_cost(self, raw_dataframes):
        result = transform(raw_dataframes)
        items = result["order_items"]
        expected = items["quantity"] * items["unit_cost"]
        pd.testing.assert_series_equal(items["cogs"], expected, check_names=False)

    def test_gross_profit_equals_revenue_minus_cogs(self, raw_dataframes):
        result = transform(raw_dataframes)
        items = result["order_items"]
        expected = items["revenue"] - items["cogs"]
        pd.testing.assert_series_equal(items["gross_profit"], expected, check_names=False)

    def test_known_line_item_values(self, raw_dataframes):
        """O001 / P001: qty=10, price=6.99, cost=3.50 → rev=69.90, cogs=35.00, gp=34.90"""
        result = transform(raw_dataframes)
        items = result["order_items"]
        row = items[(items["order_id"] == "O001") & (items["product_id"] == "P001")].iloc[0]

        assert row["revenue"] == pytest.approx(69.90, abs=0.01)
        assert row["cogs"]    == pytest.approx(35.00, abs=0.01)
        assert row["gross_profit"] == pytest.approx(34.90, abs=0.01)


class TestReturnedOrderExclusion:
    """Returned orders must be excluded from fact_sales."""

    def test_returned_orders_absent_from_fact_sales(self, raw_dataframes):
        result = transform(raw_dataframes)
        assert "O003" not in result["fact_sales"]["order_id"].values

    def test_completed_orders_present_in_fact_sales(self, raw_dataframes):
        result = transform(raw_dataframes)
        order_ids = set(result["fact_sales"]["order_id"].values)
        assert "O001" in order_ids
        assert "O002" in order_ids

    def test_fact_sales_row_count_matches_completed_lines(self, raw_dataframes):
        # O001 has 2 lines, O002 has 1 line. O003 (returned) is excluded.
        result = transform(raw_dataframes)
        assert len(result["fact_sales"]) == 3


class TestDateColumnEnrichment:
    """orders must have year, month, and week columns after transform."""

    def test_year_column_added(self, raw_dataframes):
        result = transform(raw_dataframes)
        assert "year" in result["orders"].columns

    def test_month_column_added(self, raw_dataframes):
        result = transform(raw_dataframes)
        assert "month" in result["orders"].columns

    def test_week_column_added(self, raw_dataframes):
        result = transform(raw_dataframes)
        assert "week" in result["orders"].columns

    def test_year_value_correct(self, raw_dataframes):
        result = transform(raw_dataframes)
        orders = result["orders"]
        o001 = orders[orders["order_id"] == "O001"].iloc[0]
        assert o001["year"] == 2024

    def test_month_value_correct(self, raw_dataframes):
        result = transform(raw_dataframes)
        orders = result["orders"]
        o001 = orders[orders["order_id"] == "O001"].iloc[0]
        assert o001["month"] == 1


class TestInventoryEnrichment:
    """Inventory must have below_reorder flag and inventory_value after transform."""

    def test_below_reorder_flag_true_when_stock_lt_reorder(self, raw_dataframes):
        # P001: stock=50, reorder=100 → below
        result = transform(raw_dataframes)
        inv = result["inventory"]
        p001 = inv[inv["product_id"] == "P001"].iloc[0]
        assert p001["below_reorder"] is True or p001["below_reorder"] == 1

    def test_below_reorder_flag_false_when_stock_gte_reorder(self, raw_dataframes):
        # P002: stock=200, reorder=50 → not below
        result = transform(raw_dataframes)
        inv = result["inventory"]
        p002 = inv[inv["product_id"] == "P002"].iloc[0]
        assert p002["below_reorder"] is False or p002["below_reorder"] == 0

    def test_inventory_value_equals_stock_times_cost(self, raw_dataframes):
        # P001: stock=50, cost=3.50 → value=175.00
        result = transform(raw_dataframes)
        inv = result["inventory"]
        p001 = inv[inv["product_id"] == "P001"].iloc[0]
        assert p001["inventory_value"] == pytest.approx(175.00, abs=0.01)


class TestDailySummaryAggregation:
    """daily_summary must correctly aggregate fact_sales by date."""

    def test_daily_summary_has_correct_columns(self, raw_dataframes):
        result = transform(raw_dataframes)
        daily = result["daily_summary"]
        for col in ("revenue", "cogs", "gross_profit", "orders", "margin_pct"):
            assert col in daily.columns, f"Missing column: {col}"

    def test_daily_summary_revenue_for_jan_15(self, raw_dataframes):
        # O001 only: 69.90 + 90.00 = 159.90
        result = transform(raw_dataframes)
        daily = result["daily_summary"]
        row = daily[daily["order_date"] == pd.Timestamp("2024-01-15")].iloc[0]
        assert row["revenue"] == pytest.approx(159.90, abs=0.01)

    def test_daily_summary_order_count(self, raw_dataframes):
        # 2024-01-15 has 1 distinct order (O001)
        result = transform(raw_dataframes)
        daily = result["daily_summary"]
        row = daily[daily["order_date"] == pd.Timestamp("2024-01-15")].iloc[0]
        assert row["orders"] == 1

    def test_daily_summary_margin_pct_in_valid_range(self, raw_dataframes):
        result = transform(raw_dataframes)
        daily = result["daily_summary"]
        assert (daily["margin_pct"] >= 0).all()
        assert (daily["margin_pct"] <= 100).all()


class TestOutputTableKeys:
    """transform() must return all expected table keys."""

    EXPECTED_KEYS = {
        "customers", "products", "orders", "order_items",
        "inventory", "fact_sales", "daily_summary",
    }

    def test_all_expected_tables_returned(self, raw_dataframes):
        result = transform(raw_dataframes)
        assert self.EXPECTED_KEYS == set(result.keys())

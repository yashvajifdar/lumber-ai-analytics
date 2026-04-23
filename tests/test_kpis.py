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
        # Jan 2024: O001 (69.90+90.00) + O002 (13.98) + O006/C003 (69.90) = 243.78
        result = kpis.revenue_over_time("month")
        jan = result[result["period"] == "2024-01"]
        assert len(jan) == 1
        assert jan.iloc[0]["revenue"] == pytest.approx(243.78, abs=0.01)

    def test_known_january_gross_profit(self, test_db):
        # Jan 2024 GP: 34.90 + 30.00 + 6.98 + 34.90 (O006/C003) = 106.78
        result = kpis.revenue_over_time("month")
        jan = result[result["period"] == "2024-01"]
        assert jan.iloc[0]["gross_profit"] == pytest.approx(106.78, abs=0.01)

    def test_known_february_revenue(self, test_db):
        # Feb 2024: O004 (130.00) + O007/C003 (34.95) = 164.95
        result = kpis.revenue_over_time("month")
        feb = result[result["period"] == "2024-02"]
        assert len(feb) == 1
        assert feb.iloc[0]["revenue"] == pytest.approx(164.95, abs=0.01)

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


# ── sales_by_rep ──────────────────────────────────────────────────────────────

class TestSalesByRep:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.sales_by_rep(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.sales_by_rep()
        for col in ("sales_rep", "location", "revenue", "gross_profit", "margin_pct", "orders", "customers"):
            assert col in result.columns, f"Missing column: {col}"

    def test_known_mike_torres_revenue(self, test_db):
        # Mike Torres: O001 (69.90+90.00) + O004 (130.00) + O005 (41.25) = 331.15
        result = kpis.sales_by_rep()
        mike = result[result["sales_rep"] == "Mike Torres"]
        assert len(mike) == 1
        assert mike.iloc[0]["revenue"] == pytest.approx(331.15, abs=0.01)

    def test_known_sarah_chen_revenue(self, test_db):
        # Sarah Chen: O006 (69.90) + O007 (34.95) = 104.85
        result = kpis.sales_by_rep()
        sarah = result[result["sales_rep"] == "Sarah Chen"]
        assert len(sarah) == 1
        assert sarah.iloc[0]["revenue"] == pytest.approx(104.85, abs=0.01)

    def test_location_filter_excludes_other_yards(self, test_db):
        # Yard A only — Amanda Price (Yard B) must not appear
        result = kpis.sales_by_rep(location="Yard A")
        assert "Amanda Price" not in result["sales_rep"].values

    def test_location_filter_includes_yard_a_reps(self, test_db):
        result = kpis.sales_by_rep(location="Yard A")
        assert "Mike Torres" in result["sales_rep"].values
        assert "Sarah Chen" in result["sales_rep"].values

    def test_sorted_by_revenue_descending_by_default(self, test_db):
        result = kpis.sales_by_rep()
        revenues = result["revenue"].tolist()
        assert revenues == sorted(revenues, reverse=True)

    def test_sort_by_gross_profit(self, test_db):
        result = kpis.sales_by_rep(sort_by="gross_profit")
        gp = result["gross_profit"].tolist()
        assert gp == sorted(gp, reverse=True)

    def test_invalid_sort_by_defaults_to_revenue(self, test_db):
        # Should not raise — falls back to revenue
        result = kpis.sales_by_rep(sort_by="invalid_column")
        assert isinstance(result, pd.DataFrame)
        revenues = result["revenue"].tolist()
        assert revenues == sorted(revenues, reverse=True)

    def test_date_filter_restricts_results(self, test_db):
        # Filter to Jan 2024 only — O004 (Feb) and O005 (recent) excluded
        result = kpis.sales_by_rep(date_from="2024-01-01", date_to="2024-01-31")
        mike = result[result["sales_rep"] == "Mike Torres"]
        # Only O001 (159.90) in Jan for Mike Torres
        assert mike.iloc[0]["revenue"] == pytest.approx(159.90, abs=0.01)

    def test_orders_count_correct(self, test_db):
        # Mike Torres: 3 distinct orders (O001, O004, O005)
        result = kpis.sales_by_rep()
        mike = result[result["sales_rep"] == "Mike Torres"]
        assert mike.iloc[0]["orders"] == 3

    def test_customers_count_correct(self, test_db):
        # Mike Torres: 1 distinct customer (C001 on all orders)
        result = kpis.sales_by_rep()
        mike = result[result["sales_rep"] == "Mike Torres"]
        assert mike.iloc[0]["customers"] == 1


# ── inactive_customers ────────────────────────────────────────────────────────

class TestInactiveCustomers:
    def test_returns_dataframe(self, test_db):
        assert isinstance(kpis.inactive_customers(), pd.DataFrame)

    def test_has_required_columns(self, test_db):
        result = kpis.inactive_customers()
        for col in ("customer_id", "type", "location", "last_order_date",
                    "lifetime_revenue", "total_orders"):
            assert col in result.columns, f"Missing column: {col}"

    def test_c003_appears_as_inactive(self, test_db):
        # C003 has 2 orders (Jan/Feb 2024), both older than MAX(order_date) - 90 days
        result = kpis.inactive_customers(period="quarter")
        assert "C003" in result["customer_id"].values

    def test_active_customer_excluded(self, test_db):
        # C001 has O005 on RECENT_DATE — within the 90-day window → NOT inactive
        result = kpis.inactive_customers(period="quarter")
        assert "C001" not in result["customer_id"].values

    def test_single_order_customer_excluded(self, test_db):
        # C002 has only 1 order → excluded by HAVING total_orders >= 2
        result = kpis.inactive_customers(period="quarter")
        assert "C002" not in result["customer_id"].values

    def test_c003_lifetime_revenue(self, test_db):
        # C003: O006 (69.90) + O007 (34.95) = 104.85
        result = kpis.inactive_customers()
        c003 = result[result["customer_id"] == "C003"]
        assert c003.iloc[0]["lifetime_revenue"] == pytest.approx(104.85, abs=0.01)

    def test_c003_total_orders(self, test_db):
        result = kpis.inactive_customers()
        c003 = result[result["customer_id"] == "C003"]
        assert c003.iloc[0]["total_orders"] == 2

    def test_customer_type_filter(self, test_db):
        # Filter to Retail — C003 is Contractor, should not appear
        result = kpis.inactive_customers(customer_type="Retail")
        assert "C003" not in result["customer_id"].values

    def test_invalid_period_defaults_gracefully(self, test_db):
        # Unknown period falls back to 90-day default via dict.get
        result = kpis.inactive_customers(period="decade")
        assert isinstance(result, pd.DataFrame)

    def test_sorted_oldest_inactive_first(self, test_db):
        result = kpis.inactive_customers()
        if len(result) > 1:
            dates = result["last_order_date"].tolist()
            assert dates == sorted(dates)


# ── customer_cross_sell_gap ───────────────────────────────────────────────────

class TestCustomerCrossSellGap:
    def test_returns_dataframe(self, test_db):
        assert isinstance(
            kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods"),
            pd.DataFrame,
        )

    def test_has_required_columns(self, test_db):
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        for col in ("customer_id", "customer_name", "type", "location",
                    "revenue_on_has", "total_orders", "lifetime_revenue"):
            assert col in result.columns, f"Missing column: {col}"

    def test_excludes_customer_who_bought_both(self, test_db):
        # C001 bought Dimensional Lumber AND Sheet Goods → must not appear
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        assert "C001" not in result["customer_id"].values

    def test_includes_customers_missing_product(self, test_db):
        # C002 and C003 bought Dimensional Lumber but never Sheet Goods → must appear
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        assert "C002" in result["customer_id"].values
        assert "C003" in result["customer_id"].values

    def test_customer_names_present(self, test_db):
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        assert "John Smith" in result["customer_name"].values
        assert "SunriseDev Inc" in result["customer_name"].values

    def test_sorted_by_revenue_on_has_descending(self, test_db):
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        revs = result["revenue_on_has"].tolist()
        assert revs == sorted(revs, reverse=True)

    def test_c003_revenue_on_has(self, test_db):
        # C003 Dimensional Lumber revenue: O006 (69.90) + O007 (34.95) = 104.85
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods")
        c003 = result[result["customer_id"] == "C003"]
        assert c003.iloc[0]["revenue_on_has"] == pytest.approx(104.85, abs=0.01)

    def test_partial_name_match(self, test_db):
        # "Lumber" should match "Dimensional Lumber" category
        result = kpis.customer_cross_sell_gap("Lumber", "Sheet Goods")
        assert "C002" in result["customer_id"].values

    def test_no_results_when_all_bought_both(self, test_db):
        # "Sheet Goods" but not "Decking" — only C001 has Sheet Goods and they also have Decking
        result = kpis.customer_cross_sell_gap("Sheet Goods", "Decking")
        assert len(result) == 0

    def test_customer_type_filter(self, test_db):
        # Filter to Retail — C002 (Retail) in, C003 (Contractor) out
        result = kpis.customer_cross_sell_gap(
            "Dimensional Lumber", "Sheet Goods", customer_type="Retail"
        )
        assert "C002" in result["customer_id"].values
        assert "C003" not in result["customer_id"].values

    def test_n_limits_results(self, test_db):
        result = kpis.customer_cross_sell_gap("Dimensional Lumber", "Sheet Goods", n=1)
        assert len(result) == 1

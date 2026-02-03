from decimal import Decimal

import pytest

from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot


class TestReserveSnapshotUtilization:
    def test_utilization_normal_case(self):
        result = ReserveSnapshot.compute_utilization(
            supplied=Decimal("1000"),
            borrowed=Decimal("400"),
        )
        assert result == Decimal("0.4")

    def test_utilization_zero_supply(self):
        result = ReserveSnapshot.compute_utilization(
            supplied=Decimal("0"),
            borrowed=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_utilization_full_utilization(self):
        result = ReserveSnapshot.compute_utilization(
            supplied=Decimal("1000"),
            borrowed=Decimal("1000"),
        )
        assert result == Decimal("1")

    def test_utilization_very_small_values(self):
        result = ReserveSnapshot.compute_utilization(
            supplied=Decimal("0.000001"),
            borrowed=Decimal("0.0000004"),
        )
        assert result == Decimal("0.4")

    def test_utilization_large_values(self):
        result = ReserveSnapshot.compute_utilization(
            supplied=Decimal("1000000000000000000"),
            borrowed=Decimal("500000000000000000"),
        )
        assert result == Decimal("0.5")


class TestRateModelParams:
    @pytest.fixture
    def standard_rate_model(self):
        return RateModelParams(
            optimal_utilization_rate=Decimal("0.8"),
            base_variable_borrow_rate=Decimal("0"),
            variable_rate_slope1=Decimal("0.04"),
            variable_rate_slope2=Decimal("0.75"),
        )

    def test_compute_rate_at_zero_utilization(self, standard_rate_model):
        rate = standard_rate_model.compute_variable_borrow_rate(Decimal("0"))
        assert rate == Decimal("0")

    def test_compute_rate_below_optimal(self, standard_rate_model):
        rate = standard_rate_model.compute_variable_borrow_rate(Decimal("0.4"))
        expected = Decimal("0") + (Decimal("0.4") * Decimal("0.04") / Decimal("0.8"))
        assert rate == expected
        assert rate == Decimal("0.02")

    def test_compute_rate_at_optimal(self, standard_rate_model):
        rate = standard_rate_model.compute_variable_borrow_rate(Decimal("0.8"))
        expected = Decimal("0") + Decimal("0.04")
        assert rate == expected

    def test_compute_rate_above_optimal(self, standard_rate_model):
        rate = standard_rate_model.compute_variable_borrow_rate(Decimal("0.9"))
        excess = Decimal("0.9") - Decimal("0.8")
        excess_rate = Decimal("1") - Decimal("0.8")
        expected = Decimal("0") + Decimal("0.04") + (excess * Decimal("0.75") / excess_rate)
        assert rate == expected
        assert rate == Decimal("0.415")

    def test_compute_rate_at_full_utilization(self, standard_rate_model):
        rate = standard_rate_model.compute_variable_borrow_rate(Decimal("1.0"))
        expected = Decimal("0") + Decimal("0.04") + Decimal("0.75")
        assert rate == expected

    def test_base_rate_returned_at_zero_utilization(self):
        model = RateModelParams(
            optimal_utilization_rate=Decimal("0.8"),
            base_variable_borrow_rate=Decimal("0.02"),
            variable_rate_slope1=Decimal("0.04"),
            variable_rate_slope2=Decimal("0.75"),
        )

        rate = model.compute_variable_borrow_rate(Decimal("0"))

        assert rate == Decimal("0.02")

    def test_base_rate_plus_slope1_at_optimal_utilization(self):
        model = RateModelParams(
            optimal_utilization_rate=Decimal("0.8"),
            base_variable_borrow_rate=Decimal("0.02"),
            variable_rate_slope1=Decimal("0.04"),
            variable_rate_slope2=Decimal("0.75"),
        )

        rate = model.compute_variable_borrow_rate(Decimal("0.8"))

        assert rate == Decimal("0.06")

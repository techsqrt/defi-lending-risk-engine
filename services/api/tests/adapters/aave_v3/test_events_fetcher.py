"""Tests for EventsFetcher."""

import pytest

from services.api.src.api.adapters.aave_v3.events_fetcher import (
    EVENT_QUERIES,
    EVENT_RESPONSE_FIELDS,
    MockEventsFetcher,
)


class TestEventQueries:

    @pytest.mark.parametrize("event_type", ["supply", "withdraw", "borrow", "repay", "liquidation", "flashloan"])
    def test_uses_timestamp_gt_not_gte(self, event_type):
        query = EVENT_QUERIES[event_type]

        assert "timestamp_gt" in query
        assert "timestamp_gte" not in query

    @pytest.mark.parametrize("event_type", ["supply", "withdraw", "borrow", "repay", "liquidation", "flashloan"])
    def test_orders_ascending(self, event_type):
        query = EVENT_QUERIES[event_type]

        assert "orderDirection: asc" in query

    @pytest.mark.parametrize("event_type", ["supply", "withdraw", "borrow", "repay", "liquidation", "flashloan"])
    def test_has_response_field_mapping(self, event_type):
        assert event_type in EVENT_RESPONSE_FIELDS

    def test_supply_query_includes_required_fields(self):
        query = EVENT_QUERIES["supply"]

        for field in ["id", "timestamp", "amount", "user", "reserve"]:
            assert field in query

    def test_borrow_query_includes_borrow_rate(self):
        query = EVENT_QUERIES["borrow"]

        assert "borrowRate" in query

    def test_liquidation_query_includes_both_parties(self):
        query = EVENT_QUERIES["liquidation"]

        assert "user" in query
        assert "liquidator" in query

    def test_liquidation_query_includes_collateral_fields(self):
        query = EVENT_QUERIES["liquidation"]

        assert "collateralAmount" in query
        assert "collateralReserve" in query
        assert "principalAmount" in query
        assert "principalReserve" in query

    def test_flashloan_query_uses_initiator(self):
        query = EVENT_QUERIES["flashloan"]

        assert "initiator" in query


class TestMockEventsFetcher:

    def test_records_call_with_event_type_and_timestamp(self):
        fetcher = MockEventsFetcher()
        fetcher.set_mock_pages("supply", [[{"id": "1"}]])

        list(fetcher.fetch_events("supply", 100))

        assert fetcher.call_history == [("supply", 100)]

    def test_returns_empty_when_no_pages_configured(self):
        fetcher = MockEventsFetcher()

        pages = list(fetcher.fetch_events("supply", 0))

        assert pages == []

    def test_returns_configured_pages(self):
        fetcher = MockEventsFetcher()
        fetcher.set_mock_pages("supply", [[{"id": "1"}], [{"id": "2"}]])

        pages = list(fetcher.fetch_events("supply", 0))

        assert pages == [[{"id": "1"}], [{"id": "2"}]]

    def test_tracks_multiple_calls_separately(self):
        fetcher = MockEventsFetcher()
        fetcher.set_mock_pages("supply", [[]])
        fetcher.set_mock_pages("borrow", [[]])

        list(fetcher.fetch_events("supply", 100))
        list(fetcher.fetch_events("borrow", 200))

        assert fetcher.call_history == [("supply", 100), ("borrow", 200)]

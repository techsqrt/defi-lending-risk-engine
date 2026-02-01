import pytest

from services.api.src.api.adapters.aave_v3.fetcher import MockAaveV3Fetcher


class TestMockAaveV3Fetcher:
    """Tests for MockAaveV3Fetcher."""

    def test_fetch_reserves_records_call(self):
        fetcher = MockAaveV3Fetcher()
        fetcher.set_mock_response("reserves", {"data": {"reserves": []}})

        fetcher.fetch_reserves(["0xabc", "0xdef"])

        assert len(fetcher.call_history) == 1
        call_type, call_args = fetcher.call_history[0]
        assert call_type == "fetch_reserves"
        assert call_args["addresses"] == ["0xabc", "0xdef"]

    def test_fetch_reserves_returns_mock_data(self):
        fetcher = MockAaveV3Fetcher()
        mock_response = {
            "data": {
                "reserves": [{"underlyingAsset": "0xabc", "symbol": "TEST"}]
            }
        }
        fetcher.set_mock_response("reserves", mock_response)

        result = fetcher.fetch_reserves(["0xabc"])

        assert result == mock_response

    def test_fetch_reserves_returns_empty_when_not_set(self):
        fetcher = MockAaveV3Fetcher()

        result = fetcher.fetch_reserves(["0xabc"])

        assert result == {"data": {"reserves": []}}

    def test_fetch_reserve_history_records_call(self):
        fetcher = MockAaveV3Fetcher()

        fetcher.fetch_reserve_history("0xreserve123", 1700000000)

        assert len(fetcher.call_history) == 1
        call_type, call_args = fetcher.call_history[0]
        assert call_type == "fetch_reserve_history"
        assert call_args["reserve_id"] == "0xreserve123"
        assert call_args["from"] == 1700000000

    def test_fetch_reserve_history_returns_mock_data(self):
        fetcher = MockAaveV3Fetcher()
        mock_response = {
            "data": {
                "reserveParamsHistoryItems": [
                    {"id": "item1", "timestamp": 1700000000},
                    {"id": "item2", "timestamp": 1700003600},
                ]
            }
        }
        fetcher.set_mock_response("history", mock_response)

        result = fetcher.fetch_reserve_history("0xreserve", 1700000000)

        assert result == mock_response

    def test_fetch_reserve_history_returns_empty_when_not_set(self):
        fetcher = MockAaveV3Fetcher()

        result = fetcher.fetch_reserve_history("0xreserve", 1700000000)

        assert result == {"data": {"reserveParamsHistoryItems": []}}

    def test_multiple_calls_tracked_in_order(self):
        fetcher = MockAaveV3Fetcher()
        fetcher.set_mock_response("reserves", {"data": {"reserves": []}})

        fetcher.fetch_reserves(["0xfirst"])
        fetcher.fetch_reserve_history("0xhistory", 1700000000)
        fetcher.fetch_reserves(["0xsecond"])

        assert len(fetcher.call_history) == 3
        assert fetcher.call_history[0][0] == "fetch_reserves"
        assert fetcher.call_history[0][1]["addresses"] == ["0xfirst"]
        assert fetcher.call_history[1][0] == "fetch_reserve_history"
        assert fetcher.call_history[2][0] == "fetch_reserves"
        assert fetcher.call_history[2][1]["addresses"] == ["0xsecond"]

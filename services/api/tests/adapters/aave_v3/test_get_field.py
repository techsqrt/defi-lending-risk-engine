import pytest

from services.api.src.api.adapters.aave_v3.transformer import (
    TransformationError,
    _get_field,
)


class TestGetField:
    def test_returns_value_when_present(self):
        data = {"foo": "bar"}
        assert _get_field(data, "foo") == "bar"

    def test_raises_when_required_and_missing(self):
        data = {"foo": "bar"}
        with pytest.raises(TransformationError) as exc:
            _get_field(data, "baz")
        assert exc.value.field == "baz"

    def test_raises_when_required_and_none(self):
        data = {"foo": None}
        with pytest.raises(TransformationError) as exc:
            _get_field(data, "foo")
        assert exc.value.field == "foo"

    def test_returns_none_when_not_required_and_missing(self):
        data = {"foo": "bar"}
        assert _get_field(data, "baz", required=False) is None

    def test_returns_default_when_not_required_and_missing(self):
        data = {"foo": "bar"}
        assert _get_field(data, "baz", required=False, default="default") == "default"

    def test_returns_default_when_not_required_and_none(self):
        data = {"foo": None}
        assert _get_field(data, "foo", required=False, default="default") == "default"

    def test_returns_value_over_default_when_present(self):
        data = {"foo": "bar"}
        assert _get_field(data, "foo", required=False, default="default") == "bar"

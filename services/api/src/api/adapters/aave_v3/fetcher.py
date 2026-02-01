from typing import Any

import httpx

RESERVE_QUERY = """
query GetReserves($addresses: [String!]) {
  reserves(where: { underlyingAsset_in: $addresses }) {
    id
    underlyingAsset
    symbol
    name
    decimals
    totalLiquidity
    totalLiquidityAsCollateral
    availableLiquidity
    totalCurrentVariableDebt
    totalPrincipalStableDebt
    borrowingEnabled
    usageAsCollateralEnabled
    reserveFactor
    borrowCap
    supplyCap
    price {
      priceInEth
    }
    optimalUtilisationRate
    baseVariableBorrowRate
    variableRateSlope1
    variableRateSlope2
    stableRateSlope1
    stableRateSlope2
    lastUpdateTimestamp
  }
}
"""

RESERVE_HISTORY_QUERY = """
query GetReserveHistory($reserveId: String!, $from: Int!, $skip: Int!) {
  reserveParamsHistoryItems(
    where: { reserve: $reserveId, timestamp_gte: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    reserve {
      underlyingAsset
      symbol
      decimals
      borrowCap
      supplyCap
    }
    totalLiquidity
    availableLiquidity
    totalCurrentVariableDebt
    totalPrincipalStableDebt
    priceInEth
    priceInUsd
    timestamp
    variableBorrowRate
    liquidityRate
    stableBorrowRate
    utilizationRate
  }
}
"""


class AaveV3Fetcher:
    def __init__(self, subgraph_url: str, timeout: float = 30.0):
        self.subgraph_url = subgraph_url
        self.timeout = timeout

    def fetch_reserves(self, asset_addresses: list[str]) -> dict[str, Any]:
        """Fetch current reserve data for given asset addresses."""
        addresses_lower = [addr.lower() for addr in asset_addresses]

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.subgraph_url,
                json={
                    "query": RESERVE_QUERY,
                    "variables": {"addresses": addresses_lower},
                },
            )
            response.raise_for_status()
            return response.json()

    def fetch_reserve_history(
        self, reserve_id: str, from_timestamp: int, max_items: int = 5000
    ) -> dict[str, Any]:
        """Fetch historical reserve data from a given timestamp with pagination."""
        all_items: list[dict[str, Any]] = []
        skip = 0
        page_size = 1000

        with httpx.Client(timeout=self.timeout) as client:
            while len(all_items) < max_items:
                response = client.post(
                    self.subgraph_url,
                    json={
                        "query": RESERVE_HISTORY_QUERY,
                        "variables": {
                            "reserveId": reserve_id,
                            "from": from_timestamp,
                            "skip": skip,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("data", {}).get("reserveParamsHistoryItems", [])
                if not items:
                    break

                all_items.extend(items)
                skip += page_size

                # If we got fewer than page_size, we've reached the end
                if len(items) < page_size:
                    break

        return {"data": {"reserveParamsHistoryItems": all_items}}


class MockAaveV3Fetcher(AaveV3Fetcher):
    """Mock fetcher for testing without network calls."""

    def __init__(self, mock_data: dict[str, Any] | None = None):
        super().__init__("http://mock")
        self.mock_data = mock_data or {}
        self.call_history: list[tuple[str, dict]] = []

    def set_mock_response(self, query_type: str, response: dict[str, Any]) -> None:
        self.mock_data[query_type] = response

    def fetch_reserves(self, asset_addresses: list[str]) -> dict[str, Any]:
        self.call_history.append(("fetch_reserves", {"addresses": asset_addresses}))
        return self.mock_data.get("reserves", {"data": {"reserves": []}})

    def fetch_reserve_history(
        self, reserve_id: str, from_timestamp: int, max_items: int = 6000
    ) -> dict[str, Any]:
        self.call_history.append(
            ("fetch_reserve_history", {"reserve_id": reserve_id, "from": from_timestamp})
        )
        return self.mock_data.get(
            "history", {"data": {"reserveParamsHistoryItems": []}}
        )

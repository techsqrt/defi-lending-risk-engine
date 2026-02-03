"""Event fetcher for Aave V3 protocol events via subgraph."""

from typing import Any, Iterator

import httpx

# GraphQL queries for each event type
# All use timestamp_gt (not gte) to avoid re-fetching the last event
# All order by timestamp ASC for predictable pagination
EVENT_QUERIES = {
    "supply": """
query GetSupplies($from: Int!, $skip: Int!) {
  supplies(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    txHash
    timestamp
    amount
    assetPriceUSD
    user { id }
    caller { id }
    referrer { id }
    reserve { symbol underlyingAsset decimals }
  }
}
""",
    "withdraw": """
query GetWithdraws($from: Int!, $skip: Int!) {
  redeemUnderlyings(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    txHash
    timestamp
    amount
    assetPriceUSD
    user { id }
    to { id }
    reserve { symbol underlyingAsset decimals }
  }
}
""",
    "borrow": """
query GetBorrows($from: Int!, $skip: Int!) {
  borrows(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    txHash
    timestamp
    amount
    assetPriceUSD
    borrowRate
    borrowRateMode
    stableTokenDebt
    variableTokenDebt
    user { id }
    caller { id }
    referrer { id }
    reserve { symbol underlyingAsset decimals }
  }
}
""",
    "repay": """
query GetRepays($from: Int!, $skip: Int!) {
  repays(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    txHash
    timestamp
    amount
    assetPriceUSD
    useATokens
    user { id }
    repayer { id }
    reserve { symbol underlyingAsset decimals }
  }
}
""",
    "liquidation": """
query GetLiquidations($from: Int!, $skip: Int!) {
  liquidationCalls(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    txHash
    timestamp
    user { id }
    liquidator { id }
    collateralAmount
    collateralReserve { symbol underlyingAsset decimals }
    principalAmount
    principalReserve { symbol underlyingAsset decimals }
    collateralAssetPriceUSD
    borrowAssetPriceUSD
  }
}
""",
    "flashloan": """
query GetFlashLoans($from: Int!, $skip: Int!) {
  flashLoans(
    where: { timestamp_gt: $from }
    orderBy: timestamp
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    id
    timestamp
    amount
    assetPriceUSD
    initiator { id }
    target
    totalFee
    lpFee
    protocolFee
    reserve { symbol underlyingAsset decimals }
  }
}
""",
}

# Map event type to the response field name in GraphQL
EVENT_RESPONSE_FIELDS = {
    "supply": "supplies",
    "withdraw": "redeemUnderlyings",
    "borrow": "borrows",
    "repay": "repays",
    "liquidation": "liquidationCalls",
    "flashloan": "flashLoans",
}


class EventsFetcher:
    """Fetches protocol events from Aave V3 subgraph."""

    def __init__(self, subgraph_url: str, timeout: float = 30.0):
        self.subgraph_url = subgraph_url
        self.timeout = timeout

    def fetch_events(
        self, event_type: str, from_timestamp: int
    ) -> Iterator[list[dict[str, Any]]]:
        """
        Yield pages of events, oldest first. Paginate until exhausted.

        Args:
            event_type: One of 'supply', 'borrow', 'repay', 'liquidation', 'flashloan'
            from_timestamp: Unix timestamp to start from (exclusive - uses timestamp_gt)

        Yields:
            Pages of event dictionaries from the subgraph
        """
        if event_type not in EVENT_QUERIES:
            raise ValueError(f"Unknown event type: {event_type}")

        query = EVENT_QUERIES[event_type]
        response_field = EVENT_RESPONSE_FIELDS[event_type]
        skip = 0
        page_size = 1000

        with httpx.Client(timeout=self.timeout) as client:
            while True:
                response = client.post(
                    self.subgraph_url,
                    json={
                        "query": query,
                        "variables": {"from": from_timestamp, "skip": skip},
                    },
                )
                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    raise RuntimeError(f"GraphQL errors: {data['errors']}")

                page = data.get("data", {}).get(response_field, [])
                if not page:
                    break

                yield page
                skip += page_size

                # If we got fewer than page_size, we've reached the end
                if len(page) < page_size:
                    break


class MockEventsFetcher(EventsFetcher):
    """Mock fetcher for testing without network calls."""

    def __init__(self) -> None:
        super().__init__("http://mock")
        self._mock_pages: dict[str, list[list[dict[str, Any]]]] = {}
        self.call_history: list[tuple[str, int]] = []

    def set_mock_pages(
        self, event_type: str, pages: list[list[dict[str, Any]]]
    ) -> None:
        """Set mock pages to return for an event type."""
        self._mock_pages[event_type] = pages

    def fetch_events(
        self, event_type: str, from_timestamp: int
    ) -> Iterator[list[dict[str, Any]]]:
        """Return mock pages."""
        self.call_history.append((event_type, from_timestamp))
        pages = self._mock_pages.get(event_type, [])
        for page in pages:
            yield page

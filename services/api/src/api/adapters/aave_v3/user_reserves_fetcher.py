"""Fetcher for Aave V3 user reserve positions via subgraph."""

from typing import Any

import httpx

# Query to fetch all user reserves with position data
USER_RESERVES_QUERY = """
query GetUserReserves($skip: Int!) {
  userReserves(
    first: 1000
    skip: $skip
    where: {
      or: [
        { currentATokenBalance_gt: "0" }
        { currentVariableDebt_gt: "0" }
        { currentStableDebt_gt: "0" }
      ]
    }
  ) {
    id
    user {
      id
    }
    reserve {
      symbol
      underlyingAsset
      decimals
      baseLTVasCollateral
      reserveLiquidationThreshold
      reserveLiquidationBonus
      usageAsCollateralEnabled
      price {
        priceInUsd
      }
    }
    currentATokenBalance
    currentVariableDebt
    currentStableDebt
    usageAsCollateralEnabledOnUser
    lastUpdateTimestamp
  }
}
"""

# Query for reserve parameters (liquidation config)
RESERVES_CONFIG_QUERY = """
query GetReservesConfig {
  reserves {
    symbol
    underlyingAsset
    decimals
    baseLTVasCollateral
    reserveLiquidationThreshold
    reserveLiquidationBonus
    usageAsCollateralEnabled
    price {
      priceInUsd
    }
  }
}
"""


class UserReservesFetcher:
    """Fetches user reserve positions from Aave V3 subgraph."""

    def __init__(self, subgraph_url: str, timeout: float = 60.0):
        self.subgraph_url = subgraph_url
        self.timeout = timeout

    def fetch_all_user_reserves(self, max_users: int = 10000) -> list[dict[str, Any]]:
        """
        Fetch all user reserves with non-zero positions.

        Args:
            max_users: Maximum number of user reserve records to fetch

        Returns:
            List of user reserve records from subgraph
        """
        all_reserves: list[dict[str, Any]] = []
        skip = 0
        page_size = 1000

        with httpx.Client(timeout=self.timeout) as client:
            while len(all_reserves) < max_users:
                response = client.post(
                    self.subgraph_url,
                    json={
                        "query": USER_RESERVES_QUERY,
                        "variables": {"skip": skip},
                    },
                )
                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    raise RuntimeError(f"GraphQL errors: {data['errors']}")

                reserves = data.get("data", {}).get("userReserves", [])
                if not reserves:
                    break

                all_reserves.extend(reserves)
                skip += page_size

                # If we got fewer than page_size, we've reached the end
                if len(reserves) < page_size:
                    break

        return all_reserves[:max_users]

    def fetch_reserves_config(self) -> list[dict[str, Any]]:
        """
        Fetch reserve configuration (LTV, liquidation thresholds, etc.)

        Returns:
            List of reserve configurations
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.subgraph_url,
                json={"query": RESERVES_CONFIG_QUERY},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")

            return data.get("data", {}).get("reserves", [])

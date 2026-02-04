"""Fetcher for Aave V3 user reserve positions via subgraph."""

import os
from typing import Any

import httpx

# Chain-specific RPC URLs (public endpoints)
CHAIN_RPC_URLS = {
    "ethereum": os.environ.get("ETH_RPC_URL", "https://ethereum.publicnode.com"),
    "arbitrum": os.environ.get("ARBITRUM_RPC_URL", "https://arbitrum-one.publicnode.com"),
    "optimism": os.environ.get("OPTIMISM_RPC_URL", "https://optimism.publicnode.com"),
    "polygon": os.environ.get("POLYGON_RPC_URL", "https://polygon-bor.publicnode.com"),
    "base": os.environ.get("BASE_RPC_URL", "https://base.publicnode.com"),
}

# Aave V3 Oracle contract addresses by chain
AAVE_ORACLE_ADDRESSES = {
    "ethereum": "0x54586bE62E3c3580375aE3723C145253060Ca0C2",
    "arbitrum": "0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7",
    "optimism": "0xD81eb3728a631871a7eBBaD631b5f424909f0c77",
    "polygon": "0xb023e699F5a33916Ea823A16485e259257cA8Bd1",
    "base": "0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156",
}


def get_rpc_url(chain_id: str) -> str:
    """Get the RPC URL for a chain."""
    return CHAIN_RPC_URLS.get(chain_id, CHAIN_RPC_URLS["ethereum"])

# getAssetPrice(address) function selector
GET_ASSET_PRICE_SELECTOR = "0xb3596f07"

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
        priceInEth
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


def fetch_aave_oracle_price(
    asset_address: str,
    oracle_address: str,
    rpc_url: str,
) -> int | None:
    """
    Fetch asset price from Aave Oracle contract.

    Args:
        asset_address: Asset address (with 0x prefix)
        oracle_address: Aave Oracle contract address
        rpc_url: RPC URL for the chain

    Returns:
        Price as integer with 8 decimals, or None if failed
    """
    try:
        # Encode call: selector + padded address
        addr_padded = asset_address[2:].lower().zfill(64)
        data = GET_ASSET_PRICE_SELECTOR + addr_padded

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {"to": oracle_address, "data": data},
                "latest",
            ],
            "id": 1,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(rpc_url, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                return None

            hex_result = result.get("result", "0x")
            if len(hex_result) <= 2:
                return None

            price = int(hex_result, 16)
            return price if price > 0 else None

    except Exception:
        return None


def fetch_aave_oracle_prices(
    asset_addresses: list[str],
    chain_id: str = "ethereum",
) -> dict[str, str]:
    """
    Fetch prices from Aave Oracle for multiple assets.

    Args:
        asset_addresses: List of asset addresses (lowercase with 0x)
        chain_id: Chain ID to get oracle address and RPC URL

    Returns:
        Dict mapping asset address (lowercase) to price string (8 decimals)
    """
    oracle_address = AAVE_ORACLE_ADDRESSES.get(chain_id)
    if not oracle_address:
        return {}

    rpc_url = get_rpc_url(chain_id)
    prices: dict[str, str] = {}

    # Batch fetch prices (could be optimized with multicall but this works)
    for addr in asset_addresses:
        price = fetch_aave_oracle_price(addr, oracle_address, rpc_url)
        if price:
            prices[addr.lower()] = str(price)

    return prices


class UserReservesFetcher:
    """Fetches user reserve positions from Aave V3 subgraph."""

    def __init__(self, subgraph_url: str, chain_id: str = "ethereum", timeout: float = 60.0):
        self.subgraph_url = subgraph_url
        self.chain_id = chain_id
        self.timeout = timeout

    def fetch_all_user_reserves(self, max_users: int = 10000) -> list[dict[str, Any]]:
        """
        Fetch all user reserves with non-zero positions.

        Args:
            max_users: Maximum number of user reserve records to fetch

        Returns:
            List of user reserve records from subgraph, with priceInUsd injected
        """
        all_reserves: list[dict[str, Any]] = []
        skip = 0
        page_size = 1000
        all_asset_addresses: set[str] = set()

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

                # Collect all unique asset addresses
                for r in reserves:
                    addr = r["reserve"]["underlyingAsset"].lower()
                    all_asset_addresses.add(addr)

                all_reserves.extend(reserves)
                skip += page_size

                # If we got fewer than page_size, we've reached the end
                if len(reserves) < page_size:
                    break

        # Fetch ALL prices from Aave Oracle (the authoritative source)
        oracle_prices = fetch_aave_oracle_prices(
            list(all_asset_addresses),
            chain_id=self.chain_id,
        )

        # Inject prices into reserves
        for r in all_reserves:
            addr = r["reserve"]["underlyingAsset"].lower()
            price_obj = r["reserve"].get("price") or {}

            if addr in oracle_prices:
                price_obj["priceInUsd"] = oracle_prices[addr]

            r["reserve"]["price"] = price_obj

        return all_reserves[:max_users]

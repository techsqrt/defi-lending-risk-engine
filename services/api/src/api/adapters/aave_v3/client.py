from datetime import datetime, timezone
from typing import Sequence

from services.api.src.api.adapters.aave_v3.config import AaveV3Config, MarketConfig
from services.api.src.api.adapters.aave_v3.fetcher import AaveV3Fetcher
from services.api.src.api.adapters.aave_v3.transformer import (
    transform_history_item_to_snapshot,
    transform_rate_strategy,
    transform_reserve_to_snapshot,
)
from services.api.src.api.domain.models import ReserveSnapshot


class AaveV3Client:
    def __init__(self, config: AaveV3Config, fetcher_factory=AaveV3Fetcher):
        self.config = config
        self.fetcher_factory = fetcher_factory
        self._fetchers: dict[str, AaveV3Fetcher] = {}

    def _get_fetcher(self, chain_id: str) -> AaveV3Fetcher:
        if chain_id not in self._fetchers:
            chain = self.config.get_chain(chain_id)
            if not chain:
                raise ValueError(f"Unknown chain: {chain_id}")
            self._fetchers[chain_id] = self.fetcher_factory(chain.get_url())
        return self._fetchers[chain_id]

    def fetch_current_reserves(
        self, chain_id: str, market: MarketConfig
    ) -> list[ReserveSnapshot]:
        """Fetch current reserve snapshots for a market."""
        fetcher = self._get_fetcher(chain_id)
        addresses = [asset.address for asset in market.assets]

        response = fetcher.fetch_reserves(addresses)
        reserves_data = response.get("data", {}).get("reserves", [])

        snapshots = []
        for reserve_data in reserves_data:
            snapshot = transform_reserve_to_snapshot(
                reserve_data, chain_id, market.market_id
            )
            if snapshot:
                snapshots.append(snapshot)

        return snapshots

    def fetch_reserve_history(
        self,
        chain_id: str,
        market: MarketConfig,
        from_timestamp: int,
    ) -> list[ReserveSnapshot]:
        """Fetch historical reserve snapshots for a market from a given timestamp."""
        fetcher = self._get_fetcher(chain_id)
        snapshots = []

        current_response = fetcher.fetch_reserves(
            [asset.address for asset in market.assets]
        )
        current_reserves = current_response.get("data", {}).get("reserves", [])
        rate_models = {}
        for reserve in current_reserves:
            addr = reserve.get("underlyingAsset", "").lower()
            strategy = reserve.get("reserveInterestRateStrategy")
            if strategy:
                rate_models[addr] = transform_rate_strategy(strategy)

        for asset in market.assets:
            reserve_id = f"{asset.address.lower()}0x2f39d218133afab8f2b819b1066c7e434ad94e9e"

            response = fetcher.fetch_reserve_history(reserve_id, from_timestamp)
            items = response.get("data", {}).get("reserveParamsHistoryItems", [])

            rate_model = rate_models.get(asset.address.lower())

            for item in items:
                snapshot = transform_history_item_to_snapshot(
                    item, chain_id, market.market_id, rate_model
                )
                if snapshot:
                    snapshots.append(snapshot)

        return snapshots

    def fetch_all_current(self) -> list[ReserveSnapshot]:
        """Fetch current snapshots for all configured chains and markets."""
        all_snapshots = []

        for chain in self.config.chains:
            markets = self.config.get_markets_for_chain(chain.chain_id)
            for market in markets:
                snapshots = self.fetch_current_reserves(chain.chain_id, market)
                all_snapshots.extend(snapshots)

        return all_snapshots

    def fetch_all_history(
        self, hours: int = 6, interval_seconds: int = 3600
    ) -> list[ReserveSnapshot]:
        """Fetch historical snapshots for all configured chains and markets."""
        now = datetime.now(timezone.utc)
        from_timestamp = int(now.timestamp()) - (hours * interval_seconds)

        all_snapshots = []

        for chain in self.config.chains:
            markets = self.config.get_markets_for_chain(chain.chain_id)
            for market in markets:
                snapshots = self.fetch_reserve_history(
                    chain.chain_id, market, from_timestamp
                )
                all_snapshots.extend(snapshots)

        return self._dedupe_by_hour(all_snapshots)

    def _dedupe_by_hour(
        self, snapshots: Sequence[ReserveSnapshot]
    ) -> list[ReserveSnapshot]:
        """Keep only one snapshot per (chain, market, asset, hour)."""
        seen: dict[tuple, ReserveSnapshot] = {}
        for s in snapshots:
            key = (s.chain_id, s.market_id, s.asset_address, s.timestamp_hour)
            if key not in seen:
                seen[key] = s
        return list(seen.values())

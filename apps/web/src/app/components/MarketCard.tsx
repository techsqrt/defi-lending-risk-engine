'use client';

import Link from 'next/link';
import type { AssetOverview } from '@/lib/types';

interface MarketCardProps {
  chainId: string;
  marketId: string;
  marketName: string;
  assets: AssetOverview[];
}

function formatNumber(value: string | null, decimals: number = 2): string {
  if (!value) return 'N/A';
  const num = parseFloat(value);
  if (isNaN(num)) return 'N/A';
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function formatPercent(value: string | null): string {
  if (!value) return 'N/A';
  const num = parseFloat(value) * 100;
  if (isNaN(num)) return 'N/A';
  return `${num.toFixed(2)}%`;
}

function formatUSD(value: string | null): string {
  if (!value) return 'N/A';
  const num = parseFloat(value);
  if (isNaN(num)) return 'N/A';
  if (num >= 1_000_000) {
    return `$${(num / 1_000_000).toFixed(2)}M`;
  }
  if (num >= 1_000) {
    return `$${(num / 1_000).toFixed(2)}K`;
  }
  return `$${num.toFixed(2)}`;
}

export function MarketCard({ chainId, marketId, marketName, assets }: MarketCardProps) {
  return (
    <div style={{
      border: '1px solid #ddd',
      borderRadius: '8px',
      marginBottom: '16px',
      overflow: 'hidden',
    }}>
      <div style={{
        background: '#f5f5f5',
        padding: '12px 16px',
        borderBottom: '1px solid #ddd',
        fontWeight: 'bold',
      }}>
        {marketName}
      </div>

      <div>
        {assets.map((asset) => (
          <div
            key={asset.asset_address}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '12px 16px',
              borderBottom: '1px solid #eee',
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                {asset.asset_symbol}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>
                Utilization: {formatPercent(asset.utilization)}
              </div>
            </div>

            <div style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: '#888' }}>Supplied</div>
              <div>{formatNumber(asset.supplied_amount)} {asset.asset_symbol}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                {formatUSD(asset.supplied_value_usd)}
              </div>
            </div>

            <div style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: '#888' }}>Borrowed</div>
              <div>{formatNumber(asset.borrowed_amount)} {asset.asset_symbol}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                {formatUSD(asset.borrowed_value_usd)}
              </div>
            </div>

            <div style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: '#888' }}>Price</div>
              <div>{formatUSD(asset.price_usd)}</div>
            </div>

            <div style={{ flex: 0 }}>
              <Link
                href={`/markets/${chainId}/${marketId}/${asset.asset_address}`}
                style={{
                  padding: '6px 12px',
                  background: '#0066cc',
                  color: '#fff',
                  borderRadius: '4px',
                  textDecoration: 'none',
                  fontSize: '14px',
                }}
              >
                Details
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

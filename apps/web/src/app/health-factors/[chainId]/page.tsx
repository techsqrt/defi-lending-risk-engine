'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ComposedChart,
  AreaChart,
  Area,
  Bar,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { fetchHealthFactorAnalysis, fetchHealthFactorHistory } from '@/lib/api';
import type {
  HealthFactorAnalysis,
  HealthFactorHistory,
  LiquidationSimulation,
  UserHealthFactor,
  ReserveConfig,
} from '@/lib/types';

// Format USD with proper compact notation
function formatUSD(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

function formatUSDShort(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatHF(hf: number | null): string {
  if (hf === null) return 'N/A';
  if (hf > 100) return '>100';
  return hf.toFixed(2);
}

function shortenAddress(addr: string): string {
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

// Color based on HF value (only for HF >= 1.0)
function getHFColor(hf: number | null): string {
  if (hf === null) return '#94a3b8';
  if (hf < 1.1) return '#ea580c'; // Orange - critical
  if (hf < 1.25) return '#f59e0b'; // Amber - warning
  if (hf < 1.5) return '#eab308'; // Yellow - caution
  return '#22c55e'; // Green - healthy
}

// Chart colors for distribution buckets (risk gradient: red -> green)
function getBucketColor(bucket: string): string {
  if (bucket === '1.0-1.1') return '#dc2626';   // Red - critical
  if (bucket === '1.1-1.25') return '#ea580c';  // Orange - high risk
  if (bucket === '1.25-1.5') return '#f59e0b';  // Amber - warning
  if (bucket === '1.5-2.0') return '#eab308';   // Yellow - caution
  if (bucket === '2.0-3.0') return '#84cc16';   // Lime - moderate
  if (bucket === '3.0-5.0') return '#22c55e';   // Green - healthy
  return '#10b981';                              // Teal - very healthy
}

// Section component
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '20px',
      marginBottom: '20px',
    }}>
      <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>{title}</h2>
      {children}
    </div>
  );
}

// Stat card component
function StatCard({ label, value, subValue }: { label: string; value: string; subValue?: string }) {
  return (
    <div style={{
      background: '#f8fafc',
      borderRadius: '6px',
      padding: '16px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '24px', fontWeight: '700', color: '#1e293b' }}>{value}</div>
      {subValue && <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{subValue}</div>}
    </div>
  );
}

// Simulation card component
function SimulationCard({ sim, title }: { sim: LiquidationSimulation; title: string }) {
  return (
    <div style={{
      background: sim.users_at_risk > 0 ? '#fef2f2' : '#f0fdf4',
      border: `1px solid ${sim.users_at_risk > 0 ? '#fecaca' : '#bbf7d0'}`,
      borderRadius: '8px',
      padding: '16px',
    }}>
      <div style={{ fontWeight: '600', marginBottom: '12px', color: '#1e293b' }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '13px' }}>
        <div>
          <span style={{ color: '#64748b' }}>Price: </span>
          <span style={{ fontWeight: '500' }}>${sim.simulated_price_usd.toFixed(2)}</span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Users at risk: </span>
          <span style={{ fontWeight: '600', color: sim.users_at_risk > 0 ? '#dc2626' : '#22c55e' }}>
            {sim.users_at_risk}
          </span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Collateral at risk: </span>
          <span style={{ fontWeight: '500' }}>{formatUSD(sim.total_collateral_at_risk_usd)}</span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Debt at risk: </span>
          <span style={{ fontWeight: '500' }}>{formatUSD(sim.total_debt_at_risk_usd)}</span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Liquidatable debt: </span>
          <span style={{ fontWeight: '500' }}>{formatUSD(sim.estimated_liquidatable_debt_usd)}</span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Liquidator profit: </span>
          <span style={{ fontWeight: '500', color: '#16a34a' }}>
            {formatUSD(sim.estimated_liquidator_profit_usd)}
          </span>
        </div>
      </div>
    </div>
  );
}

const RESERVES_PER_PAGE = 10;
const USER_PAGE_SIZES = [10, 25, 50, 100];

// Bucket order and colors for historical chart (risk gradient: red -> green)
const BUCKET_ORDER = ['1.0-1.1', '1.1-1.25', '1.25-1.5', '1.5-2.0', '2.0-3.0', '3.0-5.0', '> 5.0'];
const BUCKET_COLORS: Record<string, string> = {
  '1.0-1.1': '#dc2626',   // Red - critical
  '1.1-1.25': '#ea580c',  // Orange - high risk
  '1.25-1.5': '#f59e0b',  // Amber - warning
  '1.5-2.0': '#eab308',   // Yellow - caution
  '2.0-3.0': '#84cc16',   // Lime - moderate
  '3.0-5.0': '#22c55e',   // Green - healthy
  '> 5.0': '#10b981',     // Teal - very healthy
};

export default function HealthFactorsPage() {
  const params = useParams();
  const chainId = params.chainId as string;

  const [data, setData] = useState<HealthFactorAnalysis | null>(null);
  const [history, setHistory] = useState<HealthFactorHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reservePage, setReservePage] = useState(0);
  const [userPage, setUserPage] = useState(0);
  const [userPageSize, setUserPageSize] = useState(25);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setReservePage(0);
    setUserPage(0);

    // Fetch main analysis and history in parallel
    Promise.all([
      fetchHealthFactorAnalysis(chainId),
      fetchHealthFactorHistory(chainId, 100).catch(() => null),  // Don't fail if no history
    ])
      .then(([analysisData, historyData]) => {
        setData(analysisData);
        setHistory(historyData);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [chainId]);

  if (loading) {
    return (
      <main style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        <Link href="/" style={{ color: '#0066cc', display: 'block', marginBottom: '16px' }}>
          &larr; Back to Overview
        </Link>
        <h1>Health Factor Analysis</h1>
        <p>Loading user positions from subgraph...</p>
        <p style={{ fontSize: '13px', color: '#64748b' }}>This may take a moment for large datasets.</p>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        <Link href="/" style={{ color: '#0066cc', display: 'block', marginBottom: '16px' }}>
          &larr; Back to Overview
        </Link>
        <h1>Health Factor Analysis</h1>
        <div style={{ color: '#dc2626', background: '#fef2f2', padding: '16px', borderRadius: '8px' }}>
          Error: {error}
        </div>
      </main>
    );
  }

  if (!data) {
    return null;
  }

  const { summary, weth_simulation } = data;
  const atRiskUsers = summary.at_risk_users || [];
  const totalUserPages = Math.ceil(atRiskUsers.length / userPageSize);

  // Pre-calculate max values for bar scaling in at-risk users table
  const maxCollateral = atRiskUsers.length > 0 ? Math.max(...atRiskUsers.map(u => u.total_collateral_usd)) : 0;
  const maxDebt = atRiskUsers.length > 0 ? Math.max(...atRiskUsers.map(u => u.total_debt_usd)) : 0;
  const barWidth = 60; // pixels

  return (
    <main style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Link href="/" style={{ color: '#0066cc', display: 'block', marginBottom: '16px' }}>
        &larr; Back to Overview
      </Link>

      <h1 style={{ marginBottom: '8px' }}>Health Factor Analysis</h1>
      <p style={{ color: '#64748b', marginBottom: '12px' }}>
        {summary.chain_id.charAt(0).toUpperCase() + summary.chain_id.slice(1)}
      </p>

      {/* Data Source Info */}
      {summary.data_source && (
        <div style={{
          background: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '24px',
          fontSize: '13px',
        }}>
          <strong>Data Source:</strong> {summary.data_source.price_source} &bull;{' '}
          <span style={{ color: '#64748b' }}>Oracle:</span>{' '}
          <code style={{ background: '#e0f2fe', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
            {summary.data_source.oracle_address}
          </code>{' '}
          &bull; <span style={{ color: '#64748b' }}>RPC:</span> {summary.data_source.rpc_url} &bull;{' '}
          <span style={{ color: '#64748b' }}>Snapshot:</span> {summary.data_source.snapshot_time_utc}
        </div>
      )}

      {/* Summary Stats */}
      <Section title="Overview">
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '12px',
        }}>
          <StatCard label="Total Users" value={summary.total_users.toLocaleString()} />
          <StatCard label="Users with Debt" value={summary.users_with_debt.toLocaleString()} />
          <StatCard
            label="At Risk (HF 1.0-1.5)"
            value={summary.users_at_risk.toLocaleString()}
            subValue={`${((summary.users_at_risk / summary.users_with_debt) * 100 || 0).toFixed(1)}%`}
          />
          <StatCard label="Total Collateral" value={formatUSD(summary.total_collateral_usd)} />
          <StatCard label="Total Debt" value={formatUSD(summary.total_debt_usd)} />
        </div>
      </Section>

      {/* Reserve Configs */}
      <Section title="Liquidation Parameters">
        <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '12px' }}>
          Sorted by total value in protocol (collateral + debt)
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left', padding: '8px' }}>Asset</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Price (USD)</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Total Value</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Max LTV</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Liq. Threshold</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Liq. Bonus</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Close Factor</th>
              </tr>
            </thead>
            <tbody>
              {summary.reserve_configs
                .slice(reservePage * RESERVES_PER_PAGE, (reservePage + 1) * RESERVES_PER_PAGE)
                .map((rc) => (
                <tr key={rc.address} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '8px', fontWeight: '500' }}>{rc.symbol}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>${rc.price_usd.toFixed(2)}</td>
                  <td style={{ padding: '8px', textAlign: 'right', color: '#64748b', fontSize: '12px' }}>
                    {formatUSD((rc.total_collateral_usd || 0) + (rc.total_debt_usd || 0))}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{formatPercent(rc.ltv)}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{formatPercent(rc.liquidation_threshold)}</td>
                  <td style={{ padding: '8px', textAlign: 'right', color: '#16a34a' }}>
                    {formatPercent(rc.liquidation_bonus)}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>50%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '12px',
          fontSize: '13px',
        }}>
          <span style={{ color: '#64748b' }}>
            Showing {reservePage * RESERVES_PER_PAGE + 1}-
            {Math.min((reservePage + 1) * RESERVES_PER_PAGE, summary.reserve_configs.length)} of {summary.reserve_configs.length} assets
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setReservePage(p => Math.max(0, p - 1))}
              disabled={reservePage === 0}
              style={{
                padding: '6px 12px',
                border: '1px solid #e5e7eb',
                borderRadius: '4px',
                background: reservePage === 0 ? '#f5f5f5' : '#fff',
                cursor: reservePage === 0 ? 'not-allowed' : 'pointer',
                color: reservePage === 0 ? '#9ca3af' : '#1e293b',
              }}
            >
              Previous
            </button>
            <button
              onClick={() => setReservePage(p => p + 1)}
              disabled={(reservePage + 1) * RESERVES_PER_PAGE >= summary.reserve_configs.length}
              style={{
                padding: '6px 12px',
                border: '1px solid #e5e7eb',
                borderRadius: '4px',
                background: (reservePage + 1) * RESERVES_PER_PAGE >= summary.reserve_configs.length ? '#f5f5f5' : '#fff',
                cursor: (reservePage + 1) * RESERVES_PER_PAGE >= summary.reserve_configs.length ? 'not-allowed' : 'pointer',
                color: (reservePage + 1) * RESERVES_PER_PAGE >= summary.reserve_configs.length ? '#9ca3af' : '#1e293b',
              }}
            >
              Next
            </button>
          </div>
        </div>
      </Section>

      {/* HF Distribution Chart */}
      <Section title="Health Factor Distribution">
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart data={summary.distribution} margin={{ top: 20, right: 60, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11 }}
              tickFormatter={(value) => formatUSDShort(value)}
              label={{ value: 'Collateral Volume', angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: '#64748b' } }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11 }}
              label={{ value: 'Users', angle: 90, position: 'insideRight', style: { fontSize: 11, fill: '#64748b' } }}
            />
            <Tooltip
              formatter={(value: number, name: string) => {
                if (name === 'Users') return [value.toLocaleString(), 'Users'];
                if (name === 'Collateral') return [formatUSD(value), 'Collateral'];
                return [value, name];
              }}
              labelFormatter={(label) => `HF: ${label}`}
            />
            <Bar yAxisId="left" dataKey="total_collateral_usd" name="Collateral">
              {summary.distribution.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBucketColor(entry.bucket)} />
              ))}
            </Bar>
            <Scatter
              yAxisId="right"
              dataKey="count"
              name="Users"
              fill="#374151"
              shape="circle"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '12px', fontSize: '12px', flexWrap: 'wrap' }}>
          <span><span style={{ color: '#dc2626' }}>&#9632;</span> Critical (1.0-1.1)</span>
          <span><span style={{ color: '#ea580c' }}>&#9632;</span> High Risk (1.1-1.25)</span>
          <span><span style={{ color: '#f59e0b' }}>&#9632;</span> Warning (1.25-1.5)</span>
          <span><span style={{ color: '#22c55e' }}>&#9632;</span> Healthy (&gt;1.5)</span>
          <span><span style={{ color: '#374151' }}>&#9679;</span> Users</span>
        </div>
      </Section>

      {/* Historical Collateral Distribution (Normalized) */}
      {history && history.snapshots.length > 1 && (() => {
        // Transform history data to normalized percentages with numeric timestamp for proper scaling
        const chartData = history.snapshots.map((snapshot) => {
          const totalCollateral = BUCKET_ORDER.reduce(
            (sum, bucket) => sum + (snapshot.buckets[bucket]?.collateral || 0),
            0
          );
          const ts = new Date(snapshot.snapshot_time).getTime();
          const row: Record<string, number | string> = {
            timestamp: ts,
            timeLabel: new Date(snapshot.snapshot_time).toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              timeZone: 'UTC',
            }) + ' UTC',
          };
          // Calculate percentages for each bucket
          BUCKET_ORDER.forEach((bucket) => {
            const collateral = snapshot.buckets[bucket]?.collateral || 0;
            row[bucket] = totalCollateral > 0 ? (collateral / totalCollateral) * 100 : 0;
          });
          return row;
        });

        // Format timestamp for X-axis tick
        const formatXAxis = (ts: number) => {
          const d = new Date(ts);
          return d.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'UTC',
          });
        };

        return (
          <Section title="Historical Collateral Distribution by Health Factor">
            <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '12px' }}>
              Normalized distribution showing the proportion of total collateral in each health factor bucket over time
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }} stackOffset="expand">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  scale="time"
                  domain={['dataMin', 'dataMax']}
                  tickFormatter={formatXAxis}
                  tick={{ fontSize: 10 }}
                  angle={-45}
                  textAnchor="end"
                  height={70}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                  domain={[0, 1]}
                />
                <Tooltip
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, `HF ${name}`]}
                  labelFormatter={(ts) => formatXAxis(ts as number) + ' UTC'}
                />
                {/* Stack areas in reverse order so critical is at bottom (most visible) */}
                {[...BUCKET_ORDER].reverse().map((bucket) => (
                  <Area
                    key={bucket}
                    type="monotone"
                    dataKey={bucket}
                    stackId="1"
                    stroke={BUCKET_COLORS[bucket]}
                    fill={BUCKET_COLORS[bucket]}
                    fillOpacity={0.8}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginTop: '12px', fontSize: '11px', flexWrap: 'wrap' }}>
              {BUCKET_ORDER.map((bucket) => (
                <span key={bucket}>
                  <span style={{ color: BUCKET_COLORS[bucket] }}>&#9632;</span> {bucket}
                </span>
              ))}
            </div>
          </Section>
        );
      })()}

      {/* WETH Liquidation Simulations */}
      {weth_simulation && (
        <Section title="WETH Price Drop Simulation">
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
            What happens if WETH price drops? Current price: ${weth_simulation.drop_1_percent.original_price_usd.toFixed(2)}
          </p>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px',
          }}>
            <SimulationCard sim={weth_simulation.drop_1_percent} title="-1% Drop" />
            <SimulationCard sim={weth_simulation.drop_3_percent} title="-3% Drop" />
            <SimulationCard sim={weth_simulation.drop_5_percent} title="-5% Drop" />
            <SimulationCard sim={weth_simulation.drop_10_percent} title="-10% Drop" />
          </div>
        </Section>
      )}

      {/* At Risk Users Table (HF 1.0-1.5) */}
      <Section title={`At Risk Users (HF 1.0-1.5) - ${atRiskUsers.length} total`}>
        {atRiskUsers.length === 0 ? (
          <p style={{ color: '#22c55e', fontWeight: '500' }}>No users at risk currently.</p>
        ) : (
          <>
            {/* Page Size Selector */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', color: '#64748b' }}>Show:</span>
              {USER_PAGE_SIZES.map((size) => (
                <button
                  key={size}
                  onClick={() => { setUserPageSize(size); setUserPage(0); }}
                  style={{
                    padding: '4px 10px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '4px',
                    background: userPageSize === size ? '#3b82f6' : '#fff',
                    color: userPageSize === size ? '#fff' : '#1e293b',
                    cursor: 'pointer',
                    fontSize: '12px',
                  }}
                >
                  {size}
                </button>
              ))}
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                    <th style={{ textAlign: 'left', padding: '8px' }}>User</th>
                    <th style={{ textAlign: 'right', padding: '8px' }}>Health Factor</th>
                    <th style={{ textAlign: 'right', padding: '8px', minWidth: '150px' }}>Collateral</th>
                    <th style={{ textAlign: 'right', padding: '8px', minWidth: '150px' }}>Debt</th>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Positions</th>
                  </tr>
                </thead>
                <tbody>
                  {atRiskUsers
                    .slice(userPage * userPageSize, (userPage + 1) * userPageSize)
                    .map((user) => {
                      const collateralPct = maxCollateral > 0 ? (user.total_collateral_usd / maxCollateral) * 100 : 0;
                      const debtPct = maxDebt > 0 ? (user.total_debt_usd / maxDebt) * 100 : 0;
                      return (
                        <tr key={user.user_address} style={{ borderBottom: '1px solid #e5e7eb' }}>
                          <td style={{ padding: '8px' }}>
                            <a
                              href={`https://debank.com/profile/${user.user_address}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: '#0066cc', textDecoration: 'none' }}
                            >
                              {shortenAddress(user.user_address)}
                            </a>
                          </td>
                          <td style={{
                            padding: '8px',
                            textAlign: 'right',
                            fontWeight: '600',
                            color: getHFColor(user.health_factor),
                          }}>
                            {formatHF(user.health_factor)}
                          </td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                              <span>{formatUSD(user.total_collateral_usd)}</span>
                              <div style={{
                                width: `${barWidth}px`,
                                height: '8px',
                                background: '#e5e7eb',
                                borderRadius: '2px',
                                overflow: 'hidden',
                              }}>
                                <div style={{
                                  width: `${collateralPct}%`,
                                  height: '100%',
                                  background: '#3b82f6',
                                  borderRadius: '2px',
                                }} />
                              </div>
                            </div>
                          </td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                              <span>{formatUSD(user.total_debt_usd)}</span>
                              <div style={{
                                width: `${barWidth}px`,
                                height: '8px',
                                background: '#e5e7eb',
                                borderRadius: '2px',
                                overflow: 'hidden',
                              }}>
                                <div style={{
                                  width: `${debtPct}%`,
                                  height: '100%',
                                  background: '#64748b',
                                  borderRadius: '2px',
                                }} />
                              </div>
                            </div>
                          </td>
                          <td style={{ padding: '8px', fontSize: '12px', color: '#64748b' }}>
                            {user.positions.map((p) => (
                              <span key={p.asset_address} style={{ marginRight: '8px' }}>
                                {p.asset_symbol}: {p.collateral_usd > 0 ? `+${formatUSDShort(p.collateral_usd)}` : ''}
                                {p.debt_usd > 0 ? ` -${formatUSDShort(p.debt_usd)}` : ''}
                              </span>
                            ))}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '12px',
              fontSize: '13px',
            }}>
              <span style={{ color: '#64748b' }}>
                Showing {userPage * userPageSize + 1}-
                {Math.min((userPage + 1) * userPageSize, atRiskUsers.length)} of {atRiskUsers.length} users
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setUserPage(p => Math.max(0, p - 1))}
                  disabled={userPage === 0}
                  style={{
                    padding: '6px 12px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '4px',
                    background: userPage === 0 ? '#f5f5f5' : '#fff',
                    cursor: userPage === 0 ? 'not-allowed' : 'pointer',
                    color: userPage === 0 ? '#9ca3af' : '#1e293b',
                  }}
                >
                  Previous
                </button>
                <button
                  onClick={() => setUserPage(p => p + 1)}
                  disabled={(userPage + 1) * userPageSize >= atRiskUsers.length}
                  style={{
                    padding: '6px 12px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '4px',
                    background: (userPage + 1) * userPageSize >= atRiskUsers.length ? '#f5f5f5' : '#fff',
                    cursor: (userPage + 1) * userPageSize >= atRiskUsers.length ? 'not-allowed' : 'pointer',
                    color: (userPage + 1) * userPageSize >= atRiskUsers.length ? '#9ca3af' : '#1e293b',
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Section>
    </main>
  );
}

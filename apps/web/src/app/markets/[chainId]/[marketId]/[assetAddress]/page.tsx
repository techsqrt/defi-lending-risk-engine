'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  ReferenceDot,
  TooltipProps,
} from 'recharts';
import { fetchMarketHistory, fetchMarketLatest } from '@/lib/api';
import type { MarketHistory, LatestRawResponse, RateModel } from '@/lib/types';
import { TimePeriodSelector, TimePeriod, getHoursForPeriod } from '@/app/components/TimePeriodSelector';

interface ChartDataPoint {
  timestamp: string;
  time: string;
  fullTime: string;
  utilization: number | null;
  suppliedUsd: number | null;
  borrowedUsd: number | null;
  variableRate: number | null;
  liquidityRate: number | null;
}

// Format percentage consistently
function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A';
  return `${(value * 100).toFixed(2)}%`;
}

// Format APR consistently
function formatAPR(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A';
  return `${(value * 100).toFixed(2)}% APR`;
}

// Format USD with proper compact notation
function formatUSDCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A';
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

// Format USD for axis (shorter)
function formatUSDAxis(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

// Custom tooltip for utilization chart
function UtilizationTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as ChartDataPoint;
  return (
    <div style={{ background: 'white', border: '1px solid #ccc', padding: '10px', borderRadius: '4px', fontSize: '13px' }}>
      <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{data.fullTime}</div>
      <div>Utilization: <strong>{formatPercent(data.utilization)}</strong></div>
      <div>Borrow Rate: <strong>{formatAPR(data.variableRate)}</strong></div>
      <div>Supply Rate: <strong>{formatAPR(data.liquidityRate)}</strong></div>
    </div>
  );
}

// Custom tooltip for supply/borrow chart
function SupplyBorrowTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as ChartDataPoint;
  return (
    <div style={{ background: 'white', border: '1px solid #ccc', padding: '10px', borderRadius: '4px', fontSize: '13px' }}>
      <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{data.fullTime}</div>
      <div style={{ color: '#16a34a' }}>Supplied: <strong>{formatUSDCompact(data.suppliedUsd)}</strong></div>
      <div style={{ color: '#ea580c' }}>Borrowed: <strong>{formatUSDCompact(data.borrowedUsd)}</strong></div>
    </div>
  );
}

// Custom tooltip for interest rates chart
function RatesTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as ChartDataPoint;
  return (
    <div style={{ background: 'white', border: '1px solid #ccc', padding: '10px', borderRadius: '4px', fontSize: '13px' }}>
      <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{data.fullTime}</div>
      <div style={{ color: '#7c3aed' }}>Borrow Rate: <strong>{formatAPR(data.variableRate)}</strong></div>
      <div style={{ color: '#16a34a' }}>Supply Rate: <strong>{formatAPR(data.liquidityRate)}</strong></div>
    </div>
  );
}

export default function AssetDetailsPage() {
  const params = useParams();
  const chainId = params.chainId as string;
  const marketId = params.marketId as string;
  const assetAddress = params.assetAddress as string;

  const [history, setHistory] = useState<MarketHistory | null>(null);
  const [latest, setLatest] = useState<LatestRawResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRawJson, setShowRawJson] = useState(false);
  const [timePeriod, setTimePeriod] = useState<TimePeriod>('24H');

  useEffect(() => {
    setLoading(true);
    const hours = getHoursForPeriod(timePeriod);
    Promise.all([
      fetchMarketHistory(chainId, marketId, assetAddress, hours),
      fetchMarketLatest(chainId, marketId, assetAddress),
    ])
      .then(([historyData, latestData]) => {
        setHistory(historyData);
        setLatest(latestData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [chainId, marketId, assetAddress, timePeriod]);

  if (loading) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <Link href="/" style={{ color: '#0066cc' }}>&larr; Back to Overview</Link>
        <h1>Loading...</h1>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <Link href="/" style={{ color: '#0066cc' }}>&larr; Back to Overview</Link>
        <h1>Error</h1>
        <p style={{ color: 'red' }}>{error}</p>
      </main>
    );
  }

  if (!history || history.snapshots.length === 0) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <Link href="/" style={{ color: '#0066cc' }}>&larr; Back to Overview</Link>
        <h1>No Data</h1>
        <p>No historical data available for this asset.</p>
      </main>
    );
  }

  const chartData: ChartDataPoint[] = history.snapshots.map((s) => {
    const date = new Date(s.timestamp_hour);
    return {
      timestamp: s.timestamp_hour,
      time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      fullTime: date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
      utilization: s.utilization ? parseFloat(s.utilization) : null,
      suppliedUsd: s.supplied_value_usd ? parseFloat(s.supplied_value_usd) : null,
      borrowedUsd: s.borrowed_value_usd ? parseFloat(s.borrowed_value_usd) : null,
      variableRate: s.variable_borrow_rate ? parseFloat(s.variable_borrow_rate) : null,
      liquidityRate: s.liquidity_rate ? parseFloat(s.liquidity_rate) : null,
    };
  });

  const optimalUtil = history.rate_model?.optimal_utilization_rate
    ? parseFloat(history.rate_model.optimal_utilization_rate)
    : null;

  const currentUtilization = chartData.length > 0 ? chartData[chartData.length - 1].utilization : null;

  return (
    <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Link href="/" style={{ color: '#0066cc', display: 'block', marginBottom: '16px' }}>
        &larr; Back to Overview
      </Link>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <h1 style={{ margin: 0 }}>{history.asset_symbol}</h1>
        <TimePeriodSelector selected={timePeriod} onChange={setTimePeriod} />
      </div>
      <p style={{ color: '#666', marginBottom: '24px' }}>
        {chainId} / {marketId}
      </p>

      <div style={{ display: 'grid', gap: '24px' }}>
        {/* Utilization Chart */}
        <ChartSection title={`Utilization (${timePeriod})`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                domain={[0, 1]}
                tick={{ fontSize: 11 }}
                width={50}
              />
              <Tooltip content={<UtilizationTooltip />} />
              <Legend />
              {/* Optimal utilization reference line */}
              {optimalUtil !== null && (
                <ReferenceLine
                  y={optimalUtil}
                  stroke="#dc2626"
                  strokeWidth={2}
                  strokeDasharray="8 4"
                  label={{
                    value: `U_opt = ${formatPercent(optimalUtil)}`,
                    position: 'right',
                    fill: '#dc2626',
                    fontSize: 11,
                    fontWeight: 'bold',
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="utilization"
                name="Utilization"
                stroke="#7c3aed"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartSection>

        {/* Supply & Borrow Chart */}
        <ChartSection title={`Supply & Borrow Value (${timePeriod})`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis
                tickFormatter={formatUSDAxis}
                tick={{ fontSize: 11 }}
                width={50}
              />
              <Tooltip content={<SupplyBorrowTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="suppliedUsd"
                name="Supplied (USD)"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="borrowedUsd"
                name="Borrowed (USD)"
                stroke="#ea580c"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartSection>

        {/* Interest Rates Chart */}
        <ChartSection title={`Interest Rates (${timePeriod})`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis
                tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                tick={{ fontSize: 11 }}
                width={50}
              />
              <Tooltip content={<RatesTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="variableRate"
                name="Borrow APR"
                stroke="#7c3aed"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="liquidityRate"
                name="Supply APR"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartSection>

        {/* Interest Rate Model */}
        {history.rate_model && (
          <InterestRateModelSection
            rateModel={history.rate_model}
            currentUtilization={currentUtilization}
          />
        )}

        {/* Raw JSON Debug Panel */}
        <div style={{ border: '1px solid #ddd', borderRadius: '8px', overflow: 'hidden' }}>
          <button
            onClick={() => setShowRawJson(!showRawJson)}
            style={{
              width: '100%',
              padding: '12px 16px',
              background: '#f5f5f5',
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
              fontWeight: 'bold',
            }}
          >
            {showRawJson ? '▼' : '▶'} Raw JSON (Debug)
          </button>
          {showRawJson && (
            <pre style={{
              padding: '16px',
              background: '#1e1e1e',
              color: '#d4d4d4',
              overflow: 'auto',
              maxHeight: '400px',
              margin: 0,
              fontSize: '12px',
            }}>
              {JSON.stringify(latest?.snapshot ?? {}, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </main>
  );
}

function ChartSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ background: '#f5f5f5', padding: '12px 16px', borderBottom: '1px solid #ddd', fontWeight: 'bold' }}>
        {title}
      </div>
      <div style={{ padding: '16px' }}>
        {children}
      </div>
    </div>
  );
}

interface InterestRateModelProps {
  rateModel: RateModel;
  currentUtilization: number | null;
}

// Tooltip for rate model curve
function RateModelTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as { utilization: number; rate: number };
  return (
    <div style={{ background: 'white', border: '1px solid #ccc', padding: '10px', borderRadius: '4px', fontSize: '13px' }}>
      <div>Utilization: <strong>{formatPercent(data.utilization)}</strong></div>
      <div>Borrow Rate: <strong>{formatAPR(data.rate)}</strong></div>
    </div>
  );
}

function InterestRateModelSection({ rateModel, currentUtilization }: InterestRateModelProps) {
  const uOpt = rateModel.optimal_utilization_rate ? parseFloat(rateModel.optimal_utilization_rate) : null;
  const baseRate = rateModel.base_variable_borrow_rate ? parseFloat(rateModel.base_variable_borrow_rate) : null;
  const slope1 = rateModel.variable_rate_slope1 ? parseFloat(rateModel.variable_rate_slope1) : null;
  const slope2 = rateModel.variable_rate_slope2 ? parseFloat(rateModel.variable_rate_slope2) : null;

  if (uOpt === null || baseRate === null || slope1 === null || slope2 === null) {
    return null;
  }

  // Generate curve data points
  const curveData: { utilization: number; rate: number }[] = [];
  for (let u = 0; u <= 1; u += 0.005) {
    let rate: number;
    if (u <= uOpt) {
      rate = baseRate + (u / uOpt) * slope1;
    } else {
      rate = baseRate + slope1 + ((u - uOpt) / (1 - uOpt)) * slope2;
    }
    curveData.push({ utilization: u, rate });
  }

  // Calculate rate at current utilization
  let currentRate: number | null = null;
  if (currentUtilization !== null) {
    if (currentUtilization <= uOpt) {
      currentRate = baseRate + (currentUtilization / uOpt) * slope1;
    } else {
      currentRate = baseRate + slope1 + ((currentUtilization - uOpt) / (1 - uOpt)) * slope2;
    }
  }

  // Rate at optimal (kink point)
  const kinkRate = baseRate + slope1;

  // Max rate for Y-axis
  const maxRate = baseRate + slope1 + slope2;

  return (
    <ChartSection title="Interest Rate Model (Borrow APR vs Utilization)">
      <div style={{ marginBottom: '16px' }}>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={curveData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
            <XAxis
              dataKey="utilization"
              type="number"
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              domain={[0, 1]}
              tick={{ fontSize: 12 }}
              label={{ value: 'Utilization', position: 'bottom', offset: 0, fontSize: 12 }}
            />
            <YAxis
              type="number"
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              domain={[0, Math.ceil(maxRate * 100) / 100 + 0.1]}
              tick={{ fontSize: 12 }}
              label={{ value: 'Borrow APR', angle: -90, position: 'insideLeft', fontSize: 12 }}
            />
            <Tooltip content={<RateModelTooltip />} />

            {/* Optimal utilization (kink) vertical line */}
            <ReferenceLine
              x={uOpt}
              stroke="#dc2626"
              strokeWidth={2}
              strokeDasharray="8 4"
              label={{
                value: `U_opt = ${formatPercent(uOpt)}`,
                position: 'insideTopRight',
                fill: '#dc2626',
                fontSize: 11,
                fontWeight: 'bold',
                offset: 10,
              }}
            />

            <Line
              type="monotone"
              dataKey="rate"
              name="Borrow APR"
              stroke="#7c3aed"
              strokeWidth={3}
              dot={false}
            />

            {/* CURRENT POSITION - crosshair (vertical + horizontal lines) - rendered AFTER Line to be on top */}
            {currentUtilization !== null && currentRate !== null && (
              <>
                {/* Vertical line at current utilization */}
                <ReferenceLine
                  x={currentUtilization}
                  stroke="#16a34a"
                  strokeWidth={3}
                  ifOverflow="extendDomain"
                  label={{
                    value: `NOW: ${formatPercent(currentUtilization)}`,
                    position: 'top',
                    fill: '#16a34a',
                    fontSize: 12,
                    fontWeight: 'bold',
                  }}
                />
                {/* Horizontal line at current rate */}
                <ReferenceLine
                  y={currentRate}
                  stroke="#16a34a"
                  strokeWidth={3}
                  ifOverflow="extendDomain"
                  label={{
                    value: `R = ${formatAPR(currentRate)}`,
                    position: 'right',
                    fill: '#16a34a',
                    fontSize: 12,
                    fontWeight: 'bold',
                  }}
                />
                {/* Center dot at intersection */}
                <ReferenceDot
                  x={currentUtilization}
                  y={currentRate}
                  r={10}
                  fill="#16a34a"
                  stroke="#fff"
                  strokeWidth={3}
                  ifOverflow="extendDomain"
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Current Position Info */}
      {currentUtilization !== null && currentRate !== null && (
        <div style={{
          background: currentUtilization > uOpt ? '#fef2f2' : '#f0fdf4',
          border: `1px solid ${currentUtilization > uOpt ? '#fecaca' : '#bbf7d0'}`,
          padding: '14px 18px',
          borderRadius: '6px',
          marginBottom: '20px',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            background: '#16a34a',
            flexShrink: 0,
          }} />
          <div>
            <strong>Current Position:</strong>{' '}
            Utilization <strong>{formatPercent(currentUtilization)}</strong>{' '}
            &rarr; Borrow Rate <strong>{formatAPR(currentRate)}</strong>
            {currentUtilization > uOpt && (
              <span style={{ color: '#dc2626', marginLeft: '12px', fontWeight: 'bold' }}>
                Above optimal utilization (steep rate zone)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Formula Section */}
      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '20px', borderRadius: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <strong style={{ fontSize: '15px' }}>Rate Model Formula</strong>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              background: '#94a3b8',
              color: 'white',
              fontSize: '11px',
              cursor: 'help',
            }}
            title="Aave uses a piecewise linear interest rate model. Below optimal utilization, rates increase gradually (slope1). Above optimal, rates increase steeply (slope2) to incentivize repayments and discourage further borrowing."
          >
            ?
          </span>
        </div>

        {/* Utilization definition */}
        <div style={{ marginBottom: '16px', padding: '12px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
          <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: '14px' }}>
            <strong>Utilization:</strong> U = Total Borrowed / Total Supplied
          </div>
        </div>

        {/* Piecewise formula */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>Borrow Rate R(U):</div>
          <div style={{ display: 'grid', gap: '8px' }}>
            <div style={{
              padding: '10px 14px',
              background: currentUtilization !== null && currentUtilization <= uOpt ? '#f0fdf4' : '#fff',
              border: `1px solid ${currentUtilization !== null && currentUtilization <= uOpt ? '#bbf7d0' : '#e2e8f0'}`,
              borderRadius: '4px',
              fontFamily: 'ui-monospace, monospace',
              fontSize: '13px',
            }}>
              <span style={{ color: '#64748b' }}>If U ≤ U<sub>opt</sub>:</span>{' '}
              <strong>R = R<sub>base</sub> + (U / U<sub>opt</sub>) × slope<sub>1</sub></strong>
            </div>
            <div style={{
              padding: '10px 14px',
              background: currentUtilization !== null && currentUtilization > uOpt ? '#fef2f2' : '#fff',
              border: `1px solid ${currentUtilization !== null && currentUtilization > uOpt ? '#fecaca' : '#e2e8f0'}`,
              borderRadius: '4px',
              fontFamily: 'ui-monospace, monospace',
              fontSize: '13px',
            }}>
              <span style={{ color: '#64748b' }}>If U &gt; U<sub>opt</sub>:</span>{' '}
              <strong>R = R<sub>base</sub> + slope<sub>1</sub> + ((U − U<sub>opt</sub>) / (1 − U<sub>opt</sub>)) × slope<sub>2</sub></strong>
            </div>
          </div>
        </div>

        {/* Parameter values */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '12px',
          fontSize: '13px',
        }}>
          <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <div style={{ color: '#64748b', marginBottom: '4px' }}>Optimal Utilization (U<sub>opt</sub>)</div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{formatPercent(uOpt)}</div>
          </div>
          <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <div style={{ color: '#64748b', marginBottom: '4px' }}>Base Rate (R<sub>base</sub>)</div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{formatPercent(baseRate)}</div>
          </div>
          <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <div style={{ color: '#64748b', marginBottom: '4px' }}>Slope 1 (below optimal)</div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{formatPercent(slope1)}</div>
          </div>
          <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <div style={{ color: '#64748b', marginBottom: '4px' }}>Slope 2 (above optimal)</div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{formatPercent(slope2)}</div>
          </div>
        </div>

        {/* Key rates */}
        <div style={{ marginTop: '16px', padding: '12px', background: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
          <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>Key Rates:</div>
          <div style={{ display: 'flex', gap: '24px', fontSize: '13px' }}>
            <div>
              At 0% utilization: <strong>{formatPercent(baseRate)}</strong>
            </div>
            <div>
              At U<sub>opt</sub> ({formatPercent(uOpt)}): <strong>{formatPercent(kinkRate)}</strong>
            </div>
            <div>
              At 100% utilization: <strong>{formatPercent(maxRate)}</strong>
            </div>
          </div>
        </div>
      </div>
    </ChartSection>
  );
}

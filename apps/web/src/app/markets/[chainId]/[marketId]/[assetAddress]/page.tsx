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
import {
  fetchMarketHistory,
  fetchMarketLatest,
  fetchDebugSnapshots,
  fetchDebugEvents,
  fetchDebugStats,
} from '@/lib/api';
import type {
  MarketHistory,
  LatestRawResponse,
  RateModel,
  DebugSnapshotsResponse,
  DebugEventsResponse,
  DebugStatsResponse,
} from '@/lib/types';
import { TimePeriodSelector, TimePeriod, getPeriodConfig } from '@/app/components/TimePeriodSelector';

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

// Format relative time
function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

// Calculate next snapshot time (scheduler runs hourly at :00)
function getNextSnapshotTime(): Date {
  const now = new Date();
  const next = new Date(now);
  next.setMinutes(0, 0, 0);
  next.setHours(next.getHours() + 1);
  return next;
}

function formatTimeUntil(date: Date): string {
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins <= 0) return 'any moment';
  if (diffMins < 60) return `in ${diffMins}m`;
  return `in ${Math.floor(diffMins / 60)}h ${diffMins % 60}m`;
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
  const [timePeriod, setTimePeriod] = useState<TimePeriod>('24H');

  // Debug panel states
  const [showSnapshotsDebug, setShowSnapshotsDebug] = useState(false);
  const [showEventsDebug, setShowEventsDebug] = useState(false);
  const [showStatsDebug, setShowStatsDebug] = useState(false);
  const [debugSnapshots, setDebugSnapshots] = useState<DebugSnapshotsResponse | null>(null);
  const [debugEvents, setDebugEvents] = useState<DebugEventsResponse | null>(null);
  const [debugStats, setDebugStats] = useState<DebugStatsResponse | null>(null);
  const ALL_EVENT_TYPES = ['supply', 'withdraw', 'borrow', 'repay', 'liquidation', 'flashloan'];
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>(ALL_EVENT_TYPES);
  const [eventLimitFilter, setEventLimitFilter] = useState<number>(10);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchMarketHistory(chainId, marketId, assetAddress, timePeriod),
      fetchMarketLatest(chainId, marketId, assetAddress),
    ])
      .then(([historyData, latestData]) => {
        setHistory(historyData);
        setLatest(latestData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [chainId, marketId, assetAddress, timePeriod]);

  // Load debug snapshots when panel opens
  useEffect(() => {
    if (showSnapshotsDebug && !debugSnapshots) {
      fetchDebugSnapshots(chainId, assetAddress)
        .then(setDebugSnapshots)
        .catch(console.error);
    }
  }, [showSnapshotsDebug, chainId, assetAddress, debugSnapshots]);

  // Load debug events when panel opens or filters change
  useEffect(() => {
    if (showEventsDebug) {
      // If all types selected, pass undefined (no filter) for efficiency
      const typesToFetch = selectedEventTypes.length === ALL_EVENT_TYPES.length ? undefined : selectedEventTypes;
      fetchDebugEvents(chainId, assetAddress, typesToFetch, eventLimitFilter)
        .then(setDebugEvents)
        .catch(console.error);
    }
  }, [showEventsDebug, chainId, assetAddress, selectedEventTypes, eventLimitFilter]);

  // Load debug stats when panel opens
  useEffect(() => {
    if (showStatsDebug && !debugStats) {
      fetchDebugStats(chainId, assetAddress)
        .then(setDebugStats)
        .catch(console.error);
    }
  }, [showStatsDebug, chainId, assetAddress, debugStats]);

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

  const periodConfig = getPeriodConfig(timePeriod);
  const isDaily = periodConfig.granularity === 'day';

  // Format datetime in UTC - always include short date + time
  const formatUTCDateTime = (isoString: string): string => {
    // Parse ISO string and extract UTC components directly
    // ISO format: "2026-02-01T00:00:00+00:00" or "2026-02-01T00:00:00Z"
    const match = isoString.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!match) return isoString;

    const [, year, monthStr, dayStr, hourStr, minStr] = match;
    const month = parseInt(monthStr, 10);
    const day = parseInt(dayStr, 10);
    const hour = parseInt(hourStr, 10);

    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const monthName = monthNames[month - 1];
    const hour12 = hour % 12 || 12;
    const ampm = hour >= 12 ? 'PM' : 'AM';

    return `${monthName} ${day}, ${hour12}:${minStr} ${ampm}`;
  };

  // Build chart data with full datetime labels (all in UTC)
  const chartData: ChartDataPoint[] = history.snapshots.map((s) => {
    // Always show full date + time: "Feb 1, 12:00 AM"
    const timeLabel = formatUTCDateTime(s.timestamp_hour);
    const fullTimeLabel = `${timeLabel} UTC`;

    return {
      timestamp: s.timestamp_hour,
      time: timeLabel,
      fullTime: fullTimeLabel,
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

  // Get latest snapshot time (keep as ISO string and as Date for relative time)
  const latestSnapshotIso = history.snapshots.length > 0
    ? history.snapshots[history.snapshots.length - 1].timestamp_hour
    : null;
  const latestSnapshotDate = latestSnapshotIso ? new Date(latestSnapshotIso) : null;
  const nextSnapshotTime = getNextSnapshotTime();

  // Format snapshot times in UTC from ISO string
  const formatSnapshotTimeUTC = (isoString: string): string => {
    const match = isoString.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!match) return isoString;

    const [, , monthStr, dayStr, hourStr, minStr] = match;
    const month = parseInt(monthStr, 10);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${monthNames[month - 1]} ${parseInt(dayStr, 10)}, ${hourStr}:${minStr}`;
  };

  const formatNextSnapshotUTC = (date: Date): string => {
    const hours = date.getUTCHours().toString().padStart(2, '0');
    const minutes = date.getUTCMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  return (
    <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Link href="/" style={{ color: '#0066cc', display: 'block', marginBottom: '16px' }}>
        &larr; Back to Overview
      </Link>

      <h1 style={{ marginBottom: '8px' }}>{history.asset_symbol}</h1>
      <p style={{ color: '#666', marginBottom: '16px' }}>
        {chainId} / {marketId}
      </p>

      {/* Snapshot Status Table */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '12px',
        marginBottom: '16px',
        padding: '16px',
        background: '#f8fafc',
        borderRadius: '8px',
        border: '1px solid #e2e8f0',
      }}>
        <div>
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Latest Snapshot</div>
          <div style={{ fontSize: '14px', fontWeight: '600' }}>
            {latestSnapshotIso && latestSnapshotDate
              ? `${formatSnapshotTimeUTC(latestSnapshotIso)} UTC (${formatRelativeTime(latestSnapshotDate)})`
              : 'N/A'
            }
          </div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Next Snapshot</div>
          <div style={{ fontSize: '14px', fontWeight: '600' }}>
            {formatNextSnapshotUTC(nextSnapshotTime)} UTC ({formatTimeUntil(nextSnapshotTime)})
          </div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Current Utilization</div>
          <div style={{ fontSize: '14px', fontWeight: '600' }}>
            {formatPercent(currentUtilization)}
          </div>
        </div>
      </div>

      {/* Time Period Selector + UTC note */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ fontSize: '12px', color: '#64748b' }}>
          All times are in UTC
        </div>
        <TimePeriodSelector selected={timePeriod} onChange={setTimePeriod} />
      </div>

      <div style={{ display: 'grid', gap: '24px' }}>
        {/* Utilization Chart */}
        <ChartSection title="Utilization">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                interval={Math.max(0, Math.ceil(chartData.length / 8) - 1)}
                angle={-25}
                textAnchor="end"
                height={50}
              />
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
        <ChartSection title="Supply & Borrow Value">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                interval={Math.max(0, Math.ceil(chartData.length / 8) - 1)}
                angle={-25}
                textAnchor="end"
                height={50}
              />
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
        <ChartSection title="Interest Rates">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 30, right: 100, bottom: 20, left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                interval={Math.max(0, Math.ceil(chartData.length / 8) - 1)}
                angle={-25}
                textAnchor="end"
                height={50}
              />
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

        {/* Debug Panel 1: Snapshots */}
        <DebugPanel
          title="Debug: Snapshots (Newest & Oldest)"
          isOpen={showSnapshotsDebug}
          onToggle={() => setShowSnapshotsDebug(!showSnapshotsDebug)}
        >
          {debugSnapshots ? (
            <div style={{ display: 'grid', gap: '16px' }}>
              <div style={{ fontSize: '13px', color: '#64748b' }}>
                Total snapshots: <strong>{debugSnapshots.total_snapshots}</strong>
              </div>
              <div>
                <div style={{ fontWeight: '600', marginBottom: '8px' }}>Newest Snapshot:</div>
                <pre style={{ background: '#f8fafc', padding: '12px', borderRadius: '4px', fontSize: '11px', overflow: 'auto', maxHeight: '200px' }}>
                  {JSON.stringify(debugSnapshots.newest, null, 2)}
                </pre>
              </div>
              <div>
                <div style={{ fontWeight: '600', marginBottom: '8px' }}>Oldest Snapshot:</div>
                <pre style={{ background: '#f8fafc', padding: '12px', borderRadius: '4px', fontSize: '11px', overflow: 'auto', maxHeight: '200px' }}>
                  {JSON.stringify(debugSnapshots.oldest, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div>Loading...</div>
          )}
        </DebugPanel>

        {/* Debug Panel 2: Events */}
        <DebugPanel
          title="Debug: Events (Latest & Earliest)"
          isOpen={showEventsDebug}
          onToggle={() => setShowEventsDebug(!showEventsDebug)}
        >
          <div style={{ display: 'grid', gap: '16px' }}>
            {/* Filters */}
            <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px' }}>Event Types:</div>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  {ALL_EVENT_TYPES.map((type) => (
                    <label key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selectedEventTypes.includes(type)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedEventTypes([...selectedEventTypes, type]);
                          } else {
                            setSelectedEventTypes(selectedEventTypes.filter((t) => t !== type));
                          }
                        }}
                      />
                      {type}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px' }}>Latest count:</div>
                <select
                  value={eventLimitFilter}
                  onChange={(e) => setEventLimitFilter(Number(e.target.value))}
                  style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #ddd' }}
                >
                  <option value={1}>1</option>
                  <option value={3}>3</option>
                  <option value={10}>10</option>
                  <option value={30}>30</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>

            {debugEvents ? (
              <>
                <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>
                  Matching events: <strong>{debugEvents.total_matching_events.toLocaleString()}</strong>
                  {debugEvents.event_type_filter && debugEvents.event_type_filter.length > 0 && (
                    <span> (filtered: {debugEvents.event_type_filter.join(', ')})</span>
                  )}
                </div>
                <div>
                  <div style={{ fontWeight: '600', marginBottom: '8px' }}>Latest {debugEvents.latest.length} Events:</div>
                  <EventsTable events={debugEvents.latest} />
                </div>
                <div>
                  <div style={{ fontWeight: '600', marginBottom: '8px' }}>Earliest 3 Events:</div>
                  <EventsTable events={debugEvents.earliest} />
                </div>
              </>
            ) : (
              <div>Loading...</div>
            )}
          </div>
        </DebugPanel>

        {/* Debug Panel 3: Stats */}
        <DebugPanel
          title="Debug: Statistics"
          isOpen={showStatsDebug}
          onToggle={() => setShowStatsDebug(!showStatsDebug)}
        >
          {debugStats ? (
            <div style={{ display: 'grid', gap: '16px' }}>
              {/* Overall stats */}
              <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '4px' }}>
                <div style={{ fontWeight: '600', marginBottom: '12px' }}>Overall Summary</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '13px' }}>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Total Events</div>
                    <div style={{ fontWeight: '600', fontSize: '16px' }}>{debugStats.overall.total_events.toLocaleString()}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Unique Users</div>
                    <div style={{ fontWeight: '600', fontSize: '16px' }}>{debugStats.overall.total_unique_users.toLocaleString()}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Days Covered</div>
                    <div style={{ fontWeight: '600', fontSize: '16px' }}>{debugStats.overall.total_unique_days}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>First Event</div>
                    <div style={{ fontWeight: '600' }}>
                      {debugStats.overall.min_timestamp
                        ? new Date(debugStats.overall.min_timestamp * 1000).toLocaleString('en-US', { timeZone: 'UTC' }) + ' UTC'
                        : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Last Event</div>
                    <div style={{ fontWeight: '600' }}>
                      {debugStats.overall.max_timestamp
                        ? new Date(debugStats.overall.max_timestamp * 1000).toLocaleString('en-US', { timeZone: 'UTC' }) + ' UTC'
                        : 'N/A'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats by event type */}
              <div>
                <div style={{ fontWeight: '600', marginBottom: '12px' }}>By Event Type</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9' }}>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Type</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Count</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Users</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Total USD</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Avg USD</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>First</th>
                        <th style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Last</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(debugStats.by_event_type).map(([type, stats]) => {
                        const totalUsd = parseFloat(stats.total_usd) || 0;
                        const avgUsd = stats.count > 0 ? totalUsd / stats.count : 0;
                        return (
                          <tr key={type}>
                            <td style={{ padding: '8px', borderBottom: '1px solid #eee', fontWeight: '500' }}>{type}</td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee' }}>{stats.count.toLocaleString()}</td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee' }}>{stats.unique_users.toLocaleString()}</td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee' }}>
                              {formatUSDCompact(totalUsd)}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee' }}>
                              {formatUSDCompact(avgUsd)}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee', fontSize: '11px' }}>
                              {new Date(stats.min_timestamp * 1000).toLocaleDateString('en-US', { timeZone: 'UTC' })}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #eee', fontSize: '11px' }}>
                              {new Date(stats.max_timestamp * 1000).toLocaleDateString('en-US', { timeZone: 'UTC' })}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Quick summary */}
              <div style={{ background: '#f0fdf4', padding: '12px', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
                <div style={{ fontWeight: '600', marginBottom: '8px' }}>Quick Summary</div>
                <div style={{ fontSize: '13px', display: 'grid', gap: '4px' }}>
                  {debugStats.by_event_type.supply && (
                    <div>
                      Deposits: <strong>{debugStats.by_event_type.supply.count.toLocaleString()}</strong> events,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.supply.total_usd))}</strong> total,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.supply.total_usd) / debugStats.by_event_type.supply.count)}</strong> avg
                    </div>
                  )}
                  {debugStats.by_event_type.withdraw && (
                    <div>
                      Withdrawals: <strong>{debugStats.by_event_type.withdraw.count.toLocaleString()}</strong> events,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.withdraw.total_usd))}</strong> total
                    </div>
                  )}
                  {debugStats.by_event_type.borrow && (
                    <div>
                      Borrows: <strong>{debugStats.by_event_type.borrow.count.toLocaleString()}</strong> events,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.borrow.total_usd))}</strong> total
                    </div>
                  )}
                  {debugStats.by_event_type.repay && (
                    <div>
                      Repays: <strong>{debugStats.by_event_type.repay.count.toLocaleString()}</strong> events,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.repay.total_usd))}</strong> total
                    </div>
                  )}
                  {debugStats.by_event_type.liquidation && (
                    <div>
                      Liquidations: <strong>{debugStats.by_event_type.liquidation.count.toLocaleString()}</strong> events
                    </div>
                  )}
                  {debugStats.by_event_type.flashloan && (
                    <div>
                      Flashloans: <strong>{debugStats.by_event_type.flashloan.count.toLocaleString()}</strong> events,
                      <strong> {formatUSDCompact(parseFloat(debugStats.by_event_type.flashloan.total_usd))}</strong> total
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div>Loading...</div>
          )}
        </DebugPanel>
      </div>
    </main>
  );
}

function DebugPanel({ title, isOpen, onToggle, children }: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '8px', overflow: 'hidden' }}>
      <button
        onClick={onToggle}
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
        {isOpen ? '▼' : '▶'} {title}
      </button>
      {isOpen && (
        <div style={{ padding: '16px' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function EventsTable({ events }: { events: DebugEventsResponse['latest'] }) {
  if (events.length === 0) {
    return <div style={{ color: '#64748b', fontSize: '13px' }}>No events found</div>;
  }

  // Get explorer URL based on chain
  const getExplorerTxUrl = (chainId: string, txHash: string): string => {
    if (chainId === 'base') return `https://basescan.org/tx/${txHash}`;
    return `https://etherscan.io/tx/${txHash}`;
  };

  // Get Debank profile URL for user
  const getDebankUrl = (address: string): string => {
    return `https://debank.com/profile/${address}`;
  };

  // Format timestamp from unix to UTC string
  const formatTimestampUTC = (timestamp: number): string => {
    const date = new Date(timestamp * 1000);
    const month = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
    const day = date.getUTCDate();
    const hours = date.getUTCHours().toString().padStart(2, '0');
    const mins = date.getUTCMinutes().toString().padStart(2, '0');
    return `${month} ${day}, ${hours}:${mins}`;
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
        <thead>
          <tr style={{ background: '#f1f5f9' }}>
            <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Type</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Time (UTC)</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Tx</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>User</th>
            <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Amount USD</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td style={{ padding: '6px 8px', borderBottom: '1px solid #eee' }}>
                <span style={{
                  background: event.event_type === 'supply' ? '#dcfce7' :
                             event.event_type === 'withdraw' ? '#fef3c7' :
                             event.event_type === 'borrow' ? '#dbeafe' :
                             event.event_type === 'repay' ? '#f3e8ff' :
                             event.event_type === 'liquidation' ? '#fee2e2' :
                             '#f1f5f9',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  fontWeight: '500',
                }}>
                  {event.event_type}
                </span>
              </td>
              <td style={{ padding: '6px 8px', borderBottom: '1px solid #eee' }}>
                {formatTimestampUTC(event.timestamp)}
              </td>
              <td style={{ padding: '6px 8px', borderBottom: '1px solid #eee', fontFamily: 'monospace', fontSize: '10px' }}>
                {event.tx_hash ? (
                  <a
                    href={getExplorerTxUrl(event.chain_id, event.tx_hash)}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#0066cc', textDecoration: 'none' }}
                  >
                    {event.tx_hash.slice(0, 8)}...
                  </a>
                ) : (
                  <span style={{ color: '#999' }}>-</span>
                )}
              </td>
              <td style={{ padding: '6px 8px', borderBottom: '1px solid #eee', fontFamily: 'monospace', fontSize: '10px' }}>
                <a
                  href={getDebankUrl(event.user_address)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#0066cc', textDecoration: 'none' }}
                >
                  {event.user_address.slice(0, 6)}...{event.user_address.slice(-4)}
                </a>
              </td>
              <td style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid #eee' }}>
                {event.amount_usd ? formatUSDCompact(parseFloat(event.amount_usd)) : 'N/A'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

'use client';

export type TimePeriod = '24H' | '7D' | 'MTD' | '30D' | 'ALL';

// Granularity determines how data is aggregated
export type Granularity = 'hour' | 'day';

interface PeriodConfig {
  value: TimePeriod;
  label: string;
  granularity: Granularity;
}

interface TimePeriodSelectorProps {
  selected: TimePeriod;
  onChange: (period: TimePeriod) => void;
}

const PERIODS: PeriodConfig[] = [
  { value: '24H', label: '24H', granularity: 'hour' },
  { value: '7D', label: '7D', granularity: 'hour' },
  { value: 'MTD', label: 'MTD', granularity: 'day' },
  { value: '30D', label: '30D', granularity: 'day' },
  { value: 'ALL', label: 'All', granularity: 'day' },
];

export function getPeriodConfig(period: TimePeriod): PeriodConfig {
  const config = PERIODS.find((x) => x.value === period);
  return config ?? PERIODS[0];
}

export function TimePeriodSelector({ selected, onChange }: TimePeriodSelectorProps) {
  return (
    <div style={{ display: 'inline-flex', gap: '4px', background: '#f1f5f9', borderRadius: '6px', padding: '4px' }}>
      {PERIODS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          style={{
            padding: '6px 14px',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: selected === p.value ? '600' : '400',
            background: selected === p.value ? '#fff' : 'transparent',
            color: selected === p.value ? '#1e293b' : '#64748b',
            boxShadow: selected === p.value ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
            transition: 'all 0.15s ease',
            fontSize: '13px',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

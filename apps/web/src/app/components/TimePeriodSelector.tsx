'use client';

export type TimePeriod = '1H' | '24H' | '7D';

interface TimePeriodSelectorProps {
  selected: TimePeriod;
  onChange: (period: TimePeriod) => void;
}

const PERIODS: { value: TimePeriod; label: string; hours: number }[] = [
  { value: '1H', label: '1H', hours: 1 },
  { value: '24H', label: '24H', hours: 24 },
  { value: '7D', label: '7D', hours: 168 },
];

export function getHoursForPeriod(period: TimePeriod): number {
  const p = PERIODS.find((x) => x.value === period);
  return p?.hours ?? 24;
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

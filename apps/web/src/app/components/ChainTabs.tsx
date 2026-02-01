'use client';

interface ChainTabsProps {
  chains: string[];
  activeChain: string;
  onChainChange: (chainId: string) => void;
}

export function ChainTabs({ chains, activeChain, onChainChange }: ChainTabsProps) {
  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
      {chains.map((chainId) => (
        <button
          key={chainId}
          onClick={() => onChainChange(chainId)}
          style={{
            padding: '8px 16px',
            border: '1px solid #333',
            borderRadius: '4px',
            background: activeChain === chainId ? '#333' : 'transparent',
            color: activeChain === chainId ? '#fff' : '#333',
            cursor: 'pointer',
            fontWeight: activeChain === chainId ? 'bold' : 'normal',
          }}
        >
          {chainId}
        </button>
      ))}
    </div>
  );
}

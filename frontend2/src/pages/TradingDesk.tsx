import { useState, useEffect } from 'react'
import LeftPanel from '../components/LeftPanel.tsx'
import Chart from '../components/Chart.tsx'
import { api } from '../api/client.ts'
import type { WorkspaceStatus } from '../api/types.ts'

export default function TradingDesk() {
  const [symbol, setSymbol] = useState('2330.TW')
  const [account, setAccount] = useState<WorkspaceStatus | null>(null)

  useEffect(() => {
    api.account().then(setAccount).catch(() => {})
  }, [])

  const cash = account ? Math.round(account.cash).toLocaleString() : '—'
  const av = account ? Math.round(account.account_value).toLocaleString() : '—'
  const profile = account?.market_profile ?? ''

  return (
    <div className="flex h-full w-full overflow-hidden">
      <LeftPanel selectedSymbol={symbol} onSelectSymbol={setSymbol} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* top bar */}
        <div className="h-9 shrink-0 flex items-center justify-between px-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-sm text-gray-900 tabular">
              {symbol.replace('.TW', '').replace('.TWO', '')}
            </span>
            {profile && (
              <span className="text-xs text-gray-400 uppercase tracking-wide">{profile}</span>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500 tabular">
            <span>Cash <span className="text-gray-700 font-medium">{cash}</span></span>
            <span>NAV <span className="text-gray-700 font-medium">{av}</span></span>
          </div>
        </div>

        {/* chart */}
        <div className="flex-1 min-h-0">
          <Chart symbol={symbol} />
        </div>
      </div>
    </div>
  )
}

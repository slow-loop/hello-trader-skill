import { trades } from '../data'

function actionBadge(action: string) {
  if (action === 'BUY') return 'bg-green-100 text-green-800'
  if (action === 'SELL') return 'bg-red-100 text-red-800'
  return 'bg-neutral-100 text-neutral-800'
}

export default function Trades() {
  const sorted = [...trades].sort((a, b) => b.executed_at.localeCompare(a.executed_at))
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-black">交易紀錄</h1>
      {sorted.length === 0 && <p className="text-neutral-500 text-sm">沒有交易紀錄。</p>}
      <div className="bg-white border border-neutral-200 rounded-md overflow-hidden">
        {sorted.map((t, i) => {
          const date = t.executed_at.slice(0, 10)
          const time = t.executed_at.slice(11, 16)
          const total = t.price * t.quantity
          const pnlNum = t.pnl ?? null
          return (
            <div key={i} className="px-4 py-3 border-b border-neutral-100 last:border-b-0">
              <div className="flex items-center gap-3 text-sm">
                <span className="font-mono font-bold text-neutral-900">{date}</span>
                <span className="font-mono text-neutral-500">{time} UTC</span>
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${actionBadge(t.action)}`}>{t.action}</span>
                <span className="font-mono font-bold">{t.symbol}</span>
                <span className="text-neutral-600">{t.quantity} 股 @ {t.price}</span>
                <span className="text-neutral-500 text-xs">手續費 {t.fee.toFixed(2)}</span>
                {t.strategy && <span className="text-neutral-400 text-xs">{t.strategy}</span>}
              </div>
              <div className="flex items-center gap-4 mt-1 text-xs text-neutral-500">
                <span>成本 {total.toLocaleString()} 元</span>
                {pnlNum !== null && (
                  <span className={pnlNum >= 0 ? 'text-green-700' : 'text-red-700'}>
                    PnL {pnlNum >= 0 ? '+' : ''}{pnlNum.toLocaleString()}
                  </span>
                )}
              </div>
              {t.reason && (
                <p className="mt-1 text-xs text-neutral-600 leading-relaxed">{t.reason}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

import { tradesFromJournals } from '../data'

export default function Trades() {
  const trades = tradesFromJournals()
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-black">交易紀錄</h1>
      {trades.length === 0 && <p className="text-neutral-500 text-sm">沒有交易紀錄。</p>}
      <div className="bg-white border border-neutral-200 rounded-md overflow-hidden">
        {trades.map((t, i) => (
          <div key={i} className="px-4 py-3 border-b border-neutral-100 last:border-b-0">
            <div className="flex items-center gap-3 text-sm">
              <span className="font-mono font-bold text-neutral-900">{t.date}</span>
              <span className="font-mono text-neutral-500">{t.at}</span>
            </div>
            <ul className="mt-1 space-y-0.5 text-sm">
              {t.actions.map((a, j) => (
                <li key={j} className="font-mono text-green-800">{a}</li>
              ))}
            </ul>
            {t.notes.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-neutral-700 space-y-0.5">
                {t.notes.map((n, j) => <li key={j}>{n}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

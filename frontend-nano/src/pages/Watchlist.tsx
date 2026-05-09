import { Link } from 'react-router-dom'
import { watchlist } from '../data'

const statusCls = (s: string) =>
  s === 'hold' ? 'bg-green-100 text-green-800' :
  s === 'watch' ? 'bg-blue-100 text-blue-800' :
  'bg-neutral-100 text-neutral-700'

export default function Watchlist() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-black">Watchlist</h1>
      <div className="space-y-3">
        {watchlist.map((w) => (
          <article key={w.symbol} className="bg-white border border-neutral-200 rounded-md p-4">
            <header className="flex items-center gap-3 mb-2">
              <Link to={`/ticker/${w.symbol}`} className="font-mono font-bold text-lg text-blue-700 hover:underline">{w.symbol}</Link>
              <span className={`text-xs px-2 py-0.5 rounded ${statusCls(w.status)}`}>{w.status}</span>
              {w.updated_at && <span className="ml-auto text-xs text-neutral-500 font-mono">updated {w.updated_at}</span>}
            </header>
            {w.thesis && <p className="text-sm text-neutral-800 mb-2"><span className="font-bold">Thesis:</span> {w.thesis}</p>}
            {w.trigger && <p className="text-sm text-neutral-700"><span className="font-bold">Trigger:</span> {w.trigger}</p>}
            {w.invalidation && <p className="text-sm text-neutral-700"><span className="font-bold">Invalidation:</span> {w.invalidation}</p>}
            {w.invalidation_signals && w.invalidation_signals.length > 0 && (
              <div className="mt-2">
                <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Invalidation Signals</div>
                <ul className="list-disc pl-5 text-sm text-neutral-700">
                  {w.invalidation_signals.map((signal) => <li key={signal} className="font-mono">{signal}</li>)}
                </ul>
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}

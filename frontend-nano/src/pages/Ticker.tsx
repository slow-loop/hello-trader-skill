import { Link, useParams } from 'react-router-dom'
import { research, watchlist } from '../data'

export default function Ticker() {
  const { symbol = '' } = useParams()
  const wl = watchlist.find((w) => w.symbol === symbol)
  const docs = research.filter((r) => r.symbolOrTheme === symbol).sort((a, b) => b.date.localeCompare(a.date))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/watchlist" className="text-sm text-neutral-500 hover:underline">← Watchlist</Link>
        <h1 className="text-xl font-black font-mono">{symbol}</h1>
        {wl && <span className="text-xs px-2 py-0.5 rounded bg-neutral-900 text-white">{wl.status}</span>}
      </div>

      {wl && (
        <section className="bg-white border border-neutral-200 rounded-md p-4 space-y-2 text-sm">
          {wl.thesis && <p><span className="font-bold">Thesis：</span>{wl.thesis}</p>}
          {wl.notes && <p><span className="font-bold">Notes：</span>{wl.notes}</p>}
          {wl.trigger && <p><span className="font-bold">Trigger：</span>{wl.trigger}</p>}
          {wl.invalidation && <p><span className="font-bold">Invalidation：</span>{wl.invalidation}</p>}
          {wl.catalyst_notes && <p><span className="font-bold">Catalyst：</span>{wl.catalyst_notes}</p>}
        </section>
      )}

      <section>
        <h2 className="text-sm font-bold uppercase text-neutral-600 mb-2">研究檔案</h2>
        {docs.length === 0 && <p className="text-neutral-500 text-sm">尚無研究檔案。</p>}
        <ul className="space-y-1 text-sm">
          {docs.map((d) => (
            <li key={d.filename}>
              <Link to={`/research/${d.filename}`} className="font-mono text-blue-700 hover:underline">{d.date}</Link>
              <span className="text-neutral-500 ml-2">{d.filename}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

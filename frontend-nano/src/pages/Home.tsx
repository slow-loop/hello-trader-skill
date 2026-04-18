import { useState } from 'react'
import { Link } from 'react-router-dom'
import { allDates, journals, posts, research, researchCards, watchlist, type JournalEntry } from '../data'
import ResearchCard from '../components/ResearchCard'

function typeDot(t: string) {
  if (t === 'trade') return 'bg-green-600'
  if (t === 'study') return 'bg-blue-600'
  if (t === 'reflection') return 'bg-amber-500'
  return 'bg-neutral-400'
}

function List({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <ul className="list-disc pl-5 space-y-1 text-sm text-neutral-800">
      {items.map((x, i) => <li key={i}>{x}</li>)}
    </ul>
  )
}

function EntryBlock({ date, idx, e }: { date: string; idx: number; e: JournalEntry }) {
  const [open, setOpen] = useState(false)
  const summary = e.actions?.[0] ?? e.notes?.[0] ?? e.problems?.[0] ?? '—'
  return (
    <div className="bg-white border border-neutral-200 rounded-md overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2 flex items-center gap-3 text-sm text-left hover:bg-neutral-50"
      >
        <span className="font-mono text-neutral-500 w-12 shrink-0">{e.at}</span>
        <span className={`w-2 h-2 rounded-full ${typeDot(e.type)} shrink-0`} />
        <span className="font-bold w-20 shrink-0">{e.type}</span>
        <span className={`text-neutral-700 flex-1 ${open ? '' : 'truncate'}`}>{summary}</span>
        <span className="text-neutral-400 text-xs">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-neutral-200 space-y-3" id={`${date}-${idx}`}>
          {e.actions && e.actions.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Actions</div>
              <List items={e.actions} />
            </div>
          )}
          {e.notes && e.notes.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Notes</div>
              <List items={e.notes} />
            </div>
          )}
          {e.problems && e.problems.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Problems</div>
              <List items={e.problems} />
            </div>
          )}
          {e.changes && e.changes.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Changes</div>
              <List items={e.changes} />
            </div>
          )}
          {e.next && e.next.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase text-neutral-500 mb-1">Next</div>
              <List items={e.next} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Home() {
  return (
    <div className="space-y-8">
      <h1 className="text-xl font-black">時間軸</h1>
      {allDates.map((date) => {
        const entries = journals[date] ?? []
        const post = posts[date]
        const dayResearch = research.filter((r) => r.date === date)
        const researchCard = researchCards[date]
        return (
          <section key={date} className="space-y-2">
            <div className="sticky top-14 z-[5] bg-neutral-50/90 backdrop-blur py-1">
              <h2 className="font-mono font-black text-lg">{date}</h2>
            </div>

            {researchCard && <ResearchCard data={researchCard} />}

            {dayResearch.length > 0 && (
              <div className="bg-white border border-neutral-200 rounded-md px-4 py-3 text-sm">
                <div className="text-xs font-bold uppercase text-neutral-500 mb-1">個股研究</div>
                <ul className="space-y-1">
                  {dayResearch.map((r) => {
                    const wl = watchlist.find((w) => w.symbol === r.symbolOrTheme)
                    return (
                      <li key={r.filename}>
                        <Link to={`/research/${r.filename}`} className="font-mono text-blue-700 hover:underline">
                          {r.symbolOrTheme}
                        </Link>
                        {wl && <span className="ml-2 text-neutral-500">· {wl.status}</span>}
                        {wl?.thesis && <span className="ml-2 text-neutral-600">{wl.thesis}</span>}
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}

            {entries.map((e, i) => (
              <EntryBlock key={i} date={date} idx={i} e={e} />
            ))}

            {post && post.posts && post.posts.length > 0 && (
              <div className="bg-white border border-neutral-200 rounded-md px-4 py-3">
                <div className="text-xs font-bold uppercase text-neutral-500 mb-2">Post · {post.channel ?? ''}</div>
                {post.posts.map((p, i) => (
                  <pre key={i} className="whitespace-pre-wrap font-sans text-sm text-neutral-800 bg-neutral-50 p-3 rounded border border-neutral-200">
                    {p.text}
                  </pre>
                ))}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}

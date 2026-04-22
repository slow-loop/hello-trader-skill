import { useState } from 'react'
import { Link } from 'react-router-dom'
import { marked } from 'marked'
import { allDates, journals, posts, research, watchlist, type JournalEntry, type ResearchDoc } from '../data'

function typeDot(t: string) {
  if (t === 'trade') return 'bg-green-600'
  if (t === 'study') return 'bg-blue-600'
  if (t === 'reflection') return 'bg-amber-500'
  if (t === 'note') return 'bg-neutral-300'
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

function CollapsibleBlock({ at, dot, label, summary, children }: {
  at?: string
  dot?: string
  label: string
  summary: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bg-white border border-neutral-200 rounded-md overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2 flex items-center gap-3 text-sm text-left hover:bg-neutral-50"
      >
        <span className="font-mono text-neutral-500 w-12 shrink-0">{at ?? ''}</span>
        {dot && <span className={`w-2 h-2 rounded-full ${dot} shrink-0`} />}
        <span className="font-bold w-20 shrink-0">{label}</span>
        <span className={`text-neutral-700 flex-1 ${open ? '' : 'truncate'}`}>{summary}</span>
        <span className="text-neutral-400 text-xs">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="border-t border-neutral-200">
          {children}
        </div>
      )}
    </div>
  )
}

function ResearchBlock({ doc }: { doc: ResearchDoc }) {
  const wl = doc.kind === 'symbol' ? watchlist.find((w) => w.symbol === doc.symbolOrTheme) : undefined
  const label = doc.kind === 'brief' ? 'Brief' : doc.symbolOrTheme
  const at = doc.time ?? undefined
  const dot = doc.kind === 'brief' ? 'bg-purple-600' : 'bg-blue-400'
  const summary = doc.kind === 'brief'
    ? [doc.session, doc.screenerSource].filter(Boolean).join(' · ')
    : [wl?.status, wl?.thesis].filter(Boolean).join(' · ') || doc.filename
  const html = marked.parse(doc.body) as string
  return (
    <CollapsibleBlock at={at} dot={dot} label={label} summary={summary}>
      <div className="px-4 py-3 space-y-3">
        <div className="flex items-center gap-3 text-xs text-neutral-500">
          <Link to={`/research/${doc.filename}`} className="text-blue-700 hover:underline font-mono">
            {doc.filename}
          </Link>
          {doc.kind === 'symbol' && (
            <Link to={`/ticker/${doc.symbolOrTheme}`} className="text-blue-700 hover:underline">
              查看 {doc.symbolOrTheme}
            </Link>
          )}
        </div>
        <article
          className="prose prose-sm max-w-none prose-headings:font-black prose-h2:text-sm prose-h2:mt-4 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-1 prose-table:text-xs"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    </CollapsibleBlock>
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
        const dayResearch = research
          .filter((r) => r.date === date)
          .sort((a, b) => {
            if (a.kind !== b.kind) return a.kind === 'brief' ? -1 : 1
            return (a.time ?? a.symbolOrTheme).localeCompare(b.time ?? b.symbolOrTheme)
          })
        return (
          <section key={date} className="space-y-2">
            <div className="sticky top-14 z-[5] bg-neutral-50/90 backdrop-blur py-1">
              <h2 className="font-mono font-black text-lg">{date}</h2>
            </div>

            {dayResearch.map((doc) => (
              <ResearchBlock key={doc.filename} doc={doc} />
            ))}

            {entries.map((e, i) => (
              <EntryBlock key={i} date={date} idx={i} e={e} />
            ))}

            {post && post.posts && post.posts.length > 0 && (
              <CollapsibleBlock
                dot="bg-neutral-400"
                label="post"
                summary={post.channel ?? ''}
              >
                <div className="px-4 py-3 space-y-2">
                  {post.posts.map((p, i) => (
                    <pre key={i} className="whitespace-pre-wrap font-sans text-sm text-neutral-800 bg-neutral-50 p-3 rounded border border-neutral-200">
                      {p.text}
                    </pre>
                  ))}
                </div>
              </CollapsibleBlock>
            )}
          </section>
        )
      })}
    </div>
  )
}

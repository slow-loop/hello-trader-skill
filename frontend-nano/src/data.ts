import yaml from 'js-yaml'

const journalRaw = import.meta.glob('/../data/account/journals/*.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const postsRaw = import.meta.glob('/../data/posts/*.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const researchRaw = import.meta.glob('/../data/account/research/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const watchlistRaw = import.meta.glob('/../data/account/watchlist.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const strategyRaw = import.meta.glob('/../data/account/strategy.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const tradesRaw = import.meta.glob('/../data/account/state/trades.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

export type JournalEntry = {
  at: string
  type: 'reflection' | 'study' | 'trade' | string
  actions?: string[]
  notes?: string[]
  problems?: string[]
  changes?: string[]
  next?: string[]
}

export type PostsFile = {
  date: string
  timezone?: string
  channel?: string
  posts: { text: string }[]
}

export type WatchlistItem = {
  symbol: string
  status: 'watch' | 'hold' | string
  thesis?: string
  notes?: string
  trigger?: string
  invalidation?: string
  invalidation_signals?: string[]
  catalyst_notes?: string
  updated_at?: string
}

export type ResearchDoc = {
  filename: string
  date: string
  kind: 'brief' | 'symbol'
  symbolOrTheme: string  // for brief: "HHMM" string; else symbol/theme
  time: string | null    // "HH:MM" for brief, null for symbol research
  session: string | null
  screenerSource: string | null
  body: string
}

function dateFromFilename(path: string): string {
  const m = path.match(/(\d{4}-\d{2}-\d{2})/)
  return m ? m[1] : ''
}

function basename(path: string): string {
  return path.split('/').pop() ?? path
}

export const journals: Record<string, JournalEntry[]> = Object.fromEntries(
  Object.entries(journalRaw).map(([p, raw]) => {
    const date = dateFromFilename(p)
    const parsed = (yaml.load(raw) as JournalEntry[]) ?? []
    return [date, parsed]
  }),
)

export const posts: Record<string, PostsFile> = Object.fromEntries(
  Object.entries(postsRaw).map(([p, raw]) => {
    const date = dateFromFilename(p)
    const parsed = yaml.load(raw) as PostsFile
    return [date, parsed]
  }),
)

const FRONTMATTER_RE = /^---\n([\s\S]*?)\n---\n?/

function parseFrontmatter(raw: string): { data: Record<string, unknown>; body: string } {
  const m = raw.match(FRONTMATTER_RE)
  if (!m) return { data: {}, body: raw }
  try {
    const data = (yaml.load(m[1]) as Record<string, unknown>) ?? {}
    return { data, body: raw.slice(m[0].length) }
  } catch {
    return { data: {}, body: raw }
  }
}

function timeFromCreatedAt(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const m = value.match(/T(\d{2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : null
}

export const research: ResearchDoc[] = Object.entries(researchRaw)
  .filter(([p]) => !p.includes('/template/'))
  .map(([p, raw]) => {
    const name = basename(p).replace(/\.md$/, '')
    const date = dateFromFilename(name)
    const rest = name.replace(`${date}-tw-`, '')
    const briefMatch = rest.match(/^brief-(\d{2})(\d{2})$/)
    const { data: fm, body } = parseFrontmatter(raw)
    const createdAtTime = timeFromCreatedAt(fm.created_at)
    if (briefMatch) {
      return {
        filename: name,
        date,
        kind: 'brief' as const,
        symbolOrTheme: `${briefMatch[1]}${briefMatch[2]}`,
        time: createdAtTime ?? `${briefMatch[1]}:${briefMatch[2]}`,
        session: (fm.session as string | undefined) ?? null,
        screenerSource: (fm.screener_source as string | undefined) ?? null,
        body,
      }
    }
    return {
      filename: name,
      date,
      kind: 'symbol' as const,
      symbolOrTheme: rest,
      time: createdAtTime,
      session: null,
      screenerSource: null,
      body,
    }
  })

export const watchlist: WatchlistItem[] = (() => {
  const first = Object.values(watchlistRaw)[0]
  if (!first) return []
  return (yaml.load(first) as WatchlistItem[]) ?? []
})()

export const strategy: string = Object.values(strategyRaw)[0] ?? ''

export type Trade = {
  action: 'BUY' | 'SELL' | string
  symbol: string
  quantity: number
  price: number
  executed_at: string
  fee: number
  reason?: string
  strategy?: string
  tags?: string[]
  pnl?: number | null
}

export const trades: Trade[] = (() => {
  const first = Object.values(tradesRaw)[0]
  if (!first) return []
  return (yaml.load(first) as Trade[]) ?? []
})()

export const allDates: string[] = Array.from(
  new Set([
    ...Object.keys(journals),
    ...Object.keys(posts),
    ...research.map((r) => r.date),
  ]),
)
  .filter(Boolean)
  .sort()
  .reverse()

export function tradesFromJournals(): Array<{ date: string; at: string; actions: string[]; notes: string[] }> {
  const rows: Array<{ date: string; at: string; actions: string[]; notes: string[] }> = []
  for (const [date, entries] of Object.entries(journals)) {
    for (const e of entries) {
      if (e.type === 'trade') {
        rows.push({ date, at: e.at, actions: e.actions ?? [], notes: e.notes ?? [] })
      }
    }
  }
  return rows.sort((a, b) => (b.date + b.at).localeCompare(a.date + a.at))
}

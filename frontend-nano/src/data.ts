import yaml from 'js-yaml'

const journalRaw = import.meta.glob('/../skills/tw-trader/data/account/journals/*.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const postsRaw = import.meta.glob('/../skills/tw-trader/data/posts/*.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const researchRaw = import.meta.glob('/../skills/tw-trader/data/account/research/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const watchlistRaw = import.meta.glob('/../skills/tw-trader/data/account/watchlist.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const lessonsRaw = import.meta.glob('/../skills/tw-trader/data/account/lessons.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const briefsRaw = import.meta.glob('/../skills/tw-trader/data/account/briefs/*.yaml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const tradesRaw = import.meta.glob('/../skills/tw-trader/data/account/state/trades.yaml', {
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
  trigger_conditions?: string[]
  invalidation_conditions?: string[]
  catalyst_notes?: string
  updated_at?: string
}

export type ResearchDoc = {
  filename: string
  date: string
  symbolOrTheme: string
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

export const research: ResearchDoc[] = Object.entries(researchRaw).map(([p, raw]) => {
  const name = basename(p).replace(/\.md$/, '')
  const date = dateFromFilename(name)
  const symbolOrTheme = name.replace(`${date}-tw-`, '')
  return { filename: name, date, symbolOrTheme, body: raw }
})

export const watchlist: WatchlistItem[] = (() => {
  const first = Object.values(watchlistRaw)[0]
  if (!first) return []
  return (yaml.load(first) as WatchlistItem[]) ?? []
})()

export const lessons: string = Object.values(lessonsRaw)[0] ?? ''

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

export type ResearchCardData = {
  date: string
  session?: string
  screener?: {
    skipped?: boolean
    skip_reason?: string | null
    source?: string                     // pointer to raw CLI output
    highlights?: Array<{
      symbol: string; name?: string; reason: string; is_new?: boolean
    }>
  }
  sentiment?: {
    overall?: string
    hot_tickers?: Array<{ symbol: string; theme?: string; note?: string }>
    narratives?: string[]
    conclusion?: string
  }
  macro?: {
    market_line?: string
    main_points?: string[]
    secondary_themes?: string[]
    fund_flows?: { foreign?: string; investment_trust?: string; dealer?: string }
  }
  cross_ref?: {
    rows?: Array<{
      symbol: string; name?: string;
      screener?: string; sentiment?: string; news?: string;
      verdict?: string; tier?: string;
    }>
    tomorrow_watch?: Array<{ symbol: string; tag?: string | null; reason?: string }>
  }
  watchlist_changes?: {
    added?: Array<{ symbol: string; status?: string }>
    promoted?: Array<{ symbol: string; from?: string; to?: string }>
    removed?: Array<{ symbol: string; reason?: string }>
    updated?: Array<{ symbol: string; what_changed?: string }>
  }
  deep_research_candidates?: Array<{ symbol: string }>
}

export type BriefEntry = {
  time: string | null  // "15:14" if filename has HHMM suffix, null otherwise
  data: ResearchCardData
}

function timeFromBriefFilename(path: string): string | null {
  const m = basename(path).match(/\d{4}-\d{2}-\d{2}-(\d{2})(\d{2})\.yaml$/)
  return m ? `${m[1]}:${m[2]}` : null
}

export const briefs: Record<string, BriefEntry[]> = (() => {
  const map: Record<string, BriefEntry[]> = {}
  Object.entries(briefsRaw)
    .filter(([p]) => !p.includes('/template/'))
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([p, raw]) => {
      const date = dateFromFilename(p)
      if (!date) return
      const parsed = yaml.load(raw) as ResearchCardData
      const time = timeFromBriefFilename(p)
      ;(map[date] ??= []).push({ time, data: parsed })
    })
  return map
})()

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
    ...Object.keys(briefs),
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

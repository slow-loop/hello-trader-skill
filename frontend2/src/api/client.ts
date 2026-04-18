import type {
  AnalysisReport,
  EquityPoint,
  EvaluatedWatchlistConfig,
  JournalDocument,
  JournalSummary,
  LessonsDocument,
  OrderRequest,
  Quote,
  ScreenerResponse,
  TradeRecord,
  WorkspaceConfig,
  WorkspaceStatus,
  ChartData,
} from './types.ts'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  workspace: () => get<WorkspaceConfig>('/workspace'),
  account: () => get<WorkspaceStatus>('/account'),
  trades: (limit = 50) => get<TradeRecord[]>(`/trades?limit=${limit}`),
  equityHistory: (days = 90) => get<EquityPoint[]>(`/equity-history?days=${days}`),

  watchlist: (evaluate = true) =>
    get<EvaluatedWatchlistConfig>(`/workspace/watchlist?evaluate=${evaluate}`),

  quote: (symbol: string) => get<Quote>(`/quote/${encodeURIComponent(symbol)}`),
  analysis: (symbol: string) => get<AnalysisReport>(`/analysis/${encodeURIComponent(symbol)}`),
  chart: (symbol: string) => get<ChartData>(`/chart/${encodeURIComponent(symbol)}`),
  screener: (strategy = 'momentum', limit = 30) =>
    get<ScreenerResponse>(`/screener?strategy=${strategy}&limit=${limit}`),

  journals: (limit = 10) => get<JournalSummary[]>(`/workspace/journals?limit=${limit}`),
  journal: (date: string) => get<JournalDocument>(`/workspace/journals/${date}`),

  lessons: () => get<LessonsDocument>('/workspace/lessons'),
  saveLessons: (content: string) => put<LessonsDocument>('/workspace/lessons', { content }),

  placeOrder: (req: OrderRequest) => post<{ message: string }>('/orders', req),
  heartbeat: () => post<unknown>('/heartbeat', {}),
}

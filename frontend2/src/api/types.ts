export interface Quote {
  symbol: string
  price: number
  change: number
  change_pct: number
  volume?: number
  timestamp?: string
}

export interface WatchlistItem {
  symbol: string
  thesis?: string
  status?: 'watch' | 'hold' | 'archived'
  notes?: string
  trigger?: string
  invalidation?: string
  trigger_price?: number
  invalidation_price?: number
  updated_at?: string
}

export interface WatchlistEvaluation {
  trigger_met: boolean
  invalidation_met: boolean
  error?: string
}

export interface AnalysisReport {
  symbol: string
  name?: string
  bars?: Bar[]
  indicators?: Record<string, number[]>
  summary?: string
  generated_at?: string
}

export interface Bar {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface EvaluatedWatchlistItem extends WatchlistItem {
  analysis?: AnalysisReport
  evaluation?: WatchlistEvaluation
}

export interface EvaluatedWatchlistConfig {
  items: EvaluatedWatchlistItem[]
}

export interface PositionStatus {
  symbol: string
  quantity: number
  avg_price: number
  cost: number
  reason?: string
  current_price?: number
  market_value?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  allocation_pct?: number
}

export interface OrderStatus {
  symbol: string
  stop_loss?: number
  take_profit?: number
  dist_to_stop_pct?: number
  dist_to_take_pct?: number
}

export interface TradeRecord {
  action: 'BUY' | 'SELL'
  symbol: string
  quantity: number
  price: number
  executed_at: string
  fee?: number
  reason?: string
  strategy?: string
  pnl?: number
}

export interface WorkspaceStatus {
  workspace_id: string
  name: string
  market_profile: string
  cash: number
  realized_pnl: number
  account_value: number
  market_value: number
  exposure_pct: number
  positions: PositionStatus[]
  orders: OrderStatus[]
  today_trades: TradeRecord[]
}

export interface WorkspaceConfig {
  id: string
  name: string
  market: { profile: string; currency?: string }
}

export interface EquityPoint {
  date: string
  account_value: number
  cash: number
  market_value: number
}

export interface JournalEntry {
  at?: string
  type?: string
  actions?: string[]
  notes?: string[]
}

export interface JournalDocument {
  date: string
  entries: JournalEntry[]
}

export interface JournalSummary {
  date: string
  entry_count: number
}

export interface LessonsDocument {
  content: string
}

export interface ScreenerResult {
  symbol: string
  name: string
  close: number
  change: number
  change_pct: number
  trade_value: number
  analysis?: AnalysisReport
}

export interface ScreenerResponse {
  strategy: string
  market_profile: string
  generated_at: string
  items: ScreenerResult[]
}

export interface OrderRequest {
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price?: number
  stop_loss?: number
  take_profit?: number
  reason?: string
  strategy?: string
}

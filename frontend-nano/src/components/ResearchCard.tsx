import type { ResearchCardData } from '../data'

function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-sm font-black mb-2">
        <span className="font-mono mr-2 text-neutral-500">{n}</span>
        {title}
      </h3>
      <div className="border border-neutral-900">{children}</div>
    </section>
  )
}

const tierCls = (t?: string) =>
  t === 'triple_resonance' ? 'bg-yellow-50 font-bold' :
  t === 'double_confirm' ? 'bg-blue-50' :
  ''

const tierLabel = (t?: string) =>
  t === 'triple_resonance' ? '三方共振' :
  t === 'double_confirm' ? '雙重確認' :
  t === 'story_only' ? '有故事' :
  t === 'screener_only' ? '僅動能' :
  t === 'skip' ? '跳過' : t

export default function ResearchCard({ data }: { data: ResearchCardData }) {
  return (
    <div className="bg-white font-sans text-neutral-900 border border-neutral-300 rounded-md overflow-hidden">
      <div className="bg-neutral-900 text-white px-6 py-3 flex justify-between items-center">
        <span className="text-sm font-bold tracking-wider uppercase">AI 盤後研究</span>
        <span className="text-sm text-neutral-300 font-mono">
          {data.date}{data.session && ` · ${data.session}`}
        </span>
      </div>

      <div className="px-6 py-5 flex flex-col gap-5">

        {/* Phase 1: Screener — highlights only */}
        <Section n="01" title="Screener 亮點">
          {data.screener?.skipped ? (
            <div className="px-4 py-3 text-sm text-neutral-600">
              跳過 · {data.screener.skip_reason ?? '非盤後時段'}
            </div>
          ) : (
            <>
              <div className="px-4 py-3 text-[13px] space-y-2">
                {(data.screener?.highlights ?? []).map((h, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="font-mono font-bold shrink-0">{h.symbol}</span>
                    {h.name && <span className="font-bold shrink-0">{h.name}</span>}
                    {h.is_new && <span className="bg-yellow-400 text-neutral-900 px-1.5 text-[11px] font-black shrink-0 self-center">新面孔</span>}
                    <span className="text-neutral-700">— {h.reason}</span>
                  </div>
                ))}
              </div>
              {data.screener?.source && (
                <div className="border-t border-neutral-200 px-4 py-1.5 text-[11px] text-neutral-500 font-mono">
                  raw: {data.screener.source}
                </div>
              )}
            </>
          )}
        </Section>

        {/* Phase 2: Sentiment */}
        {data.sentiment && (
          <Section n="02" title="散戶情緒">
            <div className="px-4 py-3 text-[13px] space-y-2">
              {data.sentiment.overall && <p><span className="font-bold">整體：</span>{data.sentiment.overall}</p>}
              {(data.sentiment.hot_tickers?.length ?? 0) > 0 && (
                <div>
                  <span className="font-bold">熱門 ticker：</span>
                  {data.sentiment.hot_tickers!.map((t, i) => (
                    <span key={i} className="ml-2 inline-block">
                      <span className="font-mono">{t.symbol}</span>
                      {t.theme && <span className="text-neutral-500"> ({t.theme})</span>}
                      {t.note && <span className="text-neutral-600"> — {t.note}</span>}
                    </span>
                  ))}
                </div>
              )}
              {(data.sentiment.narratives?.length ?? 0) > 0 && (
                <ul className="list-disc pl-5">
                  {data.sentiment.narratives!.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              )}
              {data.sentiment.conclusion && (
                <p className="border-t border-neutral-200 pt-2"><span className="font-bold">結論：</span>{data.sentiment.conclusion}</p>
              )}
            </div>
          </Section>
        )}

        {/* Phase 3: Macro */}
        {data.macro && (
          <Section n="03" title="宏觀 / 新聞">
            <div className="px-4 py-3 text-[13px]">
              {data.macro.market_line && <p className="font-bold mb-1">{data.macro.market_line}</p>}
              {(data.macro.main_points?.length ?? 0) > 0 && (
                <ul className="list-disc pl-5 space-y-0.5">
                  {data.macro.main_points!.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              )}
              {(data.macro.secondary_themes?.length ?? 0) > 0 && (
                <p className="mt-2 pt-2 border-t border-neutral-200">
                  <span className="font-bold">次主線：</span>{data.macro.secondary_themes!.join('、')}
                </p>
              )}
              {data.macro.fund_flows && (
                <div className="mt-2 pt-2 border-t border-neutral-200 flex gap-4 text-xs">
                  {data.macro.fund_flows.foreign && <span>外資 <span className="font-bold">{data.macro.fund_flows.foreign}</span></span>}
                  {data.macro.fund_flows.investment_trust && <span>投信 <span className="font-bold">{data.macro.fund_flows.investment_trust}</span></span>}
                  {data.macro.fund_flows.dealer && <span>自營 <span className="font-bold">{data.macro.fund_flows.dealer}</span></span>}
                </div>
              )}
            </div>
          </Section>
        )}

        {/* Phase 4: Cross-ref — no stars, tier drives visual */}
        {data.cross_ref && (
          <Section n="04" title="交叉比對">
            <table className="w-full text-left text-[13px]">
              <thead className="bg-neutral-900 text-white">
                <tr>
                  <th className="px-3 py-1.5 font-bold">標的</th>
                  <th className="px-3 py-1.5 font-bold">Screener</th>
                  <th className="px-3 py-1.5 font-bold">Sentiment</th>
                  <th className="px-3 py-1.5 font-bold">News</th>
                  <th className="px-3 py-1.5 font-bold">判斷</th>
                  <th className="px-3 py-1.5 font-bold">Tier</th>
                </tr>
              </thead>
              <tbody>
                {(data.cross_ref.rows ?? []).map((r, i) => (
                  <tr key={i} className={`border-t border-neutral-200 ${tierCls(r.tier)}`}>
                    <td className="px-3 py-1.5 font-bold whitespace-nowrap">
                      <span className="font-mono">{r.symbol}</span>{r.name && ` ${r.name}`}
                    </td>
                    <td className="px-3 py-1.5 text-neutral-600">{r.screener ?? <span className="text-neutral-300">—</span>}</td>
                    <td className="px-3 py-1.5 text-neutral-600">{r.sentiment ?? <span className="text-neutral-300">—</span>}</td>
                    <td className="px-3 py-1.5 text-neutral-600">{r.news ?? <span className="text-neutral-300">—</span>}</td>
                    <td className="px-3 py-1.5">{r.verdict}</td>
                    <td className="px-3 py-1.5 text-[11px] text-neutral-500">{tierLabel(r.tier)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(data.cross_ref.tomorrow_watch?.length ?? 0) > 0 && (
              <div className="border-t border-neutral-900 bg-neutral-900 text-white px-4 py-3 text-[13px]">
                <p className="font-bold mb-1.5">明日關注</p>
                <div className="space-y-1">
                  {data.cross_ref.tomorrow_watch!.map((t, i) => (
                    <p key={i}>
                      {t.tag && <span className="bg-yellow-400 text-neutral-900 px-1.5 font-black text-xs mr-1">{t.tag}</span>}
                      <span className="font-mono font-bold">{t.symbol}</span>
                      {(t as any).name && <span className="font-bold"> {(t as any).name}</span>}
                      {t.reason && <span> — {t.reason}</span>}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </Section>
        )}

        {/* Watchlist changes */}
        {data.watchlist_changes && (
          ((data.watchlist_changes.added?.length ?? 0) +
            (data.watchlist_changes.promoted?.length ?? 0) +
            (data.watchlist_changes.removed?.length ?? 0) +
            (data.watchlist_changes.updated?.length ?? 0)) > 0
        ) && (
          <Section n="05" title="Watchlist 調整">
            <div className="px-4 py-3 text-[13px] space-y-1">
              {data.watchlist_changes!.added?.map((x, i) => <p key={`a${i}`}><span className="font-bold text-green-700">+ 新增</span> {x.symbol} ({x.status})</p>)}
              {data.watchlist_changes!.promoted?.map((x, i) => <p key={`p${i}`}><span className="font-bold text-blue-700">↑ 升級</span> {x.symbol} {x.from} → {x.to}</p>)}
              {data.watchlist_changes!.removed?.map((x, i) => <p key={`r${i}`}><span className="font-bold text-red-700">− 移除</span> {x.symbol} {x.reason && `— ${x.reason}`}</p>)}
              {data.watchlist_changes!.updated?.map((x, i) => <p key={`u${i}`}><span className="font-bold text-neutral-700">~ 更新</span> {x.symbol} {x.what_changed && `— ${x.what_changed}`}</p>)}
            </div>
          </Section>
        )}

      </div>
    </div>
  )
}

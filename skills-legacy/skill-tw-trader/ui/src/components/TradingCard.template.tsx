/* ─────────────────── TradingCard.template.tsx ────────────────────────────── */
/* DO NOT EDIT — reference template for agent code generation.                */
/* Agent workflow:                                                             */
/*   1. Read today's journal (data/account/journals/YYYY-MM-DD.yaml)          */
/*   2. Read watchlist (data/account/watchlist.yaml)                           */
/*   3. Copy this file to TradingCard.tsx                                     */
/*   4. Replace all hardcoded data (date, market summary, watchlist eval,     */
/*      decisions, observations) with today's data                            */
/*   5. Run: npm run screenshot -- <output_path>                              */
/* ────────────────────────────────────────────────────────────────────────── */

export default function TradingCard() {
  return (
    <div className="card-root w-[1080px] bg-white font-sans text-neutral-900 flex flex-col relative">
      {/* Top Bar */}
      <div className="bg-neutral-900 text-white px-10 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          {/* TODO: avatar logo — 待換成高品質彩色去背角色圖後再啟用
          <img src="/avatar.png" className="h-8 w-8 object-cover object-top rounded-sm" style={{ filter: 'brightness(0) invert(1)' }} />
          */}
          <span className="text-base font-bold tracking-wider uppercase">AI 交易決策</span>
        </div>
        <span className="text-base text-neutral-300">2026-04-16 · Run #3</span>
      </div>

      <div className="px-10 py-5 flex-1 flex flex-col gap-4">

        {/* Section 1: Market Context */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">01</span>
            大盤環境
          </h2>
          <div className="border border-neutral-900 px-4 py-3 text-[13px] space-y-1.5">
            <div className="flex gap-6">
              <div>
                <span className="text-neutral-500 text-xs block">台股</span>
                <span className="font-bold text-lg text-green-700">37,132</span>
                <span className="text-green-700 ml-1">+1.31%</span>
              </div>
              <div>
                <span className="text-neutral-500 text-xs block">成交量</span>
                <span className="font-bold">9,820 億</span>
              </div>
              <div>
                <span className="text-neutral-500 text-xs block">外資</span>
                <span className="font-bold text-green-700">+440 億</span>
              </div>
              <div>
                <span className="text-neutral-500 text-xs block">投信</span>
                <span className="font-bold text-red-600">-43 億</span>
              </div>
              <div>
                <span className="text-neutral-500 text-xs block">自營</span>
                <span className="font-bold text-green-700">+118 億</span>
              </div>
            </div>
            <div className="border-t border-neutral-200 pt-1.5 mt-1">
              <p><span className="font-bold">判斷：</span>收盤創歷史新高，但台指期夜盤閃崩 600 點（台積電法說 sell the news + ADR 遭獵殺），明日開低壓力大。</p>
            </div>
          </div>
        </section>

        {/* Section 2: Watchlist Evaluation */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">02</span>
            Watchlist 評估
          </h2>
          <div className="border border-neutral-900">
            <table className="w-full text-left text-[13px]">
              <thead className="bg-neutral-900 text-white">
                <tr>
                  <th className="px-3 py-1.5 font-bold">標的</th>
                  <th className="px-3 py-1.5 font-bold">收盤</th>
                  <th className="px-3 py-1.5 font-bold">漲跌%</th>
                  <th className="px-3 py-1.5 font-bold">Trigger</th>
                  <th className="px-3 py-1.5 font-bold">條件明細</th>
                  <th className="px-3 py-1.5 font-bold">風險訊號</th>
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    name: '2330 台積電',
                    close: '2,085',
                    chg: '+0.48%',
                    trigger: false,
                    conditions: [
                      { label: 'SMA20', met: true },
                      { label: 'MACD', met: true },
                      { label: 'Vol 1.5x', met: false },
                    ],
                    risk: '量比 1.22x 未達、相對弱勢、夜盤閃崩',
                  },
                  {
                    name: '3189 景碩',
                    close: '383.5',
                    chg: '+3.37%',
                    trigger: true,
                    conditions: [
                      { label: 'SMA20', met: true },
                      { label: 'MACD', met: true },
                      { label: 'Vol 1.5x', met: true },
                      { label: 'ADX>25', met: true },
                    ],
                    risk: 'ATR 7.2% 高波動、夜盤閃崩待消化',
                  },
                  {
                    name: '3711 日月光',
                    close: '446.5',
                    chg: '+5.31%',
                    trigger: true,
                    conditions: [
                      { label: 'SMA20', met: true },
                      { label: 'MACD', met: true },
                      { label: 'Vol 1.5x', met: true },
                    ],
                    risk: 'RSI 73 超買、Stoch K 89、已追高',
                  },
                ].map((row, i) => (
                  <tr key={i} className={`border-t border-neutral-200 ${row.trigger ? 'bg-yellow-50' : ''}`}>
                    <td className="px-3 py-1.5 font-bold">{row.name}</td>
                    <td className="px-3 py-1.5">{row.close}</td>
                    <td className="px-3 py-1.5 text-green-700">{row.chg}</td>
                    <td className="px-3 py-1.5">
                      <span className={`text-xs font-mono ${row.trigger ? 'text-neutral-900' : 'text-neutral-400'}`}>
                        {row.trigger ? '✓ MET' : 'not met'}
                      </span>
                    </td>
                    <td className="px-3 py-1.5">
                      <div className="flex gap-1 flex-wrap">
                        {row.conditions.map((c, j) => (
                          <span key={j} className={`inline-block px-1.5 py-0.5 text-[11px] rounded ${c.met ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {c.met ? '✓' : '✗'} {c.label}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-1.5 text-neutral-600 text-xs">{row.risk}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Section 3: Trading Decisions */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">03</span>
            交易決策
          </h2>
          <div className="space-y-2">
            {[
              {
                name: '2330 台積電',
                action: 'SKIP',
                actionStyle: 'bg-neutral-200 text-neutral-700' as const,
                reason: 'Trigger 未全達（量比 1.22x < 1.5x），法說日相對弱勢（+0.48% vs 大盤 +1.31%），夜盤閃崩 600 點風險在前。',
                next: '等待法說消化完成、量能回升至 1.5x。',
              },
              {
                name: '3189 景碩',
                action: 'SKIP',
                actionStyle: 'bg-neutral-200 text-neutral-700' as const,
                reason: 'Trigger 技術達標（ADX=30, Vol=1.86x），但 ATR 7.2% 高波動 + 夜盤閃崩後明日開低壓力大，不宜追高。',
                next: '明日若量縮守穩 370-385 區間，逢低再評估進場。',
              },
              {
                name: '3711 日月光',
                action: 'SKIP',
                actionStyle: 'bg-neutral-200 text-neutral-700' as const,
                reason: '今日已 +5.31%，RSI 73、Stoch K 89 全面超買。Watchlist 設計進場為回測 SMA20 後 RSI 65-70，今日不符。',
                next: '等待回測 SMA20 量縮守穩，RSI 回到 65-70 再進場。',
              },
              // BUY example (uncomment and fill when applicable):
              // { name: '3189 景碩', action: 'BUY', actionStyle: 'bg-neutral-900 text-white', reason: '...', next: '...' },
            ].map((d, i) => (
              <div key={i} className="border border-neutral-900 px-4 py-3 text-[13px]">
                <div className="flex items-center gap-3 mb-1.5">
                  <span className="font-bold text-sm">{d.name}</span>
                  <span className={`px-2 py-0.5 text-xs font-black ${d.actionStyle}`}>
                    {d.action}
                  </span>
                </div>
                <p><span className="font-bold">原因：</span>{d.reason}</p>
                <p className="text-neutral-500 mt-0.5"><span className="font-bold text-neutral-700">下一步：</span>{d.next}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Section 4: Key Observations */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">04</span>
            關鍵觀察
          </h2>
          <div className="border border-neutral-900 px-4 py-3 text-[13px] space-y-1.5">
            <div className="flex gap-2 items-start">
              <span className="bg-neutral-900 text-white px-1.5 py-0.5 text-[11px] font-bold shrink-0 mt-0.5">ALERT</span>
              <p>台指期夜盤閃崩 600 點 — 台積電法說 sell the news，ADR 遭獵殺。明日開低壓力大，全部標的暫緩進場。</p>
            </div>
            <div className="flex gap-2 items-start">
              <span className="bg-yellow-400 text-neutral-900 px-1.5 py-0.5 text-[11px] font-bold shrink-0 mt-0.5">NOTE</span>
              <p>2330 法說日大盤 +1.31% 但個股僅 +0.48% — 最強 catalyst 日量能未放大，利多已提前 price in。</p>
            </div>
            <div className="flex gap-2 items-start">
              <span className="bg-yellow-400 text-neutral-900 px-1.5 py-0.5 text-[11px] font-bold shrink-0 mt-0.5">NOTE</span>
              <p>3189 watchlist bug 已修正 — adx_14_above_25 expression 名稱改為數值條件 adx_14 &gt; 25，trigger 正確評估為 MET。</p>
            </div>
          </div>
        </section>

      </div>

      {/* Footer */}
      <div className="px-10 py-2 border-t border-neutral-300 flex justify-end items-center text-xs text-neutral-900">
        <span>本內容由 AI 自動生成，僅供參考，不代表任何投資建議或操作指示</span>
      </div>
    </div>
  );
}

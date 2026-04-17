/* ─────────────────── ResearchCard — 4 Phases (Complete) ─────────────────── */
/* Agent: replace the hardcoded data inside this component each day.          */

export default function ResearchCard() {
  return (
    <div className="card-root w-[1080px] bg-white font-sans text-neutral-900 flex flex-col">
      {/* Top Bar */}
      <div className="bg-neutral-900 text-white px-10 py-3 flex justify-between items-center">
        <span className="text-base font-bold tracking-wider uppercase">AI 盤後研究</span>
        <span className="text-base text-neutral-300">2026-04-16</span>
      </div>

      <div className="px-10 py-5 flex-1 flex flex-col gap-4">

        {/* Phase 1: Screener */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">01</span>
            Screener
          </h2>
          <div className="border border-neutral-900">
            <table className="w-full text-left text-[13px]">
              <thead className="bg-neutral-900 text-white">
                <tr>
                  <th className="px-3 py-1.5 font-bold">股票</th>
                  <th className="px-3 py-1.5 font-bold">收盤</th>
                  <th className="px-3 py-1.5 font-bold">漲跌%</th>
                  <th className="px-3 py-1.5 font-bold">量比</th>
                  <th className="px-3 py-1.5 font-bold">RSI</th>
                  <th className="px-3 py-1.5 font-bold">ADX</th>
                  <th className="px-3 py-1.5 font-bold">MACD</th>
                  <th className="px-3 py-1.5 font-bold">備注</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['2330 台積電', '2080', '+1.22%', '1.22x', '68.8', '20.1', '+', 'Watchlist，量未到'],
                  ['2454 聯發科', '1790', '+4.07%', '2.48x', '65.0', '21.2', '負/擴', '止穩反彈訊號'],
                  ['2327 國巨', '322', '+3.21%', '2.28x', '70.2', '17.9', '+', '法說後強勢'],
                  ['2308 台達電', '1785', '+2.0%', '0.84x', '70.3', '29.8', '+', '趨勢強量縮'],
                  ['1802 台玻', '69.2', '+1.47%', '2.77x', '66.8', '20.5', '+', '外資輪動傳產'],
                  ['2313 華通', '263', '+2.14%', '0.59x', '57.4', '41.0', '+', '整理中，趨勢超強'],
                  ['3189 景碩', '383.5', '+3.37%', '1.86x', '61.2', '30.2', '+', '新面孔★，距支撐-6%'],
                  ['2383 台光電', '3810', '+5.69%', '1.13x', '75.3', '44.1', '+', '新面孔★★，超強但超買'],
                  ['2345 智邦', '1970', '+4.23%', '1.46x', '70.8', '29.8', '+', 'AI交換器'],
                  ['2409 友達', '20.05', '+1.26%', '2.50x', '70.4', '31.2', '+', '面板輪動'],
                  ['3711 日月光', '446.5', '+5.31%', '1.57x', '73.4', '21.5', '+', '新面孔★，封測'],
                  ['3481 群創', '27.6', '+1.28%', '1.36x', '57.3', '18.6', '+', '面板，趨勢弱'],
                  ['6213 聯茂', '229.5', '+2.46%', '1.90x', '76.0', '44.7', '+', '新面孔★★，ADX最強'],
                ].map(([name, close, chg, vol, rsi, adx, macd, note], i) => {
                  const isNew = (note as string).includes('新面孔');
                  return (
                    <tr key={i} className={`border-t border-neutral-200 ${isNew ? 'bg-yellow-50' : ''}`}>
                      <td className="px-3 py-1.5 font-bold">{name}</td>
                      <td className="px-3 py-1.5">{close}</td>
                      <td className="px-3 py-1.5 text-green-700">{chg}</td>
                      <td className="px-3 py-1.5">{vol}</td>
                      <td className="px-3 py-1.5">{rsi}</td>
                      <td className="px-3 py-1.5">{adx}</td>
                      <td className="px-3 py-1.5">{macd}</td>
                      <td className="px-3 py-1.5">{note}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="border border-neutral-900 border-t-0 px-4 py-3 text-[13px] space-y-1">
            <p className="font-bold">新面孔最值得關注（ADX ≥ 20 + 量比 ≥ 1.5x）：</p>
            <p><span className="font-bold">6213 聯茂：</span>ADX 44.7（全場最高）、盤後漲幅 +10%，ABF 高頻基板極強</p>
            <p><span className="font-bold">2383 台光電：</span>ADX 44.1，但已超買（RSI 75 + BB 突破上軌）</p>
            <p><span className="font-bold">3189 景碩：</span>RSI 61（未超買）+ ADX 30 + 距支撐僅 -6%，最乾淨的結構</p>
            <p><span className="font-bold">3711 日月光：</span>volume_breakout 1.5x ✓ + ADX 21.5，封測先進封裝概念</p>
          </div>
        </section>

        {/* Phase 2: Sentiment */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">02</span>
            散戶情緒
          </h2>
          <div className="border border-neutral-900 px-4 py-3 text-[13px] space-y-2">
            <p><span className="font-bold">法人統計</span>（push 89）：外資 <span className="font-bold text-green-700">+440億</span>，自營 <span className="font-bold text-green-700">+118億</span>，投信 <span className="font-bold text-red-600">-43億</span>。PTT 情緒：「外資大哥低買高賣贏麻了」，投信被罵背骨。</p>
            <p><span className="font-bold">盤後閒聊</span>（push 98）：法說後夜盤下跌 260 點引發討論，主要圍繞 2330 是否利多出盡。重複 ticker：只有 2330，無其他新面孔。多數人認為是短線回測，非趨勢反轉。</p>
            <div className="border-t border-neutral-200 pt-2">
              <p className="font-bold">結論：</p>
              <p>大盤整體偏多，外資主導市場信心。法說後夜盤修正引發「利多出盡」疑慮，但聲量少，多方仍佔主流。無 PTT 獨立催生的新 ticker。</p>
            </div>
          </div>
        </section>

        {/* Phase 3: Macro / News */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">03</span>
            宏觀 / 新聞
          </h2>
          <div className="border border-neutral-900 px-4 py-3 text-[13px]">
            <p className="font-bold mb-1">台股 +409 點至 37,132 創歷史新高（+1.31%），成交 9,820 億</p>
            <ul className="list-disc list-outside ml-4 space-y-0.5 mt-2">
              <li>台積電法說：Q1 毛利率 66.2%、EPS 22.08 均創歷史新高，AI capex thesis 全面強化</li>
              <li>美股創高：標普首破 7,000、那指連 11 紅首破 20,000，費半繼續領漲</li>
              <li>美伊停火：川普暗示協議近，地緣政治風險降溫</li>
              <li>馬斯克 Terafab + AI5：AI5 晶片流片確認（台積電 + 三星），AI 供應鏈情緒加持</li>
              <li>GTC 台北：黃仁勳 6/1 主題演講確認，Computex 卡位戰開始</li>
              <li>籌碼確認：外資 +440億（連三日大買），資金真實流入；投信賣超但自營商承接</li>
            </ul>
            <p className="mt-2 pt-2 border-t border-neutral-200">次主線：CPO/矽光子（大立光、玉晶光）、面板輪動（友達、群創）、被動元件（國巨法說強）</p>
          </div>
        </section>

        {/* Phase 4: Cross-validation */}
        <section>
          <h2 className="text-base font-black mb-2">
            <span className="font-mono mr-2">04</span>
            交叉比對
          </h2>
          <div className="border border-neutral-900">
            <table className="w-full text-left text-[13px]">
              <thead className="bg-neutral-900 text-white">
                <tr>
                  <th className="px-3 py-1.5 font-bold">標的</th>
                  <th className="px-3 py-1.5 font-bold">Screener</th>
                  <th className="px-3 py-1.5 font-bold">Sentiment</th>
                  <th className="px-3 py-1.5 font-bold">News</th>
                  <th className="px-3 py-1.5 font-bold">判斷</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['2383 台光電', '★★（ADX 44，+5.7%）', '—', '★（AI基板，CPO）', '三方共振，但超買，等整理'],
                  ['6213 聯茂', '★★（ADX 44.7，+10%）', '—', '★（高頻基板）', '三方共振，超買，等整理'],
                  ['3189 景碩', '★（ADX 30，量1.86x，RSI 61）', '—', '★（ABF，AI PCB）', '雙重確認，最乾淨 → watchlist'],
                  ['3711 日月光', '★（量1.57x，RSI 73）', '—', '★（CoWoS封測）', '雙重確認 → watchlist'],
                  ['2454 聯發科', '★（量2.48x，止穩）', '—', '★（AI晶片設計）', '雙重確認，MACD仍負，等確認'],
                  ['2330 台積電', '✓（watchlist）', '討論最多', '★（法說亮眼）', 'Trigger 未達，保留 watch'],
                ].map(([name, scr, sent, news, judge], i) => {
                  const highlight = (name as string).includes('景碩');
                  return (
                    <tr key={i} className={`border-t border-neutral-200 ${highlight ? 'bg-yellow-50 font-bold' : ''}`}>
                      <td className="px-3 py-1.5 font-bold">{name}</td>
                      <td className="px-3 py-1.5">{scr}</td>
                      <td className="px-3 py-1.5">{sent}</td>
                      <td className="px-3 py-1.5">{news}</td>
                      <td className="px-3 py-1.5">{judge}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="border border-neutral-900 border-t-0 bg-neutral-900 text-white px-4 py-3 text-[13px]">
            <p className="font-bold mb-1.5">明日關注</p>
            <div className="space-y-1">
              <p><span className="bg-yellow-400 text-neutral-900 px-1.5 font-black text-xs mr-1">NEW</span>3189 景碩 — 量縮守穩後逢低評估（進場區 370–385，停損 360）</p>
              <p><span className="bg-yellow-400 text-neutral-900 px-1.5 font-black text-xs mr-1">NEW</span>3711 日月光 — 進 watchlist 觀察封測需求持續性</p>
              <p>台光電 / 聯茂 — 超買整理後再評估</p>
              <p>2330 台積電 — 法說消化期，看量能回到 1.5x</p>
            </div>
          </div>
        </section>

      </div>

      {/* Footer */}
      <div className="px-10 py-2 border-t border-neutral-300 flex justify-between items-center text-xs text-neutral-900">
        <span>AI-generated research · Not financial advice</span>
        <span className="font-mono">tw-trader</span>
      </div>
    </div>
  );
}

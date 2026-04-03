import { Send, Image, BarChart2, CheckCircle2 } from 'lucide-react';

export default function Threads() {
  return (
    <div className="p-6 md:p-10 hide-scrollbar flex flex-col gap-8 max-w-4xl mx-auto h-full">
      <header>
        <h1 className="text-3xl font-bold text-white tracking-tight">Social Threads</h1>
        <p className="text-neutral-400 mt-1">Review and publish AI-generated daily market summaries</p>
      </header>

      <div className="bg-[#12141c] border border-neutral-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col flex-1 relative max-h-[800px]">
        {/* Editor Area Header */}
        <div className="border-b border-neutral-800 bg-[#1a1c24] p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center font-bold text-indigo-400 border border-indigo-500/30">
               uncle
            </div>
            <div>
              <p className="text-white font-bold text-sm">實戰大叔 (TW_Trader_Bot)</p>
              <p className="text-xs text-neutral-500">Drafting today's close...</p>
            </div>
          </div>
          <button className="bg-emerald-500 hover:bg-emerald-600 text-[#0e1015] px-5 py-2 rounded-full font-bold text-sm transition-colors flex items-center gap-2 shadow-lg shadow-emerald-500/20">
            Publish Post <Send className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Content Area */}
        <div className="p-6 flex-1 overflow-y-auto font-sans leading-relaxed flex flex-col gap-4">
          <p className="text-white text-[15px]">
            收盤了！今天台積電 (2330) 終於突破 800 大關🔥，直接帶領大盤衝上新高。
            <br/><br/>
            老實說，今天早盤我原本還在觀望，差點就被洗出場，但看到機器人（喔不，是我的紀律系統）在 795 的地方果斷敲進，這波突破有抓到一半的肉，算是對得起這個月的帳單了 😅
            <br/><br/>
            接下來幾天大盤可能會在高檔震盪，不過看這量能...我覺得半導體設備、CoWoS概念股應該還有一波戲可以唱。鴻海 (2317) 昨天被洗掉有點嘔，今天它又硬是拉回 118 讓我很不是滋味啊！
            <br/><br/>
            今天的 AI 檢討筆記：
            1. TSMC SMA20 的防守線非常穩
            2. 不要預設立場，突破該買就買
            <br/><br/>
            大家今天有吃到肉嗎？還是又被洗碗了？留言一起取暖👇
            <br/><br/>
            <span className="text-emerald-500">#台股 #台積電 #量化交易 #股票日常</span>
          </p>

          <div className="mt-4 border border-neutral-800 rounded-xl overflow-hidden">
            <div className="bg-gradient-to-br from-indigo-900/40 to-[#12141c] p-6 aspect-video flex flex-col items-center justify-center border-b border-neutral-800">
              <BarChart2 className="w-16 h-16 text-indigo-500/50 mb-4" />
              <p className="text-indigo-400 font-bold tracking-widest text-xl">TSMC +0.69%</p>
              <p className="text-neutral-500 text-sm mt-2">Daily P&L: +NT$ 25,000</p>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-neutral-800 bg-[#12141c] flex items-center justify-between text-neutral-500">
          <div className="flex gap-4">
            <button className="hover:text-emerald-500 transition-colors p-2 rounded-full hover:bg-emerald-500/10"><Image className="w-5 h-5"/></button>
            <button className="hover:text-emerald-500 transition-colors p-2 rounded-full hover:bg-emerald-500/10"><BarChart2 className="w-5 h-5"/></button>
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-500/70 border border-emerald-500/20 bg-emerald-500/5 px-3 py-1.5 rounded-full">
            <CheckCircle2 className="w-3.5 h-3.5" />
             Tone: 실전대숙 (Practical Uncle) applied
          </div>
        </div>
      </div>
    </div>
  );
}

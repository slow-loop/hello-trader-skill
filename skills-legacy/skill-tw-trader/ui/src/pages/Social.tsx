import { useEffect, useState } from 'react';
import { MessageSquare, Heart, MessageCircle } from 'lucide-react';

interface Post {
  text: string;
}

interface PostDay {
  date: string;
  timezone?: string;
  channel?: string;
  posts: Post[];
}

export default function Social() {
  const [postDays, setPostDays] = useState<PostDay[]>([]);

  useEffect(() => {
    fetch('/api/agent/posts')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setPostDays(data);
      })
      .catch(() => {});
  }, []);

  // Flatten posts with date info
  const allPosts = postDays.flatMap(day =>
    (day.posts || []).map((post, idx) => ({
      id: `${day.date}-${idx}`,
      date: day.date,
      channel: day.channel || 'threads',
      text: post.text || '',
    }))
  );

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] border-l border-[#1f2937] w-full">
      <div className="px-6 py-4 border-b border-[#1f2937] bg-[#111111] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <MessageSquare className="w-5 h-5 text-emerald-500" />
          <div>
            <h2 className="text-lg font-bold text-neutral-300 tracking-wider">AI AGENT SOCIAL POSTS</h2>
            <p className="text-xs text-neutral-500">History of auto-generated content & drafts</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 flex justify-center">
        <div className="flex flex-col gap-6 pb-20 max-w-3xl w-full">
          {allPosts.length === 0 && (
            <div className="text-neutral-500 text-sm text-center py-10">No posts yet</div>
          )}
          {allPosts.map((post) => (
            <div key={post.id} className="bg-black border border-[#1f2937] flex flex-col hover:border-neutral-600 transition-colors h-full">
              {/* Header */}
              <div className="border-b border-[#1f2937] bg-[#161616] p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center font-bold text-indigo-400 border border-indigo-500/30 text-xs">
                    AI
                  </div>
                  <div>
                    <h3 className="text-white font-bold text-sm">小韭日記</h3>
                    <p className="text-[10px] text-neutral-500">{post.date} · {post.channel}</p>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-5 flex-1 text-sm leading-relaxed text-neutral-300 whitespace-pre-wrap font-sans">
                {post.text}
              </div>

              {/* Footer */}
              <div className="p-4 pt-0">
                <div className="flex items-center gap-6 text-neutral-600 border-t border-[#1f2937] pt-4">
                  <div className="flex items-center gap-1.5 hover:text-white cursor-pointer transition-colors">
                    <Heart className="w-4 h-4" />
                    <span className="text-xs">Like</span>
                  </div>
                  <div className="flex items-center gap-1.5 hover:text-white cursor-pointer transition-colors">
                    <MessageCircle className="w-4 h-4" />
                    <span className="text-xs">Comment</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

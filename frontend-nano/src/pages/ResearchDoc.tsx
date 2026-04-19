import { Link, useParams } from 'react-router-dom'
import { marked } from 'marked'
import { research } from '../data'

export default function ResearchDoc() {
  const { filename = '' } = useParams()
  const doc = research.find((r) => r.filename === filename)
  if (!doc) {
    return (
      <div>
        <Link to="/" className="text-sm text-neutral-500 hover:underline">← Timeline</Link>
        <p className="mt-4 text-neutral-500">找不到研究文件：{filename}</p>
      </div>
    )
  }
  const html = marked.parse(doc.body) as string
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-neutral-500 hover:underline">← Timeline</Link>
        <span className="text-sm text-neutral-500 font-mono">{doc.date}</span>
        <h1 className="text-lg font-black font-mono">{doc.filename}</h1>
        <Link to={`/ticker/${doc.symbolOrTheme}`} className="ml-auto text-sm text-blue-700 hover:underline">
          查看 {doc.symbolOrTheme}
        </Link>
      </div>
      <article
        className="bg-white border border-neutral-200 rounded-md p-6 prose prose-sm max-w-none prose-headings:font-black prose-h1:text-xl prose-h2:text-base prose-h2:mt-6 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-1"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}

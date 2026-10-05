import { useState } from "react"
import { HelpCircle, X, Loader2, Brain } from "lucide-react"

const API_BASE = "http://localhost:8000"

export default function WhyButton({ pageId, fieldKey }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [reasoning, setReasoning] = useState(null)

  async function fetchReasoning() {
    if (reasoning) {
      setOpen(!open)
      return
    }
    setOpen(true)
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/explain-field`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: pageId, field_key: fieldKey }),
      })
      const data = await res.json()
      setReasoning(data.reasoning || "No reasoning available.")
    } catch {
      setReasoning("Failed to fetch reasoning.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative inline-block">
      <button
        onClick={fetchReasoning}
        className="flex items-center gap-1 text-violet-400/60 hover:text-violet-300 transition-colors"
        title="Why did AI choose this?"
      >
        <HelpCircle className="w-3 h-3" />
        <span className="text-[10px]">Why?</span>
      </button>

      {open && (
        <div className="absolute z-50 top-6 left-0 w-72 bg-[#1a1a2e] border border-violet-500/20 rounded-xl shadow-2xl shadow-violet-900/30 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-violet-400" />
              <span className="text-xs font-bold text-violet-300">AI Reasoning</span>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/30 hover:text-white/60">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-white/30 text-xs py-2">
              <Loader2 className="w-3 h-3 animate-spin" /> Loading reasoning...
            </div>
          ) : (
            <div className="text-white/60 text-xs leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {reasoning}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

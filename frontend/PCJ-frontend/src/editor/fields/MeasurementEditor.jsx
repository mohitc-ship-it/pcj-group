import { useState } from "react"
import { Wand2, Loader2, Ruler } from "lucide-react"

const API_BASE = "http://localhost:8000"

export default function MeasurementEditor({ value, onUpdated }) {
  const [instruction, setInstruction] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function toDisplayUrl(path) {
    if (!path) return null
    if (path.startsWith("http")) return path
    if (path.includes("assets/")) return `${API_BASE}/${path.includes("assets/") ? "assets/" + path.split("assets/")[1] : path}`
    return path
  }

  async function handleRegenerate() {
    if (!instruction.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/regenerate-measurement`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: instruction.trim() }),
      })
      const result = await res.json()
      if (result.ok && result.new_url) {
        onUpdated()
        setInstruction("")
      } else {
        setError(result.error || "Failed to regenerate")
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const displayUrl = toDisplayUrl(value)

  return (
    <div className="flex flex-col gap-3">
      <div className="text-xs font-semibold text-white/50 uppercase tracking-widest mb-1 flex items-center gap-2">
        <Ruler className="w-3.5 h-3.5" />
        Measurement Diagram
      </div>

      {displayUrl && (
        <div className="relative rounded-xl overflow-hidden border border-white/10 bg-white">
          <img
            src={`${displayUrl}?t=${Date.now()}`}
            alt="Measurement Diagram"
            className="w-full max-h-64 object-contain"
          />
          <div className="absolute top-2 right-2 bg-black/60 text-white/60 text-xs rounded-full px-2 py-0.5">
            Current diagram
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-xs text-white/40">
          Modify the measurement diagram (image-to-image):
        </label>
        <textarea
          value={instruction}
          onChange={e => setInstruction(e.target.value)}
          placeholder='e.g. "Add hip measurement line", "Change to pant-specific measurements", "Add sleeve length indicator"'
          rows={2}
          className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-violet-500 resize-none transition-all"
        />
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      <button
        onClick={handleRegenerate}
        disabled={!instruction.trim() || loading}
        className={`flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold transition-all
          ${instruction.trim() && !loading
            ? "bg-violet-600/20 hover:bg-violet-600/30 text-violet-200 border border-violet-500/30"
            : "bg-white/5 text-white/25 border border-white/8 cursor-not-allowed"}`}
      >
        {loading
          ? <><Loader2 className="w-4 h-4 animate-spin" /> Regenerating diagram…</>
          : <><Wand2 className="w-4 h-4" /> Apply Modification</>
        }
      </button>
    </div>
  )
}

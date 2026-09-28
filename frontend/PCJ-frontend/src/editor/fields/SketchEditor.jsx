import { useState } from "react"
import { regenerateSketch } from "../../api/editorApi"
import { Wand2, Loader2, RefreshCw } from "lucide-react"

export default function SketchEditor({ value, onUpdated }) {
  const [instruction, setInstruction] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Normalise URL so it renders in browser
  function toDisplayUrl(path) {
    if (!path) return null
    if (path.startsWith("http")) return path
    if (path.includes("assets/")) return "http://localhost:8000/" + path.split("assets/")[0] + "assets/" + path.split("assets/")[1]
    return path
  }

  async function handleRegenerate() {
    if (!instruction.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await regenerateSketch(instruction.trim())
      if (result.new_url) {
        onUpdated()
        setInstruction("")
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
      <div className="text-xs font-semibold text-white/50 uppercase tracking-widest mb-1">
        Technical Sketch
      </div>

      {/* Current sketch preview */}
      {displayUrl && (
        <div className="relative rounded-xl overflow-hidden border border-white/10 bg-white">
          <img
            src={`${displayUrl}?t=${Date.now()}`}
            alt="Technical Sketch"
            className="w-full max-h-64 object-contain"
          />
          <div className="absolute top-2 right-2 bg-black/60 text-white/60 text-xs rounded-full px-2 py-0.5">
            Current sketch
          </div>
        </div>
      )}

      {/* Instruction input */}
      <div className="flex flex-col gap-2">
        <label className="text-xs text-white/40">
          Describe the modification to apply (image-to-image):
        </label>
        <textarea
          value={instruction}
          onChange={e => setInstruction(e.target.value)}
          placeholder='e.g. "Add a mandarin collar", "Remove the breast pocket", "Make the sleeves 3/4 length"'
          rows={3}
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
          ? <><Loader2 className="w-4 h-4 animate-spin" /> Regenerating sketch…</>
          : <><Wand2 className="w-4 h-4" /> Apply Modification</>
        }
      </button>

      {loading && (
        <p className="text-white/30 text-xs text-center">
          Using Gemini Pro image-to-image — this may take 20–40 seconds…
        </p>
      )}
    </div>
  )
}

import { useState } from "react"
import { updateMultipleFields } from "../../api/editorApi"

export default function MultiColorEditor({
  colors,
  pageId,
  onUpdated,
}) {
  const [loading, setLoading] = useState(false)
  const [manualInputs, setManualInputs] = useState({})

  async function selectPantone(colorIndex, option) {
    if (!option.code) return; // Ignore empty manual inputs
    try {
      setLoading(true)

      const newColors = [...colors]
      newColors[colorIndex] = {
        ...newColors[colorIndex],
        pantone_tcx: option.code,
        // Update name and hex if the option provides them
        ...(option.name && { color_name: option.name }),
        ...(option.hex && { color_hex: option.hex }),
      }

      const updates = {
        optional_colors: newColors,
      }
      
      // Update root color fields for backward compatibility
      if (colorIndex === 0) {
        updates.color_hex = newColors[0].color_hex
        updates.pantone_tcx = newColors[0].pantone_tcx
        updates.color_name = newColors[0].color_name
      }

      await updateMultipleFields({
        page_id: pageId,
        updates,
      })

      await onUpdated()
      // Clear manual input for this row on success
      setManualInputs(prev => ({...prev, [colorIndex]: ""}))
    } catch (e) {
      console.error(e)
      alert("Failed to update color")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 border p-4 rounded bg-[#18181b] border-white/10">
      <div className="text-xs font-bold text-white/80 tracking-wide uppercase">Garment Colors</div>
      
      {colors.map((c, i) => (
        <div key={i} className="bg-black/20 border border-white/10 rounded p-3">
          <div className="flex items-center gap-3 mb-2">
            <div
              className="w-10 h-10 rounded border border-white/20 shadow-sm"
              style={{ backgroundColor: c.color_hex }}
            />
            <div className="text-sm">
              <div className="font-semibold text-white/90">{c.color_name}</div>
              <div className="text-xs text-white/50 font-mono mt-0.5">
                {c.pantone_tcx}
              </div>
            </div>
          </div>
          
          {c.pantone_options && c.pantone_options.length > 0 && (
            <div className="mt-3 border-t border-white/10 pt-2">
              <div className="text-xs text-white/50 mb-2">Alternative Pantone Matches:</div>
              <div className="flex gap-2 flex-wrap">
                {c.pantone_options.map((opt, idx) => (
                  <button
                    key={idx}
                    onClick={() => selectPantone(i, opt)}
                    className={`text-[11px] border px-2 py-1 rounded transition-colors ${
                      c.pantone_tcx === opt.code 
                        ? 'bg-violet-600/90 text-white border-violet-500 shadow-[0_0_10px_rgba(139,92,246,0.2)]' 
                        : 'bg-white/5 text-white/70 border-white/10 hover:bg-white/10 hover:text-white'
                    }`}
                    title={opt.name}
                  >
                    {opt.code}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {(!c.pantone_options || c.pantone_options.length === 0) && (
            <div className="mt-2 text-xs text-white/40 italic">No alternative Pantone matches found.</div>
          )}
          
          <div className="mt-3 flex items-center gap-2 border-t border-white/5 pt-3">
            <input 
              type="text" 
              placeholder="Manual Code (e.g. 19-4010 TCX)" 
              className="bg-black/40 border border-white/10 text-white/90 text-xs px-2 py-1.5 rounded w-48 focus:outline-none focus:border-violet-500"
              value={manualInputs[i] || ""}
              onChange={(e) => setManualInputs({...manualInputs, [i]: e.target.value})}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  selectPantone(i, {code: manualInputs[i], name: "Manual Entry"});
                }
              }}
            />
            <button 
              onClick={() => selectPantone(i, {code: manualInputs[i], name: "Manual Entry"})}
              disabled={!manualInputs[i]}
              className="text-xs bg-white/5 border border-white/10 px-3 py-1.5 rounded hover:bg-white/10 text-white/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      ))}

      {loading && <div className="text-xs text-violet-400 animate-pulse">Saving changes...</div>}
    </div>
  )
}

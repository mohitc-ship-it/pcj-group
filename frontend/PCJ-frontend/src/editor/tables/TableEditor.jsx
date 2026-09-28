import { useState } from "react"
import { createPortal } from "react-dom"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { regenerateTableRow } from "../../api/editorApi"
import { Sparkles, Loader2, Send, X, Plus, Trash2 } from "lucide-react"

export default function TableEditor({ label, value, onChange, pageId }) {
  const HIDDEN_COLS = ["justification", "confidence", "requires_confirmation"]
  const columns = Object.keys(value[0] || {}).filter(c => !HIDDEN_COLS.includes(c))
  const [focusedCell, setFocusedCell] = useState(null)
  const [regenRow, setRegenRow] = useState(null)   // index of row being edited for AI regen
  const [regenInstruction, setRegenInstruction] = useState("")
  const [regenLoading, setRegenLoading] = useState(false)
  const [regenError, setRegenError] = useState(null)
  const [tooltipState, setTooltipState] = useState(null)

  function updateCell(row, col, val) {
    const updated = [...value]
    updated[row] = { ...updated[row], [col]: val }
    onChange(updated)
  }

  function addRow() {
    const empty = Object.fromEntries(columns.map(c => [c, ""]))
    onChange([...value, empty])
  }

  function deleteRow(index) {
    onChange(value.filter((_, i) => i !== index))
  }

  async function handleRegenRow(index) {
    if (!regenInstruction.trim()) return
    setRegenLoading(true)
    setRegenError(null)
    try {
      const result = await regenerateTableRow({
        page_id: pageId,
        table_key: label,
        row_index: index,
        row_data: value[index],
        instruction: regenInstruction.trim(),
      })
      if (result.updated_row) {
        const updated = [...value]
        updated[index] = result.updated_row
        onChange(updated)
        setRegenRow(null)
        setRegenInstruction("")
      }
    } catch (e) {
      setRegenError(e.message)
    } finally {
      setRegenLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: "100%", overflow: "hidden" }}>
      <h3 className="font-semibold mb-2 text-white/80">{label}</h3>

      <div className="border border-white/10 rounded-lg w-full block custom-table-scrollbar" style={{ overflowX: "auto", overflowY: "auto", maxHeight: "400px", maxWidth: "100%" }}>
        <table className="w-full text-sm" style={{ minWidth: "900px" }}>
          <thead className="bg-[#0a0a0f] border-b border-white/10 sticky top-0 z-10">
            <tr>
              {columns.map(c => (
                <th key={c} className="p-2 text-left font-medium text-white/60 text-xs uppercase tracking-wide" style={{ minWidth: "180px" }}>{c}</th>
              ))}
              <th className="p-2 w-20 text-white/40 text-xs">Actions</th>
            </tr>
          </thead>
          <tbody>
            {value.map((row, i) => (
              <>
                <tr key={i} className="border-b border-white/5 align-top hover:bg-white/[0.02]">
                  {columns.map((c, colIndex) => {
                    const cellId = `${i}-${c}`
                    const isFocused = focusedCell === cellId
                    return (
                      <td key={c} className="p-1 relative group hover:z-[60]" style={{ minWidth: "180px" }}>
                        <div className="relative">
                          <Textarea
                            value={row[c] ?? ""}
                            onChange={e => updateCell(i, c, e.target.value)}
                            onFocus={() => setFocusedCell(cellId)}
                            onBlur={() => setFocusedCell(null)}
                            className="border-0 rounded-none bg-transparent shadow-none focus-visible:ring-0 focus:bg-white/[0.03] transition-colors"
                            style={{
                              height: isFocused ? "120px" : "36px",
                              minHeight: isFocused ? "120px" : "36px",
                              fieldSizing: "fixed",
                              resize: "none",
                              overflowY: isFocused ? "auto" : "hidden",
                              transition: "height 0.2s ease-in-out",
                              paddingRight: (colIndex === 0 && row.justification) ? "25px" : "8px",
                              fontSize: "12px",
                            }}
                          />
                          {colIndex === 0 && row.justification && (
                            <div 
                              className="absolute right-2 top-2 text-yellow-500 cursor-pointer text-xs z-50"
                              onMouseEnter={(e) => {
                                const rect = e.currentTarget.getBoundingClientRect()
                                setTooltipState({
                                  text: row.justification,
                                  x: rect.right + 10,
                                  y: rect.top
                                })
                              }}
                              onMouseLeave={() => setTooltipState(null)}
                            >
                              💡
                            </div>
                          )}
                        </div>
                      </td>
                    )
                  })}
                  {/* Actions column */}
                  <td className="p-1 w-20">
                    <div className="flex items-center gap-1 justify-center pt-1">
                      <button
                        onClick={() => { setRegenRow(regenRow === i ? null : i); setRegenInstruction(""); setRegenError(null) }}
                        title="AI Regenerate this row"
                        className={`p-1.5 rounded-lg transition-all ${regenRow === i ? "bg-violet-600/30 text-violet-300" : "text-white/30 hover:text-violet-400 hover:bg-violet-600/10"}`}
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => deleteRow(i)}
                        title="Delete row"
                        className="p-1.5 rounded-lg text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>

                {/* AI regen inline panel for this row */}
                {regenRow === i && (
                  <tr key={`regen-${i}`} className="bg-violet-950/20 border-b border-violet-500/20">
                    <td colSpan={columns.length + 1} className="p-3">
                      <div className="flex flex-col gap-2">
                        <p className="text-xs font-semibold text-violet-300 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5" />
                          AI Edit Row {i + 1}
                          <span className="text-violet-400/60 font-normal">— describe the change to apply</span>
                        </p>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={regenInstruction}
                            onChange={e => setRegenInstruction(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && handleRegenRow(i)}
                            placeholder={`e.g. "Change to a French seam" or "Use gold-tone hardware"`}
                            className="flex-1 bg-white/5 border border-violet-500/30 rounded-lg px-3 py-2 text-sm text-white placeholder-white/25 focus:outline-none focus:border-violet-400 transition-all"
                            autoFocus
                          />
                          <button
                            onClick={() => handleRegenRow(i)}
                            disabled={!regenInstruction.trim() || regenLoading}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 border border-violet-500/30 text-sm font-semibold transition-all disabled:opacity-40"
                          >
                            {regenLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            {regenLoading ? "Updating…" : "Apply"}
                          </button>
                          <button
                            onClick={() => { setRegenRow(null); setRegenInstruction(""); setRegenError(null) }}
                            className="p-2 rounded-lg text-white/30 hover:text-white/60 transition-all"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        {regenError && <p className="text-red-400 text-xs">{regenError}</p>}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex gap-2">
        <Button onClick={addRow} variant="outline" size="sm" className="bg-white/5 border-white/10 text-white/80 hover:bg-white/10 hover:text-white"><Plus className="w-4 h-4 mr-1" /> Add Row</Button>
      </div>
      
      {/* Portal Tooltip */}
      {tooltipState && createPortal(
        <div 
          className="fixed w-72 bg-gradient-to-br from-[#1a103c] to-[#2a1354] text-violet-50 text-[13px] leading-relaxed p-3.5 rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.5)] border border-violet-500/30 backdrop-blur-md whitespace-normal z-[9999] font-medium pointer-events-none"
          style={{ 
            left: tooltipState.x, 
            top: tooltipState.y,
            transform: `translateY(calc(-50% + 10px))`
          }}
        >
          <div className="flex items-center gap-1.5 mb-2 text-violet-300 text-[10px] font-bold uppercase tracking-widest border-b border-violet-500/20 pb-1.5">
            <Sparkles className="w-3.5 h-3.5" /> AI Reasoning
          </div>
          {tooltipState.text}
        </div>,
        document.body
      )}
    </div>
  )
}

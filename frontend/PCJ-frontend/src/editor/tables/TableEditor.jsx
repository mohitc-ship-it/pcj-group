import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

export default function TableEditor({ label, value, onChange }) {
  // Filter out AI metadata fields so they don't clutter the table columns
  const HIDDEN_COLS = ["justification", "confidence", "requires_confirmation"]
  const columns = Object.keys(value[0] || {}).filter(c => !HIDDEN_COLS.includes(c))
  const [focusedCell, setFocusedCell] = useState(null)

  function updateCell(row, col, val) {
    const updated = [...value]
    updated[row] = { ...updated[row], [col]: val }
    onChange(updated)
  }

  function addRow() {
    const empty = Object.fromEntries(columns.map(c => [c, ""]))
    onChange([...value, empty])
  }

  return (
    <div style={{ maxWidth: '100%', overflow: 'hidden' }}>
      <h3 className="font-semibold mb-2">{label}</h3>
      
      <div 
        className="border rounded w-full block" 
        style={{ 
          overflowX: 'auto', 
          overflowY: 'auto', 
          maxHeight: '400px',
          maxWidth: '100%'
        }}
      >
        <table className="w-full text-sm" style={{ minWidth: '1000px' }}>
          <thead className="bg-slate-50 border-b sticky top-0 z-10">
            <tr>
              {columns.map(c => (
                <th key={c} className="p-2 text-left font-medium" style={{ minWidth: '200px' }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.map((row, i) => (
              <tr key={i} className="border-b align-top">
                {columns.map((c, colIndex) => {
                  const cellId = `${i}-${c}`
                  const isFocused = focusedCell === cellId
                  
                  // Render the AI reasoning tooltip inside the first column of the row
                  const isFirstCol = colIndex === 0
                  
                  return (
                    <td key={c} className="p-1 relative group" style={{ minWidth: '200px' }}>
                      <div className="relative">
                        <Textarea
                          value={row[c]}
                          onChange={e => updateCell(i, c, e.target.value)}
                          onFocus={() => setFocusedCell(cellId)}
                          onBlur={() => setFocusedCell(null)}
                          style={{
                            height: isFocused ? '150px' : '40px',
                            minHeight: isFocused ? '150px' : '40px',
                            fieldSizing: 'fixed',
                            resize: 'none',
                            overflowY: isFocused ? 'auto' : 'hidden',
                            transition: 'height 0.2s ease-in-out',
                            paddingRight: (isFirstCol && row.justification) ? '25px' : '8px'
                          }}
                        />
                        {isFirstCol && row.justification && (
                          <div 
                            className="absolute right-2 top-2 text-yellow-500 cursor-help"
                            title={row.justification}
                          >
                            💡
                          </div>
                        )}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Button className="mt-2" onClick={addRow}>Add Row</Button>
    </div>
  )
}

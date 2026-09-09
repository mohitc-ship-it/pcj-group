import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function TableEditor({ label, value, onChange }) {
  const columns = Object.keys(value[0] || {})

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
    <div>
      <h3 className="font-semibold mb-2">{label}</h3>

      <div className="overflow-auto border rounded">
        <table className="w-full text-sm">
          <thead>
            <tr>
              {columns.map(c => (
                <th key={c} className="p-2 text-left">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.map((row, i) => (
              <tr key={i}>
                {columns.map(c => (
                  <td key={c} className="p-1">
                    <Input
                      value={row[c]}
                      onChange={e => updateCell(i, c, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Button className="mt-2" onClick={addRow}>Add Row</Button>
    </div>
  )
}

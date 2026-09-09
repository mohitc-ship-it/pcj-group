import { useState } from "react"
import { updateImageField } from "../../api/editorApi"

export default function ColorSelector({
  label,
  value,
  options,
  pageId,
  fieldKey,
  onUpdated,
}) {
  const [loading, setLoading] = useState(false)

  async function selectColor(color) {
    try {
      setLoading(true)

      await updateImageField({
        page_id: pageId,
        field_path: fieldKey,
        image_url: color, // reuse same endpoint (string replacement)
      })

      await onUpdated()
    } catch (e) {
      console.error(e)
      alert("Failed to update color")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2 border p-3 rounded">
      <div className="text-sm font-medium">{label}</div>

      {/* Current color */}
      <div className="flex items-center gap-2">
        <div
          className="w-10 h-10 border rounded"
          style={{ backgroundColor: value }}
        />
        <span className="text-sm">{value}</span>
      </div>

      {/* Options */}
      <div className="flex gap-2 mt-2 flex-wrap">
        {options.map((color, idx) => (
          <div
            key={idx}
            className="w-8 h-8 rounded border cursor-pointer hover:ring-2 hover:ring-black"
            style={{ backgroundColor: color }}
            onClick={() => selectColor(color)}
            title={color}
          />
        ))}
      </div>

      {loading && <div className="text-xs">Updating...</div>}
    </div>
  )
}

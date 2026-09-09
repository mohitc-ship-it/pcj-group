import { useState } from "react"
import { updateMultipleFields } from "../../api/editorApi"

export default function ColorOptionSelector({
  current,
  options,
  pageId,
  onUpdated,
}) {
  const [loading, setLoading] = useState(false)

  async function selectColor(option) {
    try {
      setLoading(true)

      await updateMultipleFields({
        page_id: pageId,
        updates: {
          color_hex: option.color_hex,
          pantone_tcx: option.pantone_tcx,
          color_name: option.color_name,
        },
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
    <div className="space-y-3 border p-3 rounded">
      <div className="text-sm font-medium">Color</div>

      {/* Current */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded border"
          style={{ backgroundColor: current.color_hex }}
        />
        <div className="text-sm">
          <div>{current.color_name}</div>
          <div className="text-xs text-muted-foreground">
            {current.pantone_tcx}
          </div>
        </div>
      </div>

      {/* Options */}
      <div className="flex gap-2 flex-wrap mt-2">
        {options.map((opt, idx) => (
          <div
            key={idx}
            className="cursor-pointer border rounded p-1 hover:ring-2 hover:ring-black"
            onClick={() => selectColor(opt)}
          >
            <div
              className="w-8 h-8 rounded"
              style={{ backgroundColor: opt.color_hex }}
            />
          </div>
        ))}
      </div>

      {loading && <div className="text-xs">Updating...</div>}
    </div>
  )
}

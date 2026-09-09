import { useState } from "react"
import { Button } from "@/components/ui/button"
import { updateImageField } from "../../api/editorApi"

export default function DetailImageSelector({
  label,
  value,
  options,
  pageId,
  fieldKey,
  onUpdated,
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  async function selectImage(url) {
    try {
      setLoading(true)

      await updateImageField({
        page_id: pageId,
        field_path: fieldKey,
        image_url: url,
      })

      await onUpdated()
      setOpen(false)
    } catch (e) {
      console.error(e)
      alert("Failed to update image")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2 border p-3 rounded">
      <div className="text-sm font-medium">{label}</div>

      <img
        src={value}
        alt={label}
        className="max-h-32 border rounded"
      />

      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpen(!open)}
      >
        Change Image
      </Button>

      {open && (
        <div className="grid grid-cols-4 gap-2 mt-2">
          {options.map((url, idx) => (
            <img
              key={idx}
              src={url}
              onClick={() => selectImage(url)}
              className="cursor-pointer border hover:ring-2 hover:ring-black rounded max-h-20"
            />
          ))}
        </div>
      )}

      {loading && <div className="text-xs">Updating...</div>}
    </div>
  )
}

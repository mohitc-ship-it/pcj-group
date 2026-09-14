import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { updateImageField, uploadImage } from "../../api/editorApi"

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
  const fileInputRef = useRef(null)

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

  async function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return

    try {
      setLoading(true)
      const { url } = await uploadImage(file)
      await updateImageField({
        page_id: pageId,
        field_path: fieldKey,
        image_url: url,
      })
      await onUpdated()
      setOpen(false)
    } catch (err) {
      console.error(err)
      alert("Image upload failed")
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
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

      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setOpen(!open)}
          disabled={loading}
        >
          Select Existing
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
        >
          {loading ? "Uploading..." : "Upload New"}
        </Button>
      </div>

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
    </div>
  )
}

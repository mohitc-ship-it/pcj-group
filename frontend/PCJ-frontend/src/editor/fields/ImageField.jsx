// import { Input } from "@/components/ui/input"

// export default function ImageField({ label, value, onChange }) {
//   return (
//     <div>
//       <label className="text-sm font-medium">{label}</label>
//       <Input value={value} onChange={e => onChange(e.target.value)} />
//       {value && <img src={value} className="mt-2 max-h-40 border" />}
//     </div>
//   )
// }

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { uploadImage, updateImageField } from "../../api/editorApi"

export default function ImageField({
  label,
  value,
  pageId,
  fieldPath,
  onUpdated
}) {
  const fileInputRef = useRef(null)
  const [loading, setLoading] = useState(false)

  async function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return

    try {
      setLoading(true)

      // 1️⃣ Upload image
      const { url } = await uploadImage(file)

      // 2️⃣ Update draft JSON (backend stores local path)
      await updateImageField({
        page_id: pageId,
        field_path: fieldPath,
        image_url: url,
      })

      // 3️⃣ Reload page data
      await onUpdated()
    } catch (err) {
      console.error(err)
      alert("Image upload failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-1.5 mb-4">
      <label className="text-xs font-bold text-white/80 tracking-wide">{label}</label>

      {value && (
        <img
          src={value}
          alt={label}
          className="max-h-48 border border-white/10 rounded-xl bg-white/5 object-contain"
        />
      )}

      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        className="hidden"
        onChange={handleFileChange}
      />

      <Button
        variant="outline"
        size="sm"
        onClick={() => fileInputRef.current.click()}
        disabled={loading}
        className="bg-white/5 hover:bg-white/10 text-white/80 border-white/10 hover:text-white"
      >
        {loading ? "Uploading..." : "Upload Image"}
      </Button>
    </div>
  )
}

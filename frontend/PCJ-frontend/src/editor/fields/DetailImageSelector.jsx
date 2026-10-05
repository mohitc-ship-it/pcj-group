import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { updateImageField, uploadImage } from "../../api/editorApi"
import CropEditor from "./CropEditor"
import { Crop, ScanSearch, Upload } from "lucide-react"

export default function DetailImageSelector({
  label, value, options, pageId, fieldKey, onUpdated,
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showCrop, setShowCrop] = useState(false)
  const fileInputRef = useRef(null)

  // The full-res source images to crop from
  const sourceImages = [
    "http://localhost:8000/assets/image_0_front.png",
    "http://localhost:8000/assets/image_1_back.png"
  ]

  async function selectImage(url) {
    try {
      setLoading(true)
      await updateImageField({ page_id: pageId, field_path: fieldKey, image_url: url })
      await onUpdated()
      setOpen(false)
    } catch (e) {
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
      await updateImageField({ page_id: pageId, field_path: fieldKey, image_url: url })
      await onUpdated()
      setOpen(false)
    } catch {
      alert("Image upload failed")
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  // Map detail image index to crop region description
  const cropRegionMap = {
    "detail_image_1_url": "Top section — collar / neckline / upper detail",
    "detail_image_2_url": "Mid section — buttons / belt / closure area",
    "detail_image_3_url": "Back / lower section — hem / back detail",
    "detail_image_4_url": "Additional detail — pocket / trim / cuff",
    "detail_image_5_url": "Extra detail crop 5",
    "detail_image_6_url": "Extra detail crop 6",
  }

  return (
    <div className="space-y-2 border border-white/10 p-3 rounded-xl bg-white/[0.02]">
      <div className="text-xs font-semibold text-white/50 uppercase tracking-widest">{label}</div>
      {cropRegionMap[fieldKey] && (
        <div className="text-[10px] text-violet-400/60 bg-violet-600/5 border border-violet-500/10 rounded-lg px-2 py-1">
          Crop region: {cropRegionMap[fieldKey]}
        </div>
      )}

      {value && (
        <img src={value} alt={label} className="max-h-28 rounded-lg border border-white/10 bg-white/5 object-contain" />
      )}

      <input type="file" accept="image/*" ref={fileInputRef} className="hidden" onChange={handleFileChange} />

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setOpen(!open)}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 text-white/50 hover:text-white/80 hover:bg-white/5 transition-all"
        >
          <ScanSearch className="w-3.5 h-3.5" />
          AI Suggestions
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 text-white/50 hover:text-white/80 hover:bg-white/5 transition-all"
        >
          <Upload className="w-3.5 h-3.5" />
          {loading ? "Uploading…" : "Upload"}
        </button>
        <button
          onClick={() => setShowCrop(true)}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-violet-500/30 text-violet-300 hover:bg-violet-600/10 transition-all"
        >
          <Crop className="w-3.5 h-3.5" />
          Custom Crop
        </button>
      </div>

      {/* AI-generated thumbnail grid */}
      {open && options.length > 0 && (
        <div className="grid grid-cols-4 gap-2 mt-2">
          {options.map((url, idx) => (
            <img
              key={idx}
              src={url}
              onClick={() => selectImage(url)}
              className="cursor-pointer border border-white/10 hover:ring-2 hover:ring-violet-500 rounded-lg max-h-20 object-cover transition-all"
            />
          ))}
        </div>
      )}

      {/* Interactive crop modal */}
      {showCrop && (
        <CropEditor
          sourceImages={sourceImages}
          fieldKey={fieldKey}
          pageId={pageId}
          onCropped={(newUrl) => {
            onUpdated()
          }}
          onClose={() => setShowCrop(false)}
        />
      )}
    </div>
  )
}

import { useState, useRef } from "react"
import { updateImageField, uploadImage } from "../../api/editorApi"
import CropEditor from "./CropEditor"
import { Crop, ScanSearch, Upload, EyeOff, Check, X, Sparkles } from "lucide-react"

export default function DetailImageSelector({
  label, value, options = [], frontUrl, backUrl, pageId, fieldKey, onUpdated,
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showCrop, setShowCrop] = useState(false)
  const fileInputRef = useRef(null)

  // Dynamic source images to crop from (defaults to project assets if not explicitly passed)
  const _apiBase = import.meta.env.VITE_API_BASE_URL || ""
  const sourceImages = [
    frontUrl || `${_apiBase}/assets/image_0_front.png`,
    backUrl || `${_apiBase}/assets/image_1_back.png`,
  ].filter(Boolean)

  const isSelected = Boolean(value && String(value).trim() !== "")

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

  async function deselectImage() {
    try {
      setLoading(true)
      await updateImageField({ page_id: pageId, field_path: fieldKey, image_url: "" })
      await onUpdated()
      setOpen(false)
    } catch (e) {
      alert("Failed to deselect image")
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

  // Friendly slot label & region mapping
  const cropRegionMap = {
    "detail_image_1_url": "Collar / Neckline / Upper Detail",
    "detail_image_2_url": "Closure / Placket / Mid-Torso",
    "detail_image_3_url": "Hemline / Lower Sweep",
    "detail_image_4_url": "Sleeve / Cuff / Back Neckline",
    "detail_image_5_url": "Waist Contour / Seam Finish",
    "detail_image_6_url": "Back Hem / Vent / Accent Detail",
  }

  const slotIndex = fieldKey.match(/\d+/)?.[0] || ""
  const displayTitle = `Detail Slot ${slotIndex}: ${cropRegionMap[fieldKey] || label}`

  return (
    <div className={`space-y-3 border p-3.5 rounded-xl transition-all ${
      isSelected 
        ? "border-white/10 bg-white/[0.02]" 
        : "border-white/5 bg-white/[0.005] opacity-80 hover:opacity-100"
    }`}>
      {/* Header with Title & Inclusion Badge / Checkbox */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id={`toggle-${fieldKey}`}
            checked={isSelected}
            onChange={(e) => {
              if (e.target.checked) {
                // If checking an empty slot, select first available option or prompt custom crop
                if (options.length > 0) {
                  selectImage(options[0])
                } else {
                  setShowCrop(true)
                }
              } else {
                deselectImage()
              }
            }}
            disabled={loading}
            className="w-4 h-4 rounded border-white/20 bg-white/5 text-violet-600 focus:ring-violet-500 cursor-pointer"
          />
          <label 
            htmlFor={`toggle-${fieldKey}`} 
            className="text-xs font-semibold text-white/80 uppercase tracking-wider cursor-pointer"
          >
            {displayTitle}
          </label>
        </div>

        <div>
          {isSelected ? (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              <Check className="w-3 h-3" /> Included in PDF
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/40 border border-white/10 font-medium">
              <X className="w-3 h-3" /> Deselected (Excluded)
            </span>
          )}
        </div>
      </div>

      {/* Selected Image Preview or Deselected Empty State */}
      {isSelected ? (
        <div className="relative group flex items-center justify-center p-2 rounded-lg border border-white/10 bg-black/20">
          <img 
            src={value} 
            alt={label} 
            className="max-h-32 max-w-full rounded border border-white/10 bg-white/5 object-contain" 
          />
        </div>
      ) : (
        <div className="border border-dashed border-white/10 rounded-lg p-3 text-center bg-white/[0.01]">
          <p className="text-xs text-white/40 font-medium">
            Slot excluded from Tech Pack PDF
          </p>
          <p className="text-[11px] text-white/30 mt-0.5">
            Click AI Suggestions, Upload, or Custom Crop below to select an image for this slot.
          </p>
        </div>
      )}

      <input type="file" accept="image/*" ref={fileInputRef} className="hidden" onChange={handleFileChange} />

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          disabled={loading}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-all ${
            open
              ? "border-violet-500 bg-violet-600/20 text-violet-200"
              : "border-white/10 text-white/60 hover:text-white/90 hover:bg-white/5"
          }`}
          title="Choose from AI generated candidate crops"
        >
          <ScanSearch className="w-3.5 h-3.5" />
          AI Suggestions {options.length > 0 && `(${options.length})`}
        </button>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 text-white/60 hover:text-white/90 hover:bg-white/5 transition-all"
        >
          <Upload className="w-3.5 h-3.5" />
          {loading ? "Uploading…" : "Upload"}
        </button>

        <button
          type="button"
          onClick={() => setShowCrop(true)}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-violet-500/30 text-violet-300 hover:bg-violet-600/10 transition-all"
        >
          <Crop className="w-3.5 h-3.5" />
          Custom Crop
        </button>

        {isSelected && (
          <button
            type="button"
            onClick={deselectImage}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-rose-500/25 text-rose-300/80 hover:text-rose-200 hover:bg-rose-500/10 transition-all ml-auto"
            title="Deselect this crop to remove it from the PDF"
          >
            <EyeOff className="w-3.5 h-3.5" />
            Deselect
          </button>
        )}
      </div>

      {/* AI Suggestions Dropdown / Gallery */}
      {open && (
        <div className="mt-3 p-3 rounded-lg border border-violet-500/20 bg-black/40 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-violet-300 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-violet-400" />
              Click any AI crop to select it for this slot:
            </span>
            <button 
              type="button"
              onClick={() => setOpen(false)} 
              className="text-white/30 hover:text-white/70 text-xs"
            >
              Close
            </button>
          </div>

          {options.length > 0 ? (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 pt-1">
              {options.map((url, idx) => {
                const isCurrent = value && url.split("?")[0] === value.split("?")[0]
                return (
                  <div
                    key={idx}
                    onClick={() => selectImage(url)}
                    className={`group relative cursor-pointer rounded-lg border p-1 transition-all ${
                      isCurrent
                        ? "border-violet-500 ring-2 ring-violet-500/50 bg-violet-600/10"
                        : "border-white/10 hover:border-violet-400/50 hover:bg-white/5"
                    }`}
                  >
                    <img
                      src={url}
                      alt={`Suggestion ${idx + 1}`}
                      className="w-full h-16 object-cover rounded"
                    />
                    {isCurrent && (
                      <span className="absolute top-1 right-1 bg-violet-600 text-white rounded-full p-0.5">
                        <Check className="w-2.5 h-2.5" />
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-white/40 py-2">
              No AI suggestions found. Use Custom Crop or Upload above.
            </p>
          )}
        </div>
      )}

      {/* Interactive Crop Modal */}
      {showCrop && (
        <CropEditor
          sourceImages={sourceImages}
          fieldKey={fieldKey}
          pageId={pageId}
          onCropped={() => {
            onUpdated()
            setShowCrop(false)
          }}
          onClose={() => setShowCrop(false)}
        />
      )}
    </div>
  )
}

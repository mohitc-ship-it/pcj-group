import { useState, useCallback } from "react"
import ReactCrop from "react-image-crop"
import "react-image-crop/dist/ReactCrop.css"
import { manualCrop } from "../../api/editorApi"
import { Crop, Loader2, Check, X } from "lucide-react"

export default function CropEditor({ sourceImages, fieldKey, pageId, onCropped, onClose }) {
  const [crop, setCrop] = useState({ unit: "%", x: 10, y: 10, width: 80, height: 80 })
  const [completedCrop, setCompletedCrop] = useState(null)
  const [imgRef, setImgRef] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeImageIdx, setActiveImageIdx] = useState(0)
  
  const currentImageUrl = sourceImages[activeImageIdx]

  // Strip base URL to get relative asset path
  function toAssetPath(url) {
    if (url && url.includes("assets/")) {
      return "assets/" + url.split("assets/")[1]
    }
    return url
  }

  async function handleConfirm() {
    if (!completedCrop || !imgRef) return
    setLoading(true)
    setError(null)
    try {
      // Convert percent crop to pixel coordinates relative to natural image size
      const scaleX = imgRef.naturalWidth / imgRef.width
      const scaleY = imgRef.naturalHeight / imgRef.height

      const pixelX = Math.round(completedCrop.x * scaleX)
      const pixelY = Math.round(completedCrop.y * scaleY)
      const pixelW = Math.round(completedCrop.width * scaleX)
      const pixelH = Math.round(completedCrop.height * scaleY)

      const result = await manualCrop({
        image_path: toAssetPath(currentImageUrl),
        x: pixelX,
        y: pixelY,
        width: pixelW,
        height: pixelH,
        field_key: fieldKey,
        page_id: pageId,
      })

      if (result.ok) {
        onCropped(result.new_url)
        onClose()
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f0f17] border border-white/10 rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col gap-4 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Crop className="w-4 h-4 text-violet-400" />
            <h3 className="font-semibold text-white text-sm">Custom Crop</h3>
            <span className="text-white/30 text-xs">— drag to select the region you want</span>
          </div>
          <button onClick={onClose} className="text-white/30 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Crop area */}
        <div className="flex items-center justify-center rounded-xl overflow-hidden bg-black/40 border border-white/10">
          <ReactCrop
            crop={crop}
            onChange={(c) => setCrop(c)}
            onComplete={(c) => setCompletedCrop(c)}
            minWidth={20}
            minHeight={20}
          >
            <img
              ref={setImgRef}
              src={currentImageUrl}
              alt="Crop source"
              style={{ maxHeight: "55vh", maxWidth: "100%", objectFit: "contain" }}
            />
          </ReactCrop>
        </div>

        {error && <p className="text-red-400 text-xs">{error}</p>}

        {/* Source Image Selector */}
        {sourceImages.length > 1 && (
          <div className="flex items-center justify-center gap-2 mt-2">
            {sourceImages.map((src, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setActiveImageIdx(idx);
                  // Reset crop slightly when switching to prompt user to drag again
                  setCrop({ unit: "%", x: 10, y: 10, width: 80, height: 80 });
                }}
                className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                  activeImageIdx === idx 
                    ? "bg-violet-500 text-white font-medium" 
                    : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80"
                }`}
              >
                {idx === 0 ? "Front View" : "Back View"}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-white/50 hover:text-white/80 border border-white/10 hover:bg-white/5 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!completedCrop || loading}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all
              ${completedCrop && !loading
                ? "bg-violet-600/20 hover:bg-violet-600/30 text-violet-200 border border-violet-500/30"
                : "bg-white/5 text-white/25 border border-white/8 cursor-not-allowed"}`}
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Cropping…</>
              : <><Check className="w-4 h-4" /> Use This Crop</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { triggerGeneration } from "../api/editorApi"
import { Upload, Sparkles, ChevronRight, X, Plus, ImageIcon } from "lucide-react"

// Single image card (after upload)
function ImageCard({ file, preview, label, onRemove, index }) {
  return (
    <div className="relative group rounded-xl overflow-hidden border border-white/10 bg-white/5" style={{ height: 180 }}>
      <img src={preview} alt={label} className="w-full h-full object-cover" />

      {/* Label badge */}
      <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-sm rounded-full px-2.5 py-0.5 text-xs font-semibold text-white/80">
        {label}
      </div>

      {/* Remove button */}
      <button
        onClick={() => onRemove(index)}
        className="absolute top-2 right-2 w-6 h-6 rounded-full bg-red-500/80 hover:bg-red-500 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X className="w-3.5 h-3.5 text-white" />
      </button>
    </div>
  )
}

// Add more images button
function AddImageCard({ onFile }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"))
    files.forEach(f => onFile(f))
  }, [onFile])

  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200
        ${dragging ? "border-violet-400 bg-violet-950/30" : "border-white/10 bg-white/5 hover:border-violet-500/40 hover:bg-white/8"}`}
      style={{ height: 180 }}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => Array.from(e.target.files).forEach(f => onFile(f))}
      />
      <Plus className="w-7 h-7 text-white/25 mb-2" />
      <span className="text-white/30 text-xs">Add image</span>
    </div>
  )
}

function FormField({ label, id, value, onChange, placeholder, required = false }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-white/60 uppercase tracking-widest">
        {label}{required && <span className="text-violet-400 ml-1">*</span>}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/25 focus:outline-none focus:border-violet-500 transition-all duration-200"
      />
    </div>
  )
}

function getImageLabel(index) {
  if (index === 0) return "Front"
  if (index === 1) return "Back"
  return `Detail ${index - 1}`
}

export default function UploadPage() {
  const navigate = useNavigate()

  // All images as array: [{ file, preview }, ...]
  const [images, setImages] = useState([])

  const [brand, setBrand] = useState("")
  const [collection, setCollection] = useState("")
  const [season, setSeason] = useState("")
  const [fabric, setFabric] = useState("")
  const [sizeRange, setSizeRange] = useState("")
  const [sampleSize, setSampleSize] = useState("")
  const [notes, setNotes] = useState("")

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function addImage(file) {
    setImages(prev => {
      if (prev.length >= 2) return prev
      return [...prev, { file, preview: URL.createObjectURL(file) }]
    })
  }

  function removeImage(index) {
    setImages(prev => {
      // Revoke the object URL to free memory
      URL.revokeObjectURL(prev[index].preview)
      return prev.filter((_, i) => i !== index)
    })
  }

  function buildContext() {
    const lines = []
    if (brand) lines.push(`Brand: ${brand}`)
    if (collection) lines.push(`Collection: ${collection}`)
    if (season) lines.push(`Season: ${season}`)
    if (fabric) lines.push(`Fabric preference: ${fabric}`)
    if (sizeRange) lines.push(`Size Range: ${sizeRange}`)
    if (notes) lines.push(`\nAdditional Notes:\n${notes}`)
    return lines.join("\n")
  }

  const canGenerate = images.length === 2 && brand.trim()

  async function handleGenerate() {
    if (!canGenerate) return
    setError(null)
    setLoading(true)
    try {
      const imageFiles = images.map(img => img.file)
      const { job_id } = await triggerGeneration(imageFiles, buildContext(), sampleSize)
      navigate(`/generating?job_id=${job_id}`)
    } catch (err) {
      setError(err.message || "Failed to start generation. Is the backend running?")
      setLoading(false)
    }
  }

  // Initial empty state — big drop zone
  const fileInputRef = useRef(null)
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"))
    files.forEach(f => addImage(f))
  }, [])

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight">PCJ Tech Pack Studio</span>
        </div>
        <span className="text-white/30 text-sm">AI-Powered Tech Pack Generator</span>
      </header>

      <main className="flex-1 flex items-start justify-center px-6 py-10">
        <div className="w-full max-w-5xl">

          {/* Hero */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-violet-600/10 border border-violet-500/20 rounded-full px-4 py-1.5 text-violet-300 text-xs font-semibold mb-5 tracking-wide">
              <Sparkles className="w-3.5 h-3.5" />
              9-Page Factory-Ready Tech Pack in Minutes
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-3">Upload Your Garment</h1>
            <p className="text-white/40 text-base max-w-lg mx-auto leading-relaxed">
              Upload exactly 2 garment photos (Front and Back).
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

            {/* LEFT — Images */}
            <div className="flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-white/80 uppercase tracking-widest mb-1">Garment Photos</h2>
                  <p className="text-white/30 text-xs">
                    First image = Front, second = Back. Additional images are used as detail shots.
                  </p>
                </div>
                {images.length > 0 && (
                  <div className={`text-xs px-3 py-1 rounded-full border font-semibold
                    ${images.length >= 2 ? "bg-green-500/10 border-green-500/30 text-green-400" : "bg-yellow-500/10 border-yellow-500/30 text-yellow-400"}`}>
                    {images.length} / 2 images {images.length === 2 ? "✓" : ""}
                  </div>
                )}
              </div>

              {/* Image grid */}
              {images.length === 0 ? (
                // Empty state — large drop zone
                <div
                  className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-white/10 bg-white/5 hover:border-violet-500/40 hover:bg-white/8 transition-all cursor-pointer"
                  style={{ minHeight: 300 }}
                  onClick={() => fileInputRef.current?.click()}
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => Array.from(e.target.files).forEach(f => addImage(f))}
                  />
                  <div className="w-16 h-16 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center mb-4">
                    <Upload className="w-7 h-7 text-violet-400" />
                  </div>
                  <p className="text-white font-semibold mb-1">Drop garment photos here</p>
                  <p className="text-white/30 text-sm">or click to browse — you can select multiple files at once</p>
                  <div className="flex items-center gap-4 mt-5">
                    <div className="flex items-center gap-1.5 text-white/25 text-xs">
                      <ImageIcon className="w-3.5 h-3.5" />
                      Exactly 2 images (Front and Back)
                    </div>
                  </div>
                </div>
              ) : (
                // Image grid with thumbnails + add more
                <div className="grid grid-cols-2 gap-3">
                  {images.map((img, i) => (
                    <ImageCard
                      key={i}
                      file={img.file}
                      preview={img.preview}
                      label={getImageLabel(i)}
                      onRemove={removeImage}
                      index={i}
                    />
                  ))}
                  {/* Show "Add image" card if under 2 */}
                  {images.length < 2 && <AddImageCard onFile={addImage} />}
                </div>
              )}

              {/* Help text */}
              {images.length > 0 && (
                <div className="bg-white/[0.03] border border-white/6 rounded-xl px-4 py-3">
                  <p className="text-white/40 text-xs leading-relaxed">
                    <span className="text-white/60 font-semibold">Image order matters.</span> First image is used as the front view, second as the back.
                  </p>
                </div>
              )}
            </div>

            {/* RIGHT — Context Form */}
            <div className="flex flex-col gap-5">
              <div>
                <h2 className="text-sm font-bold text-white/80 uppercase tracking-widest mb-1">Garment Context</h2>
                <p className="text-white/30 text-xs">This shapes every page of the tech pack.</p>
              </div>

              <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-6 flex flex-col gap-5">
                <FormField id="brand" label="Brand Name" value={brand} onChange={setBrand} placeholder="e.g. JC & Co" required />
                <div className="grid grid-cols-2 gap-4">
                  <FormField id="collection" label="Collection" value={collection} onChange={setCollection} placeholder="e.g. Grandiose" />
                  <FormField id="season" label="Season" value={season} onChange={setSeason} placeholder="e.g. FW25" />
                </div>
                <FormField id="fabric" label="Fabric Preference" value={fabric} onChange={setFabric} placeholder="e.g. Wool blend / Gabardine" />
                <div className="grid grid-cols-2 gap-4">
                  <FormField id="sizeRange" label="Size Range" value={sizeRange} onChange={setSizeRange} placeholder="e.g. XS – XL" />
                  <FormField id="sampleSize" label="Sample Size" value={sampleSize} onChange={setSampleSize} placeholder="e.g. M" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="notes" className="text-xs font-semibold text-white/60 uppercase tracking-widest">Additional Notes</label>
                  <textarea
                    id="notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Measurements, construction preferences, special trims…"
                    rows={4}
                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/25 focus:outline-none focus:border-violet-500 transition-all duration-200 resize-none"
                  />
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                  <X className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-red-300 text-sm">{error}</p>
                </div>
              )}

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={!canGenerate || loading}
                className={`w-full flex items-center justify-center gap-3 rounded-2xl py-4 font-bold text-base transition-all duration-300
                  ${canGenerate && !loading
                    ? "bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white shadow-lg shadow-violet-900/40 hover:-translate-y-0.5 cursor-pointer"
                    : "bg-white/5 text-white/20 cursor-not-allowed border border-white/8"}`}
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                    </svg>
                    Starting generation…
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Generate Tech Pack
                    {images.length === 2 && (
                      <span className="text-white/50 text-sm font-normal">(2/2 images)</span>
                    )}
                    <ChevronRight className="w-5 h-5 opacity-60" />
                  </>
                )}
              </button>

              {!canGenerate && !loading && (
                <p className="text-white/25 text-xs text-center -mt-2">
                  {images.length < 2
                    ? `Upload at least ${2 - images.length} more image${images.length === 1 ? "" : "s"} (front + back required)`
                    : "Enter brand name to continue"}
                </p>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

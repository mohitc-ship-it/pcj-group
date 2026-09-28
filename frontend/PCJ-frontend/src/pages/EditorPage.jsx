import { useEffect, useState } from "react"
import { fetchPageData, renderPreview, resetDraft, saveDraft, downloadPdf } from "../api/editorApi"
import PreviewPane from "../components/PreviewPane"
import PageEditor from "../editor/PageEditor"
import {
  FileText, Layers, PenTool, Package, Hammer,
  Ruler, Shirt, Image, Tag, Download, RotateCcw, Save, Check, Loader2, LayoutTemplate
} from "lucide-react"

const PAGES = [
  { id: "header", label: "Header Details",      icon: LayoutTemplate },
  { id: "page_1", label: "Cover Page",         icon: FileText },
  { id: "page_2", label: "CAD Design",          icon: Layers },
  { id: "page_3", label: "Technical Sketch",    icon: PenTool },
  { id: "page_4", label: "Accessories",         icon: Package },
  { id: "page_5", label: "Construction",        icon: Hammer },
  { id: "page_6", label: "Size Chart",          icon: Ruler },
  { id: "page_10", label: "Garment Measurements", icon: Ruler },
  { id: "page_7", label: "Fabrics & Quality",   icon: Shirt },
  { id: "page_8", label: "Reference Images",    icon: Image },
  { id: "page_9", label: "Care Label",          icon: Tag },
]

export default function EditorPage() {
  const [page, setPage] = useState("page_1")
  const [data, setData] = useState({})
  const [previewHtml, setPreviewHtml] = useState("")
  const [loadingPage, setLoadingPage] = useState(false)
  const [saveState, setSaveState] = useState("idle")

  useEffect(() => {
    setLoadingPage(true)
    fetchPageData(page).then(setData).finally(() => setLoadingPage(false))
  }, [page])

  useEffect(() => {
    const t = setTimeout(() => {
      renderPreview(page, data).then(setPreviewHtml)
    }, 350)
    return () => clearTimeout(t)
  }, [data, page])

  async function reloadCurrentPage() {
    const fresh = await fetchPageData(page)
    setData(fresh)
  }

  async function handleSave() {
    setSaveState("saving")
    try {
      await saveDraft(page, data)
      setSaveState("saved")
      setTimeout(() => setSaveState("idle"), 2200)
    } catch {
      setSaveState("idle")
      alert("Failed to save. Please try again.")
    }
  }

  async function handleReset() {
    if (!window.confirm("Reset all pages to the original generated output?")) return
    try {
      await resetDraft()
      const fresh = await fetchPageData(page)
      setData(fresh)
    } catch {
      alert("Failed to reset template")
    }
  }

  const SaveIcon = saveState === "saving" ? Loader2 : saveState === "saved" ? Check : Save

  return (
    <div className="h-screen flex overflow-hidden bg-[#0a0a0f] text-white">

      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col border-r border-white/8 bg-white/[0.02]">
        <div className="px-5 py-4 border-b border-white/8">
          <span className="font-bold text-sm tracking-tight text-white/90">PCJ Tech Pack</span>
          <p className="text-white/30 text-xs mt-0.5">Manual Editor</p>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 space-y-0.5 px-2">
          {PAGES.map(({ id, label, icon: Icon }) => {
            const active = page === id
            return (
              <button
                key={id}
                onClick={() => setPage(id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-all text-left
                  ${active
                    ? "bg-violet-600/20 text-violet-200 font-semibold border border-violet-500/30"
                    : "text-white/50 hover:text-white/80 hover:bg-white/5"}`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{label}</span>
              </button>
            )
          })}
        </nav>

        <div className="p-3 border-t border-white/8 flex flex-col gap-2">
          <button
            onClick={handleSave}
            disabled={saveState === "saving"}
            className={`w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-semibold transition-all
              ${saveState === "saved"
                ? "bg-green-600/20 text-green-300 border border-green-500/30"
                : "bg-violet-600/20 hover:bg-violet-600/30 text-violet-200 border border-violet-500/30"}`}
          >
            <SaveIcon className={`w-4 h-4 ${saveState === "saving" ? "animate-spin" : ""}`} />
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved!" : "Save Page"}
          </button>

          <button
            onClick={downloadPdf}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-semibold bg-white/5 hover:bg-white/10 text-white/70 hover:text-white border border-white/10 transition-all"
          >
            <Download className="w-4 h-4" />
            Export PDF
          </button>

          <button
            onClick={handleReset}
            className="w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-lg text-xs text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset to original
          </button>
        </div>
      </aside>

      {/* Main split panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left editor */}
        <div className="w-[45%] min-w-0 flex flex-col border-r border-white/8">
          <div className="px-5 py-3 border-b border-white/8 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-sm text-white/90">
                {PAGES.find(p => p.id === page)?.label}
              </h2>
              <p className="text-white/30 text-xs">{page}</p>
            </div>
            {loadingPage && <Loader2 className="w-4 h-4 animate-spin text-violet-400" />}
          </div>
          <div className="flex-1 overflow-y-auto p-5 min-w-0 overflow-x-hidden">
            {loadingPage
              ? <div className="flex items-center justify-center h-40 text-white/30 text-sm">Loading...</div>
              : <PageEditor data={data} onChange={setData} pageId={page} reloadPage={reloadCurrentPage} />
            }
          </div>
        </div>

        {/* Right preview */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-5 py-3 border-b border-white/8">
            <h2 className="font-semibold text-sm text-white/60">Live Preview</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <PreviewPane html={previewHtml} />
          </div>
        </div>
      </div>
    </div>
  )
}

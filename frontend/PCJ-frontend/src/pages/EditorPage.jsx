
import { useEffect, useState } from "react"
import { fetchPageData, renderPreview, resetDraft } from "../api/editorApi"
import PreviewPane from "../components/PreviewPane"
import PageEditor from "../editor/PageEditor"
import Navbar from "../components/Navbar"

export default function EditorPage() {
  const [page, setPage] = useState("page_1")
  const [data, setData] = useState({})
  const [previewHtml, setPreviewHtml] = useState("")
  
  async function reloadCurrentPage() {
    const fresh = await fetchPageData(page)
    setData(fresh)
  }

  useEffect(() => {
    fetchPageData(page).then(setData)
  }, [page])

  useEffect(() => {
    const t = setTimeout(() => {
      renderPreview(page, data).then(setPreviewHtml)
    }, 300)
    return () => clearTimeout(t)
  }, [data, page])

  async function handleReset() {
    const confirmReset = window.confirm(
      "This will reset all pages to the original template. Continue?"
    )

    if (!confirmReset) return

    try {
      await resetDraft()
      const freshData = await fetchPageData(page)
      setData(freshData)
    } catch (err) {
      alert("Failed to reset template")
      console.error(err)
    }
  }

  return (
    <div className="h-screen flex flex-col">

      <Navbar
        page={page}
        onPageChange={setPage}
        onReset={handleReset}
      />

      <div className="grid grid-cols-2 flex-1 overflow-hidden">
        <div className=" overflow-scroll">
          <PageEditor
            data={data}
            onChange={setData}
            pageId={page}
            reloadPage={reloadCurrentPage}
          />
        </div>
        <div className=" overflow-scroll">
          <PreviewPane html={previewHtml} />
        </div>
      </div>

    </div>
  )
}

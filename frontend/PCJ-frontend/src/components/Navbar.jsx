import { useLocation, useNavigate } from "react-router-dom"
import PageSelector from "./PageSelector"
import { Button } from "@/components/ui/button"
import { downloadPdf } from "../api/editorApi"
import { Sparkles, ArrowLeft, Download } from "lucide-react"

export default function Navbar({ page, onPageChange, onReset }) {
  const location = useLocation()
  const navigate = useNavigate()
  const isEditor = location.pathname === "/editor"

  return (
    <div className="h-14 flex items-center justify-between px-6 border-b bg-white shadow-sm shrink-0">

      {/* LEFT */}
      <div className="flex items-center gap-4">
        {/* Logo / brand */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="text-base font-semibold tracking-wide text-gray-800">
            PCJ Group
          </span>
        </div>

        {/* Back link — only on editor */}
        {isEditor && (
          <>
            <span className="text-gray-300">|</span>
            <button
              onClick={() => navigate("/")}
              className="flex items-center gap-1.5 text-sm text-violet-600 hover:text-violet-700 font-medium transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              New Tech Pack
            </button>
          </>
        )}

        {/* Page selector — only on editor */}
        {isEditor && (
          <PageSelector page={page} onChange={onPageChange} />
        )}
      </div>

      {/* RIGHT */}
      <div className="flex items-center gap-3">
        {isEditor && (
          <>
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-1.5 text-violet-600 border-violet-200 hover:bg-violet-50"
              onClick={downloadPdf}
            >
              <Download className="w-3.5 h-3.5" />
              Download PDF
            </Button>

            <Button
              variant="destructive"
              size="sm"
              onClick={onReset}
            >
              Reset Template
            </Button>
          </>
        )}
      </div>
    </div>
  )
}

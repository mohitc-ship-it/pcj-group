import { useState, useEffect } from "react"
import { BarChart3, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, HelpCircle, RefreshCw, Wand2, Loader2 } from "lucide-react"

const API_BASE = "http://localhost:8000"

function ScoreBadge({ score, status }) {
  const colors = {
    high: "bg-green-500/20 text-green-300 border-green-500/30",
    medium: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
    low: "bg-red-500/20 text-red-300 border-red-500/30",
  }
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${colors[status] || colors.medium}`}>
      {score}%
    </span>
  )
}

function ComponentCard({ component }) {
  const [expanded, setExpanded] = useState(false)

  const Icon = component.status === "high" ? CheckCircle2
    : component.status === "low" ? AlertTriangle
    : HelpCircle

  const iconColor = component.status === "high" ? "text-green-400"
    : component.status === "low" ? "text-red-400"
    : "text-yellow-400"

  return (
    <div className="border border-white/8 rounded-xl bg-white/[0.02] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <Icon className={`w-4 h-4 shrink-0 ${iconColor}`} />
        <span className="flex-1 text-left text-sm text-white/80 font-medium">{component.name}</span>
        <span className="text-xs text-white/30 mr-2">{component.value}</span>
        <ScoreBadge score={component.score} status={component.status} />
        {expanded ? <ChevronDown className="w-3.5 h-3.5 text-white/30" /> : <ChevronRight className="w-3.5 h-3.5 text-white/30" />}
      </button>
      {expanded && (
        <div className="px-4 pb-3 border-t border-white/5">
          <pre className="text-xs text-white/50 leading-relaxed whitespace-pre-wrap mt-2">{component.reasoning}</pre>
        </div>
      )}
    </div>
  )
}

export default function AccuracyPanel() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [fixResult, setFixResult] = useState(null)

  async function fetchReport() {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/accuracy-report`)
      const data = await res.json()
      setReport(data)
    } catch {
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  async function runAutoFix() {
    setFixing(true)
    setFixResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/auto-correct`, { method: "POST" })
      const data = await res.json()
      setFixResult(data)
      // Refresh report after fixes
      await fetchReport()
    } catch {
      setFixResult({ error: "Auto-fix failed" })
    } finally {
      setFixing(false)
    }
  }

  useEffect(() => { fetchReport() }, [])

  if (!report && !loading) return null

  const overallColor = report?.overall_score >= 85 ? "text-green-400"
    : report?.overall_score >= 70 ? "text-yellow-400"
    : "text-red-400"

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-violet-400" />
          <span className="text-xs font-bold text-white/60 uppercase tracking-widest">Accuracy Report</span>
        </div>
        <button onClick={fetchReport} disabled={loading} className="text-white/30 hover:text-white/60 transition-colors">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {loading && !report && (
        <div className="text-white/30 text-xs text-center py-4">Analyzing tech pack...</div>
      )}

      {report && (
        <>
          {/* Overall score */}
          <div className="flex items-center gap-4 bg-white/[0.03] border border-white/8 rounded-xl px-4 py-3">
            <div className="flex flex-col items-center">
              <span className={`text-3xl font-bold ${overallColor}`}>{report.overall_score}%</span>
              <span className="text-[10px] text-white/30">Overall</span>
            </div>
            <div className="flex-1">
              <p className="text-xs text-white/60">{report.garment} — {report.category}</p>
              <p className="text-[10px] text-white/30 mt-1">
                {report.high_confidence} high confidence · {report.needs_review} need review
              </p>
            </div>
          </div>

          {/* Auto-fix button */}
          {report.needs_review > 0 && (
            <button
              onClick={runAutoFix}
              disabled={fixing}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold bg-violet-600/20 hover:bg-violet-600/30 text-violet-200 border border-violet-500/30 transition-all"
            >
              {fixing
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Auto-fixing issues...</>
                : <><Wand2 className="w-4 h-4" /> Auto-Fix {report.needs_review} Issues</>
              }
            </button>
          )}

          {/* Auto-fix results */}
          {fixResult && (
            <div className="bg-white/[0.03] border border-white/8 rounded-xl p-3 text-xs space-y-2">
              {fixResult.corrections_made?.map((c, i) => (
                <div key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-green-300 font-medium">{c.action}</p>
                    <p className="text-white/40">{c.reason}</p>
                  </div>
                </div>
              ))}
              {fixResult.needs_manual_review?.map((n, i) => (
                <div key={i} className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-yellow-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-yellow-300 font-medium">{n.field}: {n.issue}</p>
                    {n.suggestion && <p className="text-white/40">{n.suggestion}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Component breakdown */}
          <div className="flex flex-col gap-1.5">
            {report.components?.map((comp, i) => (
              <ComponentCard key={i} component={comp} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

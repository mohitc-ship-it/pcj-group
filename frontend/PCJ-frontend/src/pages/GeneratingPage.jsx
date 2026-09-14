import { useEffect, useState, useRef } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { getGenerationStatus } from "../api/editorApi"
import { Sparkles, CheckCircle2, Clock, AlertCircle, ChevronRight, Brain } from "lucide-react"

const PIPELINE_STEPS = [
  "Starting pipeline...",
  "Header",
  "Color Extraction",
  "Vision Analysis",
  "Garment Classification",
  "Fabric Decision",
  "Construction Specs",
  "Measurements",
  "Resolver",
  "Verification",
  "Complete",
]

function stepIndex(stepName) {
  const idx = PIPELINE_STEPS.findIndex(s =>
    stepName?.toLowerCase().includes(s.toLowerCase()) ||
    s.toLowerCase().includes(stepName?.toLowerCase())
  )
  return idx >= 0 ? idx : 0
}

function ReasoningCard({ entry, isLatest }) {
  return (
    <div className={`rounded-2xl border p-4 transition-all duration-500 ${
      isLatest
        ? "border-violet-500/40 bg-violet-950/30 shadow-lg shadow-violet-900/20"
        : "border-white/6 bg-white/[0.025]"
    }`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
          isLatest ? "bg-violet-500" : "bg-green-500/80"
        }`}>
          {isLatest
            ? <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
            : <CheckCircle2 className="w-3 h-3 text-white" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-xs font-bold text-white/80 uppercase tracking-widest">{entry.step}</span>
            <span className="text-white/25 text-xs font-mono shrink-0">{entry.timestamp}</span>
          </div>
          {entry.decision && (
            <p className="text-sm font-semibold text-white mb-1.5">{entry.decision}</p>
          )}
          {entry.reasoning && (
            <details className="mt-2 text-white/45 text-xs leading-relaxed group">
              <summary className="cursor-pointer text-violet-400/80 hover:text-violet-300 font-medium select-none mb-1 list-none flex items-center gap-1">
                <span className="group-open:hidden">▶ Show AI Thinking</span>
                <span className="hidden group-open:inline">▼ Hide AI Thinking</span>
              </summary>
              <div className="pl-2 border-l border-white/10 mt-1 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                {entry.reasoning}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}

export default function GeneratingPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const job_id = searchParams.get("job_id")

  const [status, setStatus] = useState("running")
  const [progress, setProgress] = useState(2)
  const [currentStep, setCurrentStep] = useState("Starting pipeline...")
  const [stepLog, setStepLog] = useState([])
  const [error, setError] = useState(null)

  const logEndRef = useRef(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    if (!job_id) {
      setError("No job ID found. Please go back and upload images again.")
      setStatus("error")
      return
    }

    async function poll() {
      try {
        const data = await getGenerationStatus(job_id)
        setProgress(data.progress ?? 0)
        setCurrentStep(data.current_step ?? "")
        setStepLog(data.step_log ?? [])

        if (data.status === "done") {
          setStatus("done")
          clearInterval(pollingRef.current)
          setTimeout(() => navigate("/editor"), 1500)
        } else if (data.status === "error") {
          setStatus("error")
          setError(data.error || "An unknown error occurred.")
          clearInterval(pollingRef.current)
        }
      } catch (e) {
        console.warn("[poll error]", e)
      }
    }

    poll()
    pollingRef.current = setInterval(poll, 3000)
    return () => clearInterval(pollingRef.current)
  }, [job_id, navigate])

  // Auto-scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [stepLog])

  const currentStepIdx = Math.min(
    Math.max(0, Math.round((progress / 100) * (PIPELINE_STEPS.length - 1))),
    PIPELINE_STEPS.length - 1
  )

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
        <div className="flex items-center gap-2 text-white/40 text-sm">
          <Clock className="w-4 h-4" />
          Generating your tech pack…
        </div>
      </header>

      <main className="flex-1 flex gap-0 overflow-hidden">

        {/* LEFT — Step pipeline + progress */}
        <div className="w-80 shrink-0 border-r border-white/5 flex flex-col p-6 gap-6 overflow-y-auto">
          {/* Progress ring */}
          <div className="flex flex-col items-center gap-3">
            <div className="relative w-24 h-24">
              <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
                <circle cx="48" cy="48" r="40" stroke="rgba(255,255,255,0.06)" strokeWidth="8" fill="none" />
                <circle
                  cx="48" cy="48" r="40"
                  stroke="url(#progressGrad)" strokeWidth="8" fill="none"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 40}`}
                  strokeDashoffset={`${2 * Math.PI * 40 * (1 - progress / 100)}`}
                  style={{ transition: "stroke-dashoffset 0.8s ease" }}
                />
                <defs>
                  <linearGradient id="progressGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#a78bfa" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                {status === "done"
                  ? <CheckCircle2 className="w-8 h-8 text-green-400" />
                  : status === "error"
                    ? <AlertCircle className="w-8 h-8 text-red-400" />
                    : <span className="text-xl font-bold text-white">{progress}%</span>
                }
              </div>
            </div>
            <p className="text-white/50 text-xs text-center">{currentStep}</p>
          </div>

          {/* Step list */}
          <div className="flex flex-col gap-1">
            {PIPELINE_STEPS.map((step, i) => {
              const done = i < currentStepIdx
              const active = i === currentStepIdx
              const pending = i > currentStepIdx
              return (
                <div key={step} className="flex items-center gap-2.5 py-1.5">
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
                    done ? "bg-green-500" : active ? "bg-violet-500" : "bg-white/10"
                  }`}>
                    {done
                      ? <CheckCircle2 className="w-3 h-3 text-white" />
                      : active
                        ? <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                        : null
                    }
                  </div>
                  <span className={`text-xs transition-colors duration-300 ${
                    done ? "text-white/50 line-through" : active ? "text-white font-semibold" : "text-white/20"
                  }`}>{step}</span>
                </div>
              )
            })}
          </div>

          {/* Error state */}
          {status === "error" && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
              <p className="text-red-300 text-xs leading-relaxed">{error}</p>
              <button
                onClick={() => navigate("/")}
                className="mt-3 text-xs text-white/50 hover:text-white flex items-center gap-1 transition-colors"
              >
                ← Try again
              </button>
            </div>
          )}

          {/* Done state */}
          {status === "done" && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
              <p className="text-green-300 text-sm font-semibold mb-1">Tech Pack Ready!</p>
              <p className="text-white/40 text-xs">Redirecting to editor…</p>
            </div>
          )}
        </div>

        {/* RIGHT — AI Reasoning Log */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-3 px-8 py-5 border-b border-white/5 shrink-0">
            <Brain className="w-5 h-5 text-violet-400" />
            <div>
              <h2 className="text-sm font-bold text-white">AI Reasoning Trace</h2>
              <p className="text-white/30 text-xs">Watch what each agent decides and why</p>
            </div>
          </div>

          {/* Log entries */}
          <div className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-3">
            {stepLog.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-violet-600/10 border border-violet-500/20 flex items-center justify-center mb-4">
                  <Brain className="w-6 h-6 text-violet-400/50" />
                </div>
                <p className="text-white/25 text-sm">Agents are initializing…</p>
                <p className="text-white/15 text-xs mt-1">Reasoning will appear here as each step runs</p>
              </div>
            ) : (
              stepLog.map((entry, i) => (
                <ReasoningCard
                  key={i}
                  entry={entry}
                  isLatest={i === stepLog.length - 1 && status === "running"}
                />
              ))
            )}
            <div ref={logEndRef} />
          </div>

          {/* Done CTA */}
          {status === "done" && (
            <div className="shrink-0 px-8 py-5 border-t border-white/5">
              <button
                onClick={() => navigate("/editor")}
                className="w-full flex items-center justify-center gap-3 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-bold rounded-2xl py-4 transition-all duration-300 hover:-translate-y-0.5"
              >
                <CheckCircle2 className="w-5 h-5" />
                View & Edit Tech Pack
                <ChevronRight className="w-5 h-5 opacity-60" />
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

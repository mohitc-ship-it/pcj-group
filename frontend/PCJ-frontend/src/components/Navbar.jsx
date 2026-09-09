import PageSelector from "./PageSelector"
import { Button } from "@/components/ui/button"

export default function Navbar({ page, onPageChange, onReset }) {
  return (
    <div className="h-14 flex items-center justify-between px-6 border-b bg-white shadow-sm">

      {/* LEFT */}
      <div className="flex items-center gap-4">
        <span className="text-lg font-semibold tracking-wide">
          PCJ Group
        </span>

        <PageSelector page={page} onChange={onPageChange} />
      </div>

      {/* RIGHT */}
      <div className="flex items-center gap-3">
        <Button
          variant="destructive"
          size="sm"
          onClick={onReset}
        >
          Reset Template
        </Button>

        <Button variant="outline" size="sm">
          Sign In
        </Button>

        <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-sm font-medium">
          U
        </div>
      </div>
    </div>
  )
}

import { Input } from "@/components/ui/input"

export default function TextField({ label, value, onChange }) {
  return (
    <div className="space-y-1.5 mb-4">
      <label className="text-xs font-bold text-white/80 tracking-wide">{label}</label>
      <Input 
        value={value} 
        onChange={e => onChange(e.target.value)} 
        className="bg-white/5 border-white/10 text-white placeholder-white/30 focus-visible:ring-violet-500"
      />
    </div>
  )
}

import { Input } from "@/components/ui/input"

export default function TextField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <Input value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

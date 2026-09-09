import { Input } from "@/components/ui/input"

export default function ColorField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <Input type="color" value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

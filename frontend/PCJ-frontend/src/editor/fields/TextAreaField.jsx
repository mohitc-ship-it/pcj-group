import { Textarea } from "@/components/ui/textarea"

export default function TextAreaField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <Textarea
        rows={4}
        value={value}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

import { ScrollArea } from "@/components/ui/scroll-area"
import FormRenderer from "./FormRenderer"

export default function PageEditor({ data, onChange, pageId, reloadPage }) {
  return (
    <ScrollArea className="h-full p-4">
      <FormRenderer
        data={data}
        onChange={onChange}
        pageId={pageId}
        reloadPage={reloadPage}
      />
    </ScrollArea>
  )
}

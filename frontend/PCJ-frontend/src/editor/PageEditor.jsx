import FormRenderer from "./FormRenderer"

export default function PageEditor({ data, onChange, pageId, reloadPage }) {
  return (
    <div className="h-full">
      <FormRenderer
        data={data}
        onChange={onChange}
        pageId={pageId}
        reloadPage={reloadPage}
      />
    </div>
  )
}

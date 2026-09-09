// import TextField from "./fields/TextField"
// import TextAreaField from "./fields/TextAreaField"
// import ImageField from "./fields/ImageField"
// import ColorField from "./fields/ColorField"
// import TableEditor from "./tables/TableEditor"

// export default function FormRenderer({ data, onChange }) {
//   function update(key, value) {
//     onChange({ ...data, [key]: value })
//   }

//   return (
//     <div className="space-y-6">
//       {Object.entries(data).map(([key, value]) => {

//         if (Array.isArray(value) && value.length && typeof value[0] === "object") {
//           return (
//             <TableEditor
//               key={key}
//               label={key}
//               value={value}
//               onChange={v => update(key, v)}
//             />
//           )
//         }

//         if (typeof value === "string" && value.startsWith("#")) {
//           return (
//             <ColorField
//               key={key}
//               label={key}
//               value={value}
//               onChange={v => update(key, v)}
//             />
//           )
//         }

//         if (typeof value === "string" && key.endsWith("_url")) {
//           return (
//             <ImageField
//               key={key}
//               label={key}
//               value={value}
//               onChange={v => update(key, v)}
//             />
//           )
//         }

//         if (typeof value === "string" && value.length > 120) {
//           return (
//             <TextAreaField
//               key={key}
//               label={key}
//               value={value}
//               onChange={v => update(key, v)}
//             />
//           )
//         }

//         if (typeof value === "string") {
//           return (
//             <TextField
//               key={key}
//               label={key}
//               value={value}
//               onChange={v => update(key, v)}
//             />
//           )
//         }

//         return null
//       })}
//     </div>
//   )
// }


import TextField from "./fields/TextField"
import TextAreaField from "./fields/TextAreaField"
import ImageField from "./fields/ImageField"
import ColorField from "./fields/ColorField"
import TableEditor from "./tables/TableEditor"
import DetailImageSelector from "./fields/DetailImageSelector"
import ColorSelector from "./fields/ColorSelector"
import ColorOptionSelector from "./fields/ColorOptionSelector"


export default function FormRenderer({ data, onChange, pageId, reloadPage }) {
  function update(key, value) {
    onChange({ ...data, [key]: value })
  }

  return (
    <div className="space-y-6">
      {Object.entries(data).map(([key, value]) => {

        if (Array.isArray(value) && value.length && typeof value[0] === "object") {
          return (
            <TableEditor
              key={key}
              label={key}
              value={value}
              onChange={v => update(key, v)}
            />
          )
        }

        // if (
        //   pageId === "page_2" &&
        //   key === "color_hex" &&
        //   Array.isArray(data.optional_colors)
        // ) {
        //   return (
        //     <ColorSelector
        //       key={key}
        //       label={key}
        //       value={value}
        //       options={data.optional_colors}
        //       pageId={pageId}
        //       fieldKey={key}
        //       onUpdated={reloadPage}
        //     />
        //   )
        // }
        if (
          pageId === "page_2" &&
          key === "color_hex" &&
          Array.isArray(data.optional_colors)
        ) {
          return (
            <ColorOptionSelector
              key={key}
              current={{
                color_hex: data.color_hex,
                pantone_tcx: data.pantone_tcx,
                color_name: data.color_name,
              }}
              options={data.optional_colors}
              pageId={pageId}
              onUpdated={reloadPage}
            />
          )
        }
        

        // if (typeof value === "string" && value.startsWith("#")) {
        //   return (
        //     <ColorField
        //       key={key}
        //       label={key}
        //       value={value}
        //       onChange={v => update(key, v)}
        //     />
        //   )
        // }
     
      

        if (
          pageId === "page_2" &&
          key.startsWith("detail_image_") &&
          key.endsWith("_url")
        ) {
          return (
            <DetailImageSelector
              key={key}
              label={key}
              value={value}
              options={data.optional_image_urls || []}
              pageId={pageId}
              fieldKey={key}
              onUpdated={reloadPage}
            />
          )
        }

        if (typeof value === "string" && (key.endsWith("_url") || value.includes("/assets"))) {
          return (
            <ImageField
              key={key}
              label={key}
              value={value}
              pageId={pageId}
              fieldPath={key}
              onUpdated={reloadPage}
            />
          )
        }
        
        if (typeof value === "string" && value.length > 120) {
          return (
            <TextAreaField
              key={key}
              label={key}
              value={value}
              onChange={v => update(key, v)}
            />
          )
        }

        if (typeof value === "string") {
          return (
            <TextField
              key={key}
              label={key}
              value={value}
              onChange={v => update(key, v)}
            />
          )
        }

        return null
      })}
    </div>
  )
}

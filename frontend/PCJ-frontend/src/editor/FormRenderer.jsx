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
import MultiColorEditor from "./fields/MultiColorEditor"
import SketchEditor from "./fields/SketchEditor"
import MeasurementEditor from "./fields/MeasurementEditor"
import WhyButton from "./fields/WhyButton"


export default function FormRenderer({ data, onChange, pageId, reloadPage }) {
  function update(key, value) {
    let finalValue = value
    if (pageId === "header" && typeof value === "string") {
      finalValue = value.toUpperCase()
    }
    onChange({ ...data, [key]: finalValue })
  }

  return (
    <div className="space-y-6">
      {Object.entries(data).map(([key, value]) => {

        if (
          pageId === "page_2" &&
          key === "optional_colors" &&
          Array.isArray(value)
        ) {
          return (
            <MultiColorEditor
              key={key}
              colors={value}
              pageId={pageId}
              onUpdated={reloadPage}
            />
          )
        }

        if (Array.isArray(value) && value.length && typeof value[0] === "object") {
          return (
            <div key={key} className="space-y-1">
              <div className="flex items-center gap-2">
                <WhyButton pageId={pageId} fieldKey={key} />
              </div>
              <TableEditor
                label={key}
                value={value}
                onChange={v => update(key, v)}
                pageId={pageId}
              />
            </div>
          )
        }

        // Feature 4 — Technical sketch: show SketchEditor for image-to-image editing
        if (pageId === "page_3" && key === "technical_sketch_img") {
          return (
            <SketchEditor
              key={key}
              value={value}
              onUpdated={reloadPage}
            />
          )
        }

        // Measurement diagram: show MeasurementEditor for image-to-image editing
        if ((pageId === "page_6" || pageId === "page_10") && key === "measurement_image_url") {
          return (
            <MeasurementEditor
              key={key}
              value={value}
              onUpdated={reloadPage}
            />
          )
        }

        // Hide internal fields (reasoning, confidence, options)
        if (key.startsWith("_")) return null

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

        
        // Hide color_hex and pantone_tcx at root since we edit them via optional_colors
        if (pageId === "page_2" && (key === "color_hex" || key === "pantone_tcx" || key === "color_name")) {
          return null
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

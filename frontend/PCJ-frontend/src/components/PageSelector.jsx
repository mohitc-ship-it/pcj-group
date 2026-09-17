// export default function PageSelector({ page, onChange }) {
//   const pages = [
//     "page_1","page_2","page_3","page_4",
//     "page_5","page_6","page_7","page_8","page_9"
//   ]

//   return (
//     <select
//       className="border p-2 m-2 w-64"
//       value={page}
//       onChange={e => onChange(e.target.value)}
//     >
//       {pages.map(p => (
//         <option key={p} value={p}>
//           {p.toUpperCase()}
//         </option>
//       ))}
//     </select>
//   )
// }

export default function PageSelector({ page, onChange }) {
  const pages = [
    { id: "page_1", label: "Cover" },
    { id: "page_2", label: "3D CAD" },
    { id: "page_3", label: "Technical Sketch" },
    { id: "page_4", label: "Accessories" },
    { id: "page_5", label: "Construction" },
    { id: "page_6", label: "Measurements" },
    { id: "page_7", label: "Fabric & Quality Standards" },
    { id: "page_8", label: "Reference Image" },
    { id: "page_9", label: "Wash & Care" },
  ]

  return (
    <select
      className="border rounded px-2 py-1 text-sm"
      value={page}
      onChange={e => onChange(e.target.value)}
    >
      {pages.map(p => (
        <option key={p.id} value={p.id}>
          {p.label}
        </option>
      ))}
    </select>
  )
}

// export default function PreviewPane({ html }) {
//   return (
//     <iframe
//       title="preview"
//       className="w-full h-full border-l"
//       srcDoc={html}
//     />
//   )
// }

export default function PreviewPane({ html }) {
  const PAGE_WIDTH = 1240   // must match @page width
  const PAGE_HEIGHT = 820   // must match @page height

  return (
    <div className="w-full h-full flex items-center justify-center bg-white overflow-hidden border-l">
      <div
        style={{
          width: PAGE_WIDTH,
          height: PAGE_HEIGHT,
          transform: "scale(0.54)",
          transformOrigin: "top center",
          backgroundColor : "white",
          alignItems : "center",
          justifyContent : "center",
          paddingTop : "30px",
          display : "flex"
        }}
      >
        <iframe
          title="preview"
          srcDoc={html}
          style={{
            width: PAGE_WIDTH,
            height: PAGE_HEIGHT,
            border: "none",
            marginTop : "220px"
          }}
        />
      </div>
    </div>
  )
}





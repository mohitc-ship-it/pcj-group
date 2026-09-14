import { Routes, Route, Navigate } from "react-router-dom"
import UploadPage from "./pages/UploadPage"
import GeneratingPage from "./pages/GeneratingPage"
import EditorPage from "./pages/EditorPage"

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/generating" element={<GeneratingPage />} />
      <Route path="/editor" element={<EditorPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

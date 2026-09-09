const API_BASE_URL = "http://localhost:8000"

export async function fetchPageData(pageId) {
  const res = await fetch(`${API_BASE_URL}/api/draft/${pageId}`)
  if (!res.ok) {
    throw new Error("Failed to fetch page data")
  }
  return res.json()
}

export async function renderPreview(pageId, data) {
  const res = await fetch(`${API_BASE_URL}/api/preview/${pageId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    throw new Error("Failed to render preview")
  }

  return res.text()
}

export async function resetDraft() {
  const res = await fetch(`${API_BASE_URL}/api/reset-draft`, {
    method: "POST",
  })

  if (!res.ok) {
    throw new Error("Failed to reset draft")
  }

  return res.json()
}



export async function uploadImage(file) {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch(`${API_BASE_URL}/api/upload-image`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    throw new Error("Upload failed")
  }

  return res.json()
}

export async function updateImageField(payload) {
  const res = await fetch(`${API_BASE_URL}/api/update-image-field`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    throw new Error("Update failed")
  }

  return res.json()
}

export async function updateMultipleFields(payload) {
  const res = await fetch(`${API_BASE_URL}/api/update-multiple-fields`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    throw new Error("Update failed")
  }

  return res.json()
}

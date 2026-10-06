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

export async function saveDraft(pageId, data) {
  const res = await fetch(`${API_BASE_URL}/api/save-draft/${pageId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error("Failed to save draft")
  return res.json()
}

export async function manualCrop(payload) {
  const res = await fetch(`${API_BASE_URL}/api/manual-crop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error("Crop failed")
  return res.json()
}

export async function regenerateSketch(instruction) {
  const res = await fetch(`${API_BASE_URL}/api/regenerate-sketch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  })
  if (!res.ok) throw new Error("Sketch regeneration failed")
  return res.json()
}

export async function regenerateTableRow(payload) {
  const res = await fetch(`${API_BASE_URL}/api/regenerate-table-row`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error("Row regeneration failed")
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

// --------------------------------------------------
// Generation Flow
// --------------------------------------------------

/**
 * Upload 2+ images + context and start a background generation job.
 * @param {File[]} imageFiles - array of File objects (min 2, first = front, second = back)
 * @param {string} contextText - brand/collection/season/fabric/size context
 * Returns { job_id, status, image_count }
 */
export async function triggerGeneration(imageFiles, contextText, sampleSize = "", brandLogoFile = null, highAccuracy = false) {
  const formData = new FormData()
  imageFiles.forEach((file) => formData.append("images", file))
  formData.append("context", contextText)
  formData.append("high_accuracy", highAccuracy ? "true" : "false")

  if (sampleSize) {
    formData.append("sample_size", sampleSize)
  }

  if (brandLogoFile) {
    formData.append("brand_logo", brandLogoFile)
  }

  const res = await fetch(`${API_BASE_URL}/api/generate`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }))
    throw new Error(err.error || "Generation failed to start")
  }

  return res.json() // { job_id, status, image_count }
}

/**
 * Poll generation status for a given job_id.
 * Returns { status, progress, current_step, error }
 */
export async function getGenerationStatus(jobId) {
  const res = await fetch(`${API_BASE_URL}/api/generate-status/${jobId}`)
  if (!res.ok) {
    throw new Error("Failed to fetch generation status")
  }
  return res.json()
}

/**
 * Download the generated Tech_Pack.pdf.
 */
export function downloadPdf() {
  window.open(`${API_BASE_URL}/api/download-pdf?t=${Date.now()}`, "_blank")
}

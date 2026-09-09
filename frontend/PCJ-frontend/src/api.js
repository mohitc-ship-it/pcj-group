export async function fetchPageData(page) {
    const res = await fetch(`/api/draft/${page}`);
    return res.json();
  }
  
  export async function renderPreview(page, data) {
    const res = await fetch(`/api/preview/${page}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
  
    return res.text();
  }
  
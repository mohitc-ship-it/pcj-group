import streamlit as st
import tempfile
import os
import shutil
import base64
from datetime import datetime
from main import generate_techpack
import streamlit.components.v1 as components


# -----------------------------
# Configuration
# -----------------------------

st.set_page_config(
    page_title="Swanky Tech Pack Generator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

LOGO_PATH = "assets/brand_logo.png"
PUBLIC_UPLOAD_DIR = "assets"


# -----------------------------
# Helpers
# -----------------------------

def save_images_to_public(uploaded_images):
    """
    Saves uploaded images to public/uploads and returns file paths
    """
    os.makedirs(PUBLIC_UPLOAD_DIR, exist_ok=True)
    saved_paths = []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for idx, uploaded_file in enumerate(uploaded_images):
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        safe_name = uploaded_file.name.replace(" ", "_")
        filename = f"{timestamp}_{idx}_{safe_name}"
        dest_path = os.path.join(PUBLIC_UPLOAD_DIR, filename)

        with open(dest_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        saved_paths.append(dest_path)

    return saved_paths


# -----------------------------
# Styling
# -----------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body { font-family: 'Inter', sans-serif; }

.main {
    padding: 2rem;
    background: linear-gradient(135deg, #f8f9ff 0%, #fff5f7 100%);
}

.section {
    padding: 28px;
    border-radius: 20px;
    background: white;
    border: 1px solid rgba(124, 58, 237, 0.08);
    box-shadow: 0 8px 32px rgba(124, 58, 237, 0.06);
}

.stButton > button {
    background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
    color: white;
    border-radius: 14px;
    padding: 14px 32px;
    font-weight: 600;
    width: 100%;
}

.file-badge {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    padding: 6px 16px;
    border-radius: 20px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Layout
# -----------------------------

col1, col2 = st.columns([2, 3], gap="large")

# -----------------------------
# Left Column (Inputs)
# -----------------------------

with col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=150)

    st.markdown("# 🎨 Swanky Tech Pack Studio")
    st.markdown(
        "<p>Upload garment images and generate professional tech packs.</p>",
        unsafe_allow_html=True
    )

    st.markdown("## 📸 Upload Garment Images")

    uploaded_images = st.file_uploader(
        "Upload images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_images:
        st.markdown(
            f"<span class='file-badge'>✓ {len(uploaded_images)} image(s) uploaded</span>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    st.markdown("## 📝 Specification Context")

    input_context = st.text_area(
        "Enter context",
        height=220,
        placeholder="Fabric, fit, measurements, trims, construction notes...",
        label_visibility="collapsed"
    )

    st.markdown("---")

    generate_btn = st.button("🚀 Generate Tech Pack PDF", type="primary")


# -----------------------------
# Right Column (Output)
# -----------------------------

with col2:
    preview_container = st.container()
    status_container = st.container()


# -----------------------------
# Generation Logic
# -----------------------------

if generate_btn:
    if not uploaded_images:
        st.warning("⚠️ Please upload at least one garment image.")
    else:
        try:
            with st.spinner("📤 Saving images to public folder..."):
                saved_paths = save_images_to_public(uploaded_images)

            with status_container:
                st.info("⚙️ Analyzing images and generating tech pack...")

            with st.spinner("🎨 Creating tech pack..."):
                pdf_path = generate_techpack(saved_paths, input_context,True)

            # pdf_path = "Tech_Pack.pdf"
            if pdf_path and os.path.exists(pdf_path):
                with status_container:
                    st.success("✅ Tech pack generated successfully!")
                

                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                with preview_container:
                    st.markdown("## 📄 Your Tech Pack")

                    st.download_button(
                        label="⬇️ Download Tech Pack PDF",
                        data=pdf_bytes,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )

                    try:
                        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

                        components.html(
                            f"""
                            <html>
                                <head>
                                    <style>
                                        body {{
                                            margin: 0;
                                            background: #f9fafb;
                                        }}
                                        .pdf-wrapper {{
                                            width: 100%;
                                            height: 90vh;
                                            padding: 12px;
                                            box-sizing: border-box;
                                        }}
                                        iframe {{
                                            width: 100%;
                                            height: 100%;
                                            border: none;
                                            border-radius: 12px;
                                            background: white;
                                        }}
                                    </style>
                                </head>
                                <body>
                                    <div class="pdf-wrapper">
                                        <iframe
                                            src="data:application/pdf;base64,{b64_pdf}#toolbar=1&navpanes=0&scrollbar=1">
                                        </iframe>
                                    </div>
                                </body>
                            </html>
                            """,
                            height=900,
                        )

                    except Exception:
                        st.info(f"PDF saved at: {os.path.abspath(pdf_path)}")

            else:
                st.error("❌ PDF generation failed.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# -----------------------------
# Footer
# -----------------------------

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#6b7280;'>Built with care ✨ — Swanky Tech Pack Generator</div>",
    unsafe_allow_html=True
)

# import json
# from pathlib import Path
# from jinja2 import Environment, FileSystemLoader
# from weasyprint import HTML
# from renderers.accessories_renderer import normalize_accessories

# BASE_DIR = Path(__file__).resolve().parent

# env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))


# #global_data
# with open(BASE_DIR / "data" / "master.json") as f:
#     data = json.load(f)


# #page 1
# # template = env.get_template("intro_page.html")
# # with open(BASE_DIR / "data" / "intro_page.json") as f:
# #     data = json.load(f)

# #page 2
# # template = env.get_template("technical_sketch_page.html")
# # with open(BASE_DIR / "data" / "technical_sketch_page.json") as f:
# #     data = json.load(f)

# #page 3
# # template = env.get_template("3d_cad_design_page.html")
# # with open(BASE_DIR / "data" / "3d_cad_design_page.json") as f:
# #     data = json.load(f)

# #page 4
# # template = env.get_template("accessories_page.html")
# # with open(BASE_DIR / "data" / "accessories_page.json") as f:
# #     data = json.load(f)


# #page 5
# # template = env.get_template("product_construction.html")
# # with open(BASE_DIR / "data" / "product_construction.json") as f:
# #     data = json.load(f)

# #page 6
# # template = env.get_template("measurements.html")
# # with open(BASE_DIR / "data" / "measurements.json") as f:
# #     data = json.load(f)

# #page 7
# # template = env.get_template("fabrics_quality_standards.html")
# # with open(BASE_DIR / "data" / "fabrics_quality_standards.json") as f:
# #     data = json.load(f)

# #page 8
# # template = env.get_template("size_chart_page.html")
# # with open(BASE_DIR / "data" / "size_chart_page.json") as f:
# #     data = json.load(f)

# #page 9
# # template = env.get_template("wash_and_care_label.html")
# # with open(BASE_DIR / "data" / "wash_and_care_label.json") as f:
# #     data = json.load(f)

# html = template.render(**data)

# HTML(
#     string=html,
#     base_url=str(BASE_DIR)
# ).write_pdf(
#     "Accessories.pdf",
#     presentational_hints=True  # VERY IMPORTANT
#)


import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from pypdf import PdfWriter, PdfReader


def generatePdf():
    BASE_DIR = Path(__file__).resolve().parent
    TEMPLATES_DIR = BASE_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    TEMP_DIR = BASE_DIR / "temp"

    TEMP_DIR.mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # --------------------------------------------------
    # Load MASTER DATA
    # --------------------------------------------------
    with open(DATA_DIR / "master_filled.json") as f:
        data = json.load(f)

    # --------------------------------------------------
    # Page order
    # --------------------------------------------------
    PAGES = [
        ("intro_page.html", "page_1.pdf"),
        ("3d_cad_design_page.html", "page_3.pdf"),
        ("technical_sketch_page.html", "page_2.pdf"),
        ("accessories_page.html", "page_4.pdf"),
        ("product_construction.html", "page_5.pdf"),
        ("measurements.html", "page_6.pdf"),
        ("fabrics_quality_standards.html", "page_7.pdf"),
        ("size_chart_page.html", "page_8.pdf"),
        ("wash_and_care_label.html", "page_9.pdf"),
    ]

    # PAGES = [
        
    #     ("technical_sketch_page.html", "page_2.pdf"),
    #     ("measurements.html", "page_6.pdf")
  
    # ]

    generated_pdfs = []

    # --------------------------------------------------
    # STEP 1: Generate individual PDFs
    # --------------------------------------------------
    for template_name, output_name in PAGES:
        template = env.get_template(template_name)
        html = template.render(**data)

        output_path = TEMP_DIR / output_name

        HTML(
            string=html,
            base_url=str(BASE_DIR)
        ).write_pdf(
            output_path,
            presentational_hints=True
        )

        generated_pdfs.append(output_path)
        print(f"✅ Generated {output_name}")

    # --------------------------------------------------
    # STEP 2: Merge PDFs using PdfWriter (pypdf 5.x)
    # --------------------------------------------------
    writer = PdfWriter()

    for pdf_path in generated_pdfs:
        reader = PdfReader(str(pdf_path))
        # Only take the first page — overflow pages are unwanted spillover
        if reader.pages:
            writer.add_page(reader.pages[0])

    final_pdf_path = BASE_DIR / "Tech_Pack.pdf"

    with open(final_pdf_path, "wb") as f:
        writer.write(f)

    print(f"\n🎉 Final PDF created: {final_pdf_path}")
    return final_pdf_path

# generatePdf()
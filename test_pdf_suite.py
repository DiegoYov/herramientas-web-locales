import asyncio
import os
import pymupdf
from pdf_tools_service import (
    merge_pdfs, split_pdf, compress_pdf, pdf_to_images,
    images_to_pdf, rotate_pdf, add_watermark, protect_pdf, pdf_to_text
)

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_suite")
os.makedirs(TEST_DIR, exist_ok=True)

def create_dummy_pdf(filename: str, pages_count: int = 3) -> str:
    path = os.path.join(TEST_DIR, filename)
    doc = pymupdf.open()
    for i in range(pages_count):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), f"Página {i+1} de {filename}", fontsize=18)
    doc.save(path)
    doc.close()
    return path

async def run_tests():
    pdf1 = create_dummy_pdf("doc1.pdf", 2)
    pdf2 = create_dummy_pdf("doc2.pdf", 2)

    # 1. Merge
    merged = os.path.join(TEST_DIR, "merged.pdf")
    await merge_pdfs([pdf1, pdf2], merged)
    assert os.path.exists(merged)
    print("[OK] Unir PDFs OK")

    # 2. Split
    split_out = os.path.join(TEST_DIR, "split.pdf")
    await split_pdf(merged, "1,3", split_out)
    assert os.path.exists(split_out)
    print("[OK] Dividir PDF OK")

    # 3. Compress
    comp_out = os.path.join(TEST_DIR, "compressed.pdf")
    res_comp = await compress_pdf(merged, comp_out)
    assert os.path.exists(comp_out)
    print("[OK] Comprimir PDF OK:", res_comp)

    # 4. PDF to Images
    zip_out = os.path.join(TEST_DIR, "images.zip")
    await pdf_to_images(merged, zip_out)
    assert os.path.exists(zip_out)
    print("[OK] PDF a Imagenes (ZIP) OK")

    # 5. Rotate
    rot_out = os.path.join(TEST_DIR, "rotated.pdf")
    await rotate_pdf(pdf1, 90, rot_out)
    assert os.path.exists(rot_out)
    print("[OK] Rotar PDF OK")

    # 6. Watermark
    wm_out = os.path.join(TEST_DIR, "watermarked.pdf")
    await add_watermark(pdf1, "BORRADOR", wm_out)
    assert os.path.exists(wm_out)
    print("[OK] Marca de Agua OK")

    # 7. Protect
    prot_out = os.path.join(TEST_DIR, "protected.pdf")
    await protect_pdf(pdf1, "1234", prot_out)
    assert os.path.exists(prot_out)
    print("[OK] Proteger PDF OK")

    # 8. PDF to Text
    txt_out = os.path.join(TEST_DIR, "text.txt")
    await pdf_to_text(pdf1, txt_out)
    assert os.path.exists(txt_out)
    print("[OK] PDF a Texto OK")

    print("\n¡TODAS LAS PRUEBAS DE LA SUITE PDF PASARON CORRECTAMENTE!")

if __name__ == "__main__":
    asyncio.run(run_tests())

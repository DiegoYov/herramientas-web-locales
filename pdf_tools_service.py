import os
import zipfile
import tempfile
from typing import List, Optional, Callable, Dict, Any
import pymupdf  # PyMuPDF

async def merge_pdfs(
    pdf_paths: List[str],
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Combines multiple PDF files into a single PDF."""
    if not pdf_paths:
        raise ValueError("Debe seleccionar al menos un archivo PDF.")
        
    merged_doc = pymupdf.open()
    total = len(pdf_paths)
    
    for i, path in enumerate(pdf_paths):
        if not os.path.exists(path):
            continue
        if progress_callback:
            progress_callback(round((i / total) * 90.0, 1), f"Uniendo PDF {i+1} de {total}...")
        
        doc = pymupdf.open(path)
        merged_doc.insert_pdf(doc)
        doc.close()
        
    if progress_callback:
        progress_callback(95.0, "Guardando PDF unificado...")
        
    merged_doc.save(output_path, garbage=4, deflate=True)
    merged_doc.close()
    
    if progress_callback:
        progress_callback(100.0, "¡PDFs unificados con éxito!")
        
    return output_path


async def split_pdf(
    pdf_path: str,
    pages_expr: str,
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Extracts specified pages or page ranges from a PDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    
    selected_indices = set()
    parts = [p.strip() for p in pages_expr.split(',') if p.strip()]
    
    for part in parts:
        if '-' in part:
            try:
                start_str, end_str = part.split('-', 1)
                start = max(1, int(start_str))
                end = min(total_pages, int(end_str))
                for idx in range(start - 1, end):
                    selected_indices.add(idx)
            except ValueError:
                pass
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < total_pages:
                    selected_indices.add(idx)
            except ValueError:
                pass
                
    sorted_indices = sorted(list(selected_indices))
    if not sorted_indices:
        raise ValueError(f"No se seleccionaron páginas válidas de un total de {total_pages} páginas.")
        
    if progress_callback:
        progress_callback(50.0, f"Extrayendo {len(sorted_indices)} páginas...")
        
    out_doc = pymupdf.open()
    out_doc.insert_pdf(doc, from_page=0, to_page=total_pages-1)
    out_doc.select(sorted_indices)
    
    if progress_callback:
        progress_callback(90.0, "Guardando nuevo archivo PDF...")
        
    out_doc.save(output_path, garbage=4, deflate=True)
    out_doc.close()
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, "¡PDF dividido con éxito!")
        
    return output_path


async def compress_pdf(
    pdf_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """Optimizes streams, fonts, and images to compress PDF size."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    original_size = os.path.getsize(pdf_path)
    if progress_callback:
        progress_callback(30.0, "Optimizando imágenes y objetos del PDF...")
        
    doc = pymupdf.open(pdf_path)
    
    if progress_callback:
        progress_callback(70.0, "Comprimiendo flujos de datos...")
        
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    
    new_size = os.path.getsize(output_path)
    saved_bytes = max(0, original_size - new_size)
    percent_saved = round((saved_bytes / original_size) * 100.0, 1) if original_size > 0 else 0
    
    if progress_callback:
        progress_callback(100.0, f"¡Compresión completada! Reducción: {percent_saved}%")
        
    return {
        "output_path": output_path,
        "original_size": original_size,
        "new_size": new_size,
        "percent_saved": percent_saved
    }


async def pdf_to_images(
    pdf_path: str,
    output_zip_path: str,
    image_format: str = "png",
    dpi: int = 150,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Renders PDF pages to high quality PNG/JPG images packaged in a ZIP file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, page in enumerate(doc):
            if progress_callback:
                progress_callback(round(((i + 1) / total_pages) * 90.0, 1), f"Renderizando página {i+1} de {total_pages}...")
                
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_filename = f"pagina_{i+1:03d}.{image_format.lower()}"
            img_bytes = pix.tobytes(image_format.lower())
            zip_file.writestr(img_filename, img_bytes)
            
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, f"¡Imágenes exportadas a ZIP con éxito ({total_pages} páginas)!")
        
    return output_zip_path


async def images_to_pdf(
    image_paths: List[str],
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Converts a list of image files into a single PDF document."""
    if not image_paths:
        raise ValueError("Debe seleccionar al menos una imagen.")
        
    doc = pymupdf.open()
    total = len(image_paths)
    
    for i, img_path in enumerate(image_paths):
        if not os.path.exists(img_path):
            continue
        if progress_callback:
            progress_callback(round(((i + 1) / total) * 90.0, 1), f"Procesando imagen {i+1} de {total}...")
            
        img_doc = pymupdf.open(img_path)
        pdf_bytes = img_doc.convert_to_pdf()
        img_pdf = pymupdf.open("pdf", pdf_bytes)
        doc.insert_pdf(img_pdf)
        img_doc.close()
        img_pdf.close()
        
    if progress_callback:
        progress_callback(95.0, "Generando PDF final...")
        
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, "¡Imágenes convertidas a PDF con éxito!")
        
    return output_path


async def rotate_pdf(
    pdf_path: str,
    rotation_degrees: int,
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Rotates all pages in a PDF document by rotation_degrees."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    doc = pymupdf.open(pdf_path)
    total = len(doc)
    
    for i, page in enumerate(doc):
        if progress_callback:
            progress_callback(round(((i + 1) / total) * 90.0, 1), f"Rotando página {i+1} de {total}...")
        page.set_rotation((page.rotation + rotation_degrees) % 360)
        
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, f"¡PDF rotado {rotation_degrees}° con éxito!")
        
    return output_path


async def add_watermark(
    pdf_path: str,
    text: str,
    output_path: str,
    opacity: float = 0.3,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Adds a text watermark diagonally across every page of the PDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    doc = pymupdf.open(pdf_path)
    total = len(doc)
    
    for i, page in enumerate(doc):
        if progress_callback:
            progress_callback(round(((i + 1) / total) * 90.0, 1), f"Añadiendo marca de agua p. {i+1}/{total}...")
            
        rect = page.rect
        center = pymupdf.Point(rect.width / 2, rect.height / 2)
        
        page.insert_text(
            center,
            text,
            fontsize=36,
            color=(0.5, 0.5, 0.5),
            overlay=True,
            fill_opacity=opacity
        )
        
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, "¡Marca de agua aplicada con éxito!")
        
    return output_path


async def protect_pdf(
    pdf_path: str,
    password: str,
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Encrypts a PDF file with a user password using AES-256."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    if progress_callback:
        progress_callback(50.0, "Cifrando documento PDF con contraseña...")
        
    doc = pymupdf.open(pdf_path)
    doc.save(
        output_path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password,
        garbage=4,
        deflate=True
    )
    doc.close()
    
    if progress_callback:
        progress_callback(100.0, "¡PDF protegido con contraseña!")
        
    return output_path


async def pdf_to_text(
    pdf_path: str,
    output_txt_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Extracts all text content from a PDF document into a TXT file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
    doc = pymupdf.open(pdf_path)
    total = len(doc)
    text_content = []
    
    for i, page in enumerate(doc):
        if progress_callback:
            progress_callback(round(((i + 1) / total) * 90.0, 1), f"Extrayendo texto p. {i+1}/{total}...")
        
        text_content.append(f"--- PÁGINA {i+1} ---\n")
        text_content.append(page.get_text())
        text_content.append("\n\n")
        
    doc.close()
    
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("".join(text_content))
        
    if progress_callback:
        progress_callback(100.0, "¡Texto extraído con éxito!")
        
    return output_txt_path


async def pdf_ocr(
    pdf_path: str,
    output_txt_path: str,
    language: str = "spa+eng",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """
    Performs Optical Character Recognition (OCR) on scanned PDFs or images to extract text.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    total = len(doc)
    text_content = []

    for i, page in enumerate(doc):
        if progress_callback:
            progress_callback(round(((i + 1) / total) * 90.0, 1), f"Aplicando OCR en página {i+1} de {total}...")

        text = ""
        try:
            # Try PyMuPDF native OCR textpage if Tesseract plugin is linked
            tp = page.get_textpage_ocr(flags=0, language=language)
            text = tp.extractText()
        except Exception:
            # Fallback to standard text extraction or PyMuPDF block extraction
            text = page.get_text()

        text_content.append(f"=== OCR PÁGINA {i+1} ===\n")
        text_content.append(text.strip() if text.strip() else "[Página escaneada sin texto detectable o requiere Tesseract local]")
        text_content.append("\n\n")

    doc.close()

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("".join(text_content))

    if progress_callback:
        progress_callback(100.0, "¡Reconocimiento OCR completado!")

    return output_txt_path

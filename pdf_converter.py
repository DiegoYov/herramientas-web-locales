import os
import uuid
import html
from typing import Optional, Callable, Dict, Any
import pymupdf  # PyMuPDF
from ebooklib import epub

async def convert_pdf_to_epub(
    pdf_path: str,
    output_epub_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    include_images: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Converts a PDF file into an EPUB ebook using PyMuPDF and ebooklib.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

    if progress_callback:
        progress_callback(5.0, "Abriendo archivo PDF...")

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    
    if total_pages == 0:
        raise ValueError("El archivo PDF está vacío o no tiene páginas.")

    meta = doc.metadata or {}
    book_title = title.strip() if title and title.strip() else meta.get("title") or os.path.splitext(os.path.basename(pdf_path))[0]
    book_author = author.strip() if author and author.strip() else meta.get("author") or "Autor Desconocido"

    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid.uuid4()}")
    book.set_title(book_title)
    book.set_language("es")
    book.add_author(book_author)

    # Standard EPUB CSS style
    style_content = '''
    body {
        font-family: Georgia, serif;
        margin: 5%;
        line-height: 1.6;
        color: #111111;
    }
    h1, h2, h3 {
        font-family: sans-serif;
        text-align: center;
        margin-top: 1.5em;
        margin-bottom: 0.8em;
    }
    p {
        text-indent: 1.5em;
        margin-bottom: 0.5em;
        text-align: justify;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
    }
    .page-num {
        text-align: center;
        font-size: 0.8em;
        color: #777777;
        margin-top: 2em;
        margin-bottom: 1em;
    }
    '''
    css_item = epub.EpubItem(
        uid="style_css",
        file_name="style/style.css",
        media_type="text/css",
        content=style_content
    )
    book.add_item(css_item)

    chapters = []
    toc_links = []
    images_count = 0

    pages_per_chapter = 10 if total_pages > 30 else 5 if total_pages > 10 else 1
    current_chapter_pages = []
    chapter_num = 1

    for page_idx in range(total_pages):
        page = doc[page_idx]
        percent = 10.0 + ((page_idx + 1) / total_pages) * 75.0
        if progress_callback:
            progress_callback(round(percent, 1), f"Procesando página {page_idx + 1} de {total_pages}...")

        blocks = page.get_text("blocks")
        page_html = [f'<div class="page" id="page_{page_idx + 1}">']

        for b in blocks:
            text = b[4].strip()
            if not text:
                continue
            
            lines = text.split('\n')
            clean_text = "<br/>".join([html.escape(l) for l in lines])
            
            if len(text) < 60 and not text.endswith('.'):
                page_html.append(f'<h2>{clean_text}</h2>')
            else:
                page_html.append(f'<p>{clean_text}</p>')

        if include_images:
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                if base_image:
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    image_filename = f"img_{page_idx + 1}_{xref}.{image_ext}"
                    media_type = f"image/{image_ext}" if image_ext != "jpg" else "image/jpeg"

                    img_item = epub.EpubItem(
                        uid=f"img_{images_count}",
                        file_name=f"images/{image_filename}",
                        media_type=media_type,
                        content=image_bytes
                    )
                    book.add_item(img_item)
                    images_count += 1
                    page_html.append(f'<img src="images/{image_filename}" alt="Imagen p. {page_idx+1}"/>')

        page_html.append(f'<div class="page-num">- {page_idx + 1} -</div>')
        page_html.append('</div>')

        current_chapter_pages.append("\n".join(page_html))

        if len(current_chapter_pages) >= pages_per_chapter or page_idx == total_pages - 1:
            ch_title = f"Capítulo {chapter_num}" if total_pages > 5 else f"Sección {chapter_num}"
            ch_filename = f"chap_{chapter_num}.xhtml"
            
            full_html = f'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="es">
<head>
    <meta charset="utf-8"/>
    <title>{html.escape(book_title)} - {html.escape(ch_title)}</title>
    <link rel="stylesheet" type="text/css" href="style/style.css"/>
</head>
<body>
    <h1>{html.escape(ch_title)}</h1>
    {"<hr/>".join(current_chapter_pages)}
</body>
</html>'''

            chapter_item = epub.EpubHtml(
                title=ch_title,
                file_name=ch_filename,
                lang="es"
            )
            chapter_item.set_content(full_html.encode('utf-8'))
            chapter_item.add_item(css_item)
            book.add_item(chapter_item)
            chapters.append(chapter_item)
            toc_links.append(chapter_item)

            current_chapter_pages = []
            chapter_num += 1

    if progress_callback:
        progress_callback(90.0, "Generando estructura EPUB...")

    book.toc = tuple(toc_links)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    if progress_callback:
        progress_callback(95.0, "Escribiendo archivo final .epub...")

    doc.close()
    epub.write_epub(output_epub_path, book)

    if progress_callback:
        progress_callback(100.0, "¡Conversión a EPUB completada con éxito!")

    return {
        "output_path": output_epub_path,
        "filename": os.path.basename(output_epub_path),
        "title": book_title,
        "author": book_author,
        "total_pages": total_pages,
        "chapters_count": len(chapters),
        "images_count": images_count
    }

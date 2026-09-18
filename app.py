import os
import shutil
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ffmpeg_service import get_video_info, merge_videos
from pdf_converter import convert_pdf_to_epub
import pdf_tools_service as pdf_tools
import video_tools_service as video_tools

app = FastAPI(title="Herramientas Web Locales - Suite Vídeo & PDF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

tasks_db: Dict[str, Dict[str, Any]] = {}


class PathRequest(BaseModel):
    paths: List[str]


class MergeRequest(BaseModel):
    files: List[str]
    target_resolution: Optional[str] = "1080p"
    preset: Optional[str] = "fast"
    output_filename: Optional[str] = None


class VideoTrimRequest(BaseModel):
    file_id_or_path: str
    start_time: str = "0"
    end_time: str = "10"
    output_filename: Optional[str] = None


class VideoVolumeRequest(BaseModel):
    file_id_or_path: str
    volume_factor: float = 1.0  # 0.0 for mute, 2.0 for 200%
    output_filename: Optional[str] = None


class VideoSpeedRequest(BaseModel):
    file_id_or_path: str
    speed_factor: float = 1.0  # 0.5, 1.5, 2.0
    output_filename: Optional[str] = None


class VideoExtractAudioRequest(BaseModel):
    file_id_or_path: str
    audio_format: str = "mp3"  # mp3, wav
    output_filename: Optional[str] = None


class VideoRotateRequest(BaseModel):
    file_id_or_path: str
    degrees: int = 90  # 90, 180, 270
    output_filename: Optional[str] = None


class VideoConvertRequest(BaseModel):
    file_id_or_path: str
    target_format: str = "mp4"  # webm, avi, mov, gif
    output_filename: Optional[str] = None


# PDF Request Models
class PdfConvertRequest(BaseModel):
    file_id_or_path: str
    title: Optional[str] = None
    author: Optional[str] = None
    include_images: bool = True
    output_filename: Optional[str] = None


class PdfMergeRequest(BaseModel):
    files: List[str]
    output_filename: Optional[str] = None


class PdfSplitRequest(BaseModel):
    file_id_or_path: str
    pages: str
    output_filename: Optional[str] = None


class PdfCompressRequest(BaseModel):
    file_id_or_path: str
    output_filename: Optional[str] = None


class PdfToImagesRequest(BaseModel):
    file_id_or_path: str
    format: Optional[str] = "png"
    dpi: Optional[int] = 150
    output_filename: Optional[str] = None


class ImagesToPdfRequest(BaseModel):
    files: List[str]
    output_filename: Optional[str] = None


class PdfRotateRequest(BaseModel):
    file_id_or_path: str
    degrees: int = 90
    output_filename: Optional[str] = None


class PdfWatermarkRequest(BaseModel):
    file_id_or_path: str
    text: str
    output_filename: Optional[str] = None


class PdfProtectRequest(BaseModel):
    file_id_or_path: str
    password: str
    output_filename: Optional[str] = None


class PdfToTextRequest(BaseModel):
    file_id_or_path: str
    output_filename: Optional[str] = None


class PdfOcrRequest(BaseModel):
    file_id_or_path: str
    language: Optional[str] = "spa+eng"
    output_filename: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Herramientas Web Locales activas</h1>"


def resolve_file_path(f: str) -> str:
    if os.path.isabs(f) and os.path.exists(f):
        return f
    upload_path = os.path.join(UPLOADS_DIR, f)
    if os.path.exists(upload_path):
        return upload_path
    raise HTTPException(status_code=404, detail=f"No se encontró el archivo: {f}")


# ================= MULTI-FILE UPLOAD & PATH ENDPOINTS =================

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    uploaded_info = []
    valid_img_exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
    valid_vid_exts = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts"]
    
    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower()
        unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        dest_path = os.path.join(UPLOADS_DIR, unique_name)
        
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if file_ext == ".pdf":
            uploaded_info.append({
                "id": unique_name,
                "filename": file.filename,
                "file_path": dest_path,
                "type": "pdf",
                "size": os.path.getsize(dest_path)
            })
        elif file_ext in valid_img_exts:
            uploaded_info.append({
                "id": unique_name,
                "filename": file.filename,
                "file_path": dest_path,
                "type": "image",
                "size": os.path.getsize(dest_path)
            })
        elif file_ext in valid_vid_exts:
            info = await get_video_info(dest_path)
            info["id"] = unique_name
            info["is_upload"] = True
            info["type"] = "video"
            uploaded_info.append(info)
            
    return {"status": "ok", "files": uploaded_info}


@app.post("/api/add-by-path")
async def add_by_path(req: PathRequest):
    files_info = []
    valid_img_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    valid_vid_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts")
    
    for path in req.paths:
        clean_path = path.strip('"\'')
        if os.path.isdir(clean_path):
            for root, _, filenames in os.walk(clean_path):
                for fn in sorted(filenames):
                    fp = os.path.join(root, fn)
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in valid_vid_exts:
                        info = await get_video_info(fp)
                        info["id"] = fp
                        info["is_upload"] = False
                        info["type"] = "video"
                        files_info.append(info)
                    elif ext == ".pdf":
                        files_info.append({
                            "id": fp,
                            "filename": fn,
                            "file_path": fp,
                            "type": "pdf",
                            "size": os.path.getsize(fp)
                        })
                    elif ext in valid_img_exts:
                        files_info.append({
                            "id": fp,
                            "filename": fn,
                            "file_path": fp,
                            "type": "image",
                            "size": os.path.getsize(fp)
                        })
        elif os.path.isfile(clean_path):
            ext = os.path.splitext(clean_path)[1].lower()
            if ext == ".pdf":
                files_info.append({
                    "id": clean_path,
                    "filename": os.path.basename(clean_path),
                    "file_path": clean_path,
                    "type": "pdf",
                    "size": os.path.getsize(clean_path)
                })
            elif ext in valid_img_exts:
                files_info.append({
                    "id": clean_path,
                    "filename": os.path.basename(clean_path),
                    "file_path": clean_path,
                    "type": "image",
                    "size": os.path.getsize(clean_path)
                })
            else:
                info = await get_video_info(clean_path)
                info["id"] = clean_path
                info["is_upload"] = False
                info["type"] = "video"
                files_info.append(info)
        else:
            files_info.append({
                "file_path": clean_path,
                "filename": os.path.basename(clean_path),
                "error": "El archivo o ruta no existe en el disco."
            })
            
    return {"status": "ok", "files": files_info}


# ================= VIDEO TOOLS SUITE ENDPOINTS =================

async def run_generic_video_task(task_id: str, func, output_name: str, *args, **kwargs):
    def update_progress(percent: float, message: str):
        tasks_db[task_id]["progress"] = percent
        tasks_db[task_id]["message"] = message

    try:
        tasks_db[task_id]["status"] = "processing"
        output_file_path = os.path.join(OUTPUTS_DIR, output_name)
        
        await func(*args, output_path=output_file_path, progress_callback=update_progress, **kwargs)
        
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["progress"] = 100.0
        tasks_db[task_id]["message"] = "¡Proceso de vídeo completado con éxito!"
        tasks_db[task_id]["output_file"] = output_file_path
        tasks_db[task_id]["download_url"] = f"/api/download/{output_name}"
    except Exception as e:
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["message"] = str(e)


@app.post("/api/merge")
async def start_merge(req: MergeRequest):
    if not req.files or len(req.files) < 1:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos 1 vídeo para unificar.")
        
    resolved_paths = [resolve_file_path(f) for f in req.files]
    task_id = uuid.uuid4().hex
    output_filename = req.output_filename or f"video_unificado_{uuid.uuid4().hex[:6]}.mp4"
    if not output_filename.endswith(".mp4"):
        output_filename += ".mp4"

    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(
        task_id, merge_videos, output_filename, input_files=resolved_paths, target_resolution=req.target_resolution, preset=req.preset
    ))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/trim")
async def api_video_trim(req: VideoTrimRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"video_cortado_{uuid.uuid4().hex[:6]}.mp4"
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.trim_video, output_name, vid_path, req.start_time, req.end_time))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/volume")
async def api_video_volume(req: VideoVolumeRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"video_volumen_{uuid.uuid4().hex[:6]}.mp4"
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.adjust_volume, output_name, vid_path, req.volume_factor))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/speed")
async def api_video_speed(req: VideoSpeedRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"video_velocidad_{uuid.uuid4().hex[:6]}.mp4"
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.change_speed, output_name, vid_path, req.speed_factor))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/extract-audio")
async def api_video_extract_audio(req: VideoExtractAudioRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    fmt = req.audio_format.lower()
    output_name = req.output_filename or f"audio_extraido_{uuid.uuid4().hex[:6]}.{fmt}"
    if not output_name.lower().endswith(f".{fmt}"):
        output_name += f".{fmt}"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.extract_audio, output_name, vid_path, fmt))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/rotate")
async def api_video_rotate(req: VideoRotateRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"video_rotado_{uuid.uuid4().hex[:6]}.mp4"
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.rotate_video, output_name, vid_path, req.degrees))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/video/convert")
async def api_video_convert(req: VideoConvertRequest):
    vid_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    fmt = req.target_format.lower()
    output_name = req.output_filename or f"video_convertido_{uuid.uuid4().hex[:6]}.{fmt}"
    if not output_name.lower().endswith(f".{fmt}"):
        output_name += f".{fmt}"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_video_task(task_id, video_tools.convert_video, output_name, vid_path, fmt))
    return {"status": "ok", "task_id": task_id}


# ================= PDF TO EPUB & PDF SUITE ENDPOINTS =================

async def run_pdf_convert_task(task_id: str, pdf_path: str, title: str, author: str, include_images: bool, output_name: str):
    def update_progress(percent: float, message: str):
        tasks_db[task_id]["progress"] = percent
        tasks_db[task_id]["message"] = message

    try:
        tasks_db[task_id]["status"] = "processing"
        tasks_db[task_id]["message"] = "Iniciando conversión de PDF..."
        
        output_file_path = os.path.join(OUTPUTS_DIR, output_name)
        result = await convert_pdf_to_epub(
            pdf_path=pdf_path,
            output_epub_path=output_file_path,
            title=title,
            author=author,
            include_images=include_images,
            progress_callback=update_progress
        )
        
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["progress"] = 100.0
        tasks_db[task_id]["message"] = "¡Conversión a EPUB completada!"
        tasks_db[task_id]["output_file"] = output_file_path
        tasks_db[task_id]["download_url"] = f"/api/download/{output_name}"
        tasks_db[task_id]["result_details"] = result
    except Exception as e:
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["message"] = str(e)


@app.post("/api/convert-pdf")
async def start_pdf_conversion(req: PdfConvertRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    raw_name = req.output_filename or os.path.splitext(os.path.basename(pdf_path))[0]
    output_filename = f"{raw_name}.epub" if not raw_name.lower().endswith(".epub") else raw_name

    tasks_db[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "message": "En cola...",
        "output_filename": output_filename
    }

    asyncio.create_task(run_pdf_convert_task(
        task_id=task_id,
        pdf_path=pdf_path,
        title=req.title,
        author=req.author,
        include_images=req.include_images,
        output_name=output_filename
    ))

    return {"status": "ok", "task_id": task_id}


async def run_generic_pdf_task(task_id: str, func, output_name: str, *args, **kwargs):
    def update_progress(percent: float, message: str):
        tasks_db[task_id]["progress"] = percent
        tasks_db[task_id]["message"] = message

    try:
        tasks_db[task_id]["status"] = "processing"
        output_file_path = os.path.join(OUTPUTS_DIR, output_name)
        
        res = await func(*args, output_path=output_file_path, progress_callback=update_progress, **kwargs)
        
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["progress"] = 100.0
        tasks_db[task_id]["message"] = "¡Proceso completado con éxito!"
        tasks_db[task_id]["output_file"] = output_file_path
        tasks_db[task_id]["download_url"] = f"/api/download/{output_name}"
        if isinstance(res, dict):
            tasks_db[task_id]["result_details"] = res
    except Exception as e:
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["message"] = str(e)


@app.post("/api/pdf/merge")
async def api_pdf_merge(req: PdfMergeRequest):
    paths = [resolve_file_path(f) for f in req.files]
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_unificado_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.merge_pdfs, output_name, paths))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/split")
async def api_pdf_split(req: PdfSplitRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_dividido_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.split_pdf, output_name, pdf_path, req.pages))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/compress")
async def api_pdf_compress(req: PdfCompressRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_comprimido_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.compress_pdf, output_name, pdf_path))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/to-images")
async def api_pdf_to_images(req: PdfToImagesRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_imagenes_{uuid.uuid4().hex[:6]}.zip"
    if not output_name.lower().endswith(".zip"):
        output_name += ".zip"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    
    async def run_img_task():
        def update_progress(p, m):
            tasks_db[task_id]["progress"] = p
            tasks_db[task_id]["message"] = m
        try:
            tasks_db[task_id]["status"] = "processing"
            out_file = os.path.join(OUTPUTS_DIR, output_name)
            await pdf_tools.pdf_to_images(pdf_path, out_file, image_format=req.format, dpi=req.dpi, progress_callback=update_progress)
            tasks_db[task_id]["status"] = "completed"
            tasks_db[task_id]["progress"] = 100.0
            tasks_db[task_id]["message"] = "¡Imágenes exportadas en archivo ZIP!"
            tasks_db[task_id]["download_url"] = f"/api/download/{output_name}"
        except Exception as e:
            tasks_db[task_id]["status"] = "error"
            tasks_db[task_id]["message"] = str(e)
            
    asyncio.create_task(run_img_task())
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/from-images")
async def api_images_to_pdf(req: ImagesToPdfRequest):
    paths = [resolve_file_path(f) for f in req.files]
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"imagenes_a_pdf_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.images_to_pdf, output_name, paths))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/rotate")
async def api_pdf_rotate(req: PdfRotateRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_rotado_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.rotate_pdf, output_name, pdf_path, req.degrees))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/watermark")
async def api_pdf_watermark(req: PdfWatermarkRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_marca_agua_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.add_watermark, output_name, pdf_path, req.text))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/protect")
async def api_pdf_protect(req: PdfProtectRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_protegido_{uuid.uuid4().hex[:6]}.pdf"
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.protect_pdf, output_name, pdf_path, req.password))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/to-text")
async def api_pdf_to_text(req: PdfToTextRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_texto_{uuid.uuid4().hex[:6]}.txt"
    if not output_name.lower().endswith(".txt"):
        output_name += ".txt"
        
    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.pdf_to_text, output_name, pdf_path))
    return {"status": "ok", "task_id": task_id}


@app.post("/api/pdf/ocr")
async def api_pdf_ocr(req: PdfOcrRequest):
    pdf_path = resolve_file_path(req.file_id_or_path)
    task_id = uuid.uuid4().hex
    output_name = req.output_filename or f"pdf_ocr_{uuid.uuid4().hex[:6]}.txt"
    if not output_name.lower().endswith(".txt"):
        output_name += ".txt"

    tasks_db[task_id] = {"status": "pending", "progress": 0.0, "message": "En cola..."}
    asyncio.create_task(run_generic_pdf_task(task_id, pdf_tools.pdf_ocr, output_name, pdf_path, req.language))
    return {"status": "ok", "task_id": task_id}


# ================= SHARED DOWNLOAD & UTILS ENDPOINTS =================

@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tasks_db[task_id]


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        
    ext = os.path.splitext(filename)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
        ".zip": "application/zip",
        ".txt": "text/plain; charset=utf-8",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".gif": "image/gif",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav"
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type, filename=filename)


@app.post("/api/open-folder")
async def open_output_folder():
    """Opens the output directory in Windows File Explorer."""
    try:
        os.startfile(OUTPUTS_DIR)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    print(f"Iniciando Servidor de Herramientas Web Locales en http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)

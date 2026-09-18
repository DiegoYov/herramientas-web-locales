# 🧰 Herramientas Web Locales - Suite Vídeo & PDF

Una plataforma web local y privada (100% offline) construida con **FastAPI**, **FFmpeg** y **PyMuPDF**, diseñada para realizar edición de vídeo rápida y manipular documentos PDF sin necesidad de subir tus archivos a internet ni depender de servicios en la nube.

---

## 🚀 Características Principales

### 🎬 Suite de Edición de Vídeos (Estilo 123apps)
- **Unificador de Vídeos**: Une múltiples clips de vídeo de diferentes resoluciones, formatos y framerates en un solo archivo.
- **Cortar / Dividir Vídeo**: Extrae segmentos especificando tiempo exacto de inicio y fin (`00:00:10` a `00:01:30`) de forma ultrarrápida.
- **Control / Potenciador de Volumen**: Sube el volumen del audio hasta un **300% (Audio Boost)**, redúcelo o silencia (Mute) el vídeo.
- **Cambiar Velocidad**: Acelera a 1.25x, 1.5x, 2.0x (cámara rápida) o ralentiza a 0.5x (cámara lenta) manteniendo sincronía de audio.
- **Extraer Audio a MP3 / WAV**: Extrae únicamente la banda sonora de cualquier vídeo.
- **Rotar Vídeo**: Gira vídeos 90°, 180° o 270°.
- **Convertidor de Formatos**: Convierte entre MP4, WEBM, AVI, MOV y GIF animado.

### 📄 Suite de Herramientas PDF (Estilo ILovePDF)
- **Reconocimiento OCR**: Escanea e identifica texto en PDFs o imágenes de documentos escaneados.
- **PDF a EPUB**: Convierte libros o documentos PDF a formato EPUB estándar para e-readers (Kindle, Kobo, iPad).
- **Unir PDFs**: Combina varios archivos PDF en un único documento.
- **Dividir PDF**: Extrae páginas específicas o rangos (ej: `1, 3, 5-8`).
- **Comprimir PDF**: Optimiza objetos y fuentes para reducir el peso en MB.
- **PDF a Imágenes & Imágenes a PDF**: Exporta páginas a imágenes PNG/JPG o convierte imágenes en PDF.
- **Rotar PDF / Marca de Agua / Protección por Contraseña / Extraer a TXT**.

---

## 📋 Requisitos Previos

- Python 3.10+
- FFmpeg (instalado en el PATH del sistema)

---

## 📦 Instalación y Ejecución

### Opción 1: En Windows con un solo doble clic
Ejecuta el script incluido:
```cmd
run.bat
```
Esto instalará las dependencias necesarias y abrirá automáticamente tu navegador en `http://127.0.0.1:8000`.

### Opción 2: Desde la terminal
1. Clona el repositorio e instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Inicia la aplicación:
   ```bash
   python app.py
   ```
3. Abre en tu navegador:
   [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🔒 Privacidad & Rendimiento
- **100% Offline**: Ningún archivo se envía a servidores externos ni a la nube.
- **Procesamiento Nativo**: Operaciones de vídeo potenciadas por FFmpeg nativo y procesamiento de PDF con PyMuPDF.

---

## 📄 Licencia
Este proyecto es de código abierto bajo la licencia MIT.

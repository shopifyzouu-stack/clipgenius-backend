import os
import time
import uuid
import json
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import google.generativeai as genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

jobs_db = {}

class VideoRequest(BaseModel):
    videoUrl: str
    platform: str = "youtube"

def process_real_video(job_id: str, url: str):
    jobs_db[job_id] = {"status": "processing"}
    
    try:
        # 1. LEER EL VIDEO REAL DE YOUTUBE
        ydl_opts = {
            'quiet': True,
            'skip_download': True # Por ahora leemos la info sin gastar espacio del servidor
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Video Desconocido')
            video_desc = info.get('description', '')[:500] # Solo leemos un trozo para no saturar a la IA
            
        # 2. LA IA DE GEMINI ANALIZA LA INFO
        if GEMINI_KEY:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            Analiza este video de YouTube. 
            Título: {video_title}
            Descripción: {video_desc}
            
            Dame 1 idea para un clip corto viral (TikTok/Reels) basado en este video.
            Devuelve SOLO un JSON válido con este formato exacto, sin ninguna otra palabra:
            {{"title": "Un título muy llamativo", "viralScore": 95, "duration": "0:45"}}
            """
            
            response = model.generate_content(prompt)
            texto_ia = response.text.replace("```json", "").replace("```", "").strip()
            datos_ia = json.loads(texto_ia)
        else:
            datos_ia = {"title": f"Clip de: {video_title}", "viralScore": 85, "duration": "0:30"}

        # 3. ENVIAR RESULTADOS REALES A LOVABLE
        jobs_db[job_id] = {
            "status": "completed",
            "clips": [
                {
                    "id": f"clip_{job_id}",
                    "title": datos_ia.get("title", video_title),
                    "viralScore": datos_ia.get("viralScore", 90),
                    "duration": datos_ia.get("duration", "0:30"),
                    "videoUrl": url # Devolvemos el mismo link para que puedas verlo
                }
            ]
        }

    except Exception as e:
        jobs_db[job_id] = {"status": "error", "message": f"Error al procesar: {str(e)}"}

@app.post("/api/process")
async def iniciar_proceso(req: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {"status": "starting"}
    background_tasks.add_task(process_real_video, job_id, req.videoUrl)
    return {"jobId": job_id}

@app.get("/api/status/{job_id}")
async def consultar_estado(job_id: str):
    return jobs_db.get(job_id, {"status": "error", "message": "Proceso no encontrado"})NDER
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# 3. INICIALIZAR HERRAMIENTAS DE IA Y BASE DE DATOS
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Memoria temporal para guardar el estado de los videos
jobs_db = {}

class VideoRequest(BaseModel):
    videoUrl: str
    platform: str = "youtube"

# 4. LA FUNCIÓN QUE TRABAJA EN SEGUNDO PLANO
def procesar_video_ia(job_id: str, url: str):
    jobs_db[job_id] = "processing"
    
    # Aquí es donde en el futuro irá yt-dlp y ffmpeg para cortar el video real.
    # Por ahora, simulamos el tiempo de proceso para probar que la conexión con Lovable es perfecta.
    time.sleep(10) 
    
    # Simulamos que la IA terminó y subió el video a tu Supabase
    jobs_db[job_id] = {
        "status": "completed",
        "clips": [
            {
                "id": f"clip_{job_id}",
                "title": "Gancho Viral Creado por IA",
                "viralScore": 98,
                "duration": "0:45",
                "videoUrl": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
            }
        ]
    }

# 5. LAS "PUERTAS" (ENDPOINTS) QUE LOVABLE VA A TOCAR

@app.post("/api/process")
async def iniciar_proceso(req: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = "starting"
    
    # Mandamos a la IA a trabajar en segundo plano para no congelar la app
    background_tasks.add_task(procesar_video_ia, job_id, req.videoUrl)
    
    return {"jobId": job_id}

@app.get("/api/status/{job_id}")
async def consultar_estado(job_id: str):
    job_data = jobs_db.get(job_id, "not_found")
    
    if isinstance(job_data, dict) and job_data.get("status") == "completed":
        return job_data
    elif job_data == "not_found":
        return {"status": "error", "message": "Proceso no encontrado"}
    else:
        return {"status": "processing"}

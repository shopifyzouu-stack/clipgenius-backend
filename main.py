import os
import time
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import google.generativeai as genai

# Inicializar la aplicación
app = FastAPI()

# 1. ELIMINAR EL BLOQUEO CORS (Vital para que Lovable se conecte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que cualquier app frontend se conecte
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. LEER TUS CLAVES SECRETAS DE RENDER
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

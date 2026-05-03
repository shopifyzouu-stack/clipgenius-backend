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
            'skip_download': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Video Desconocido')
            video_desc = info.get('description', '')[:500]
            
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
                    "videoUrl": url 
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
    return jobs_db.get(job_id, {"status": "error", "message": "Proceso no encontrado"})

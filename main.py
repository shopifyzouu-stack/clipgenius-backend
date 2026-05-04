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
        video_title = "Video Viral"
        video_desc = ""
        video_id = ""
        
        # 1. LEER EL VIDEO Y SACAR SU ID
        try:
            ydl_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', video_title)
                video_desc = info.get('description', '')[:500]
                video_id = info.get('id', '')
        except Exception as yt_error:
            print(f"Error leyendo YT: {yt_error}")
            
        # Si por algún motivo yt-dlp no saca el ID, lo intentamos sacar de la URL a la fuerza
        if not video_id and "v=" in url:
            video_id = url.split("v=")[1][:11]
            
        # 2. GEMINI DECIDE EL RECORTE (SEGUNDOS EXACTOS)
        datos_ia = {
            "title": f"Clip de: {video_title}", 
            "viralScore": 95, 
            "startTime": 30, # Por defecto empieza en el segundo 30
            "endTime": 60    # Por defecto termina en el 60
        }
        
        if GEMINI_KEY and len(GEMINI_KEY) > 10:
            try:
                model = genai.GenerativeModel('gemini-pro')
                prompt = f"""
                Analiza este video. Título: {video_title}. Descripción: {video_desc}.
                Encuentra el momento con más potencial viral para un clip corto.
                Devuelve SOLO un JSON con este formato exacto:
                {{"title": "Título del clip", "viralScore": 99, "startTime": 15, "endTime": 45}}
                NOTA: startTime y endTime deben ser números enteros (segundos). El clip debe durar entre 15 y 60 segundos.
                """
                response = model.generate_content(prompt)
                texto_ia = response.text.replace("```json", "").replace("```", "").strip()
                datos_parsed = json.loads(texto_ia)
                
                # Actualizamos con lo que pensó la IA
                datos_ia["title"] = datos_parsed.get("title", datos_ia["title"])
                datos_ia["viralScore"] = datos_parsed.get("viralScore", datos_ia["viralScore"])
                datos_ia["startTime"] = int(datos_parsed.get("startTime", 30))
                datos_ia["endTime"] = int(datos_parsed.get("endTime", 60))
            except Exception as ia_error:
                print(f"Error IA: {ia_error}")
                pass

        # 3. CREAMOS EL ENLACE DEL CLIP RECORTADO
        # Usamos el formato "embed" de YouTube pasándole el inicio y el fin
        clip_url = f"https://www.youtube.com/embed/{video_id}?start={datos_ia['startTime']}&end={datos_ia['endTime']}&autoplay=1"

        # 4. ENVIAR A LOVABLE
        jobs_db[job_id] = {
            "status": "completed",
            "clips": [
                {
                    "id": f"clip_{job_id}",
                    "title": datos_ia["title"],
                    "viralScore": datos_ia["viralScore"],
                    "duration": f"{datos_ia['endTime'] - datos_ia['startTime']}s",
                    "videoUrl": clip_url 
                }
            ]
        }

    except Exception as e:
        jobs_db[job_id] = {"status": "error", "message": f"Error crítico: {str(e)}"}

@app.post("/api/process")
async def iniciar_proceso(req: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {"status": "starting"}
    background_tasks.add_task(process_real_video, job_id, req.videoUrl)
    return {"jobId": job_id}

@app.get("/api/status/{job_id}")
async def consultar_estado(job_id: str):
    return jobs_db.get(job_id, {"status": "error", "message": "Proceso no encontrado"})

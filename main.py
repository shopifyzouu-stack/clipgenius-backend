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
            pass
            
        if not video_id and "v=" in url:
            video_id = url.split("v=")[1][:11]
            
        # 2. GEMINI DECIDE 3 RECTORTES VIRALES
        clips_finales = []
        
        if GEMINI_KEY and len(GEMINI_KEY) > 10:
            try:
                model = genai.GenerativeModel('gemini-pro')
                prompt = f"""
                Analiza este video. Título: {video_title}. Descripción: {video_desc}.
                Encuentra los 3 mejores momentos con potencial viral para clips cortos de TikTok/Reels.
                Devuelve SOLO un JSON con un array llamado 'clips' que contenga 3 objetos. 
                Formato exacto:
                {{
                  "clips": [
                    {{"title": "Título 1", "viralScore": 99, "startTime": 15, "endTime": 45}},
                    {{"title": "Título 2", "viralScore": 85, "startTime": 120, "endTime": 160}},
                    {{"title": "Título 3", "viralScore": 75, "startTime": 300, "endTime": 330}}
                  ]
                }}
                """
                response = model.generate_content(prompt)
                texto_ia = response.text.replace("```json", "").replace("```", "").strip()
                datos_parsed = json.loads(texto_ia)
                
                lista_ia = datos_parsed.get("clips", [])
                
                for idx, clip in enumerate(lista_ia):
                    inicio = int(clip.get("startTime", 0))
                    fin = int(clip.get("endTime", 30))
                    clips_finales.append({
                        "id": f"clip_{job_id}_{idx}",
                        "title": clip.get("title", f"Clip {idx+1}"),
                        "viralScore": clip.get("viralScore", 80),
                        "duration": f"{fin - inicio}s",
                        "videoUrl": f"https://www.youtube.com/embed/{video_id}?start={inicio}&end={fin}&autoplay=0"
                    })
            except Exception as ia_error:
                print(f"Error IA: {ia_error}")
                pass

        # Fallback si la IA falla
        if not clips_finales:
            clips_finales.append({
                "id": f"clip_{job_id}_0",
                "title": f"Clip 1 de: {video_title}",
                "viralScore": 90,
                "duration": "30s",
                "videoUrl": f"https://www.youtube.com/embed/{video_id}?start=30&end=60&autoplay=0"
            })

        # 3. ENVIAR A LOVABLE
        jobs_db[job_id] = {
            "status": "completed",
            "clips": clips_finales
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

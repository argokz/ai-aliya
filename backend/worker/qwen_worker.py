import os
import torch
import uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import uvicorn
import shutil

app = FastAPI(title="Qwen3-TTS GPU Worker")

# Global model state
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

def load_model():
    global model
    if model is None:
        print(f"Loading Qwen3-TTS on {device}...")
        from qwen_tts import Qwen3TTSModel
        # Using 1.7B by default for quality
        model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map=device,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32
        )
        print("Model loaded successfully.")
    return model

@app.on_event("startup")
async def startup_event():
    # Pre-load model on startup to avoid latency on first request
    load_model()

@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    language: str = Form("ru"),
    reference_audio: UploadFile = File(...)
):
    try:
        # Create temp dir for processing
        temp_dir = Path("temp_worker")
        temp_dir.mkdir(exist_ok=True)
        
        # Save reference audio
        ref_path = temp_dir / f"ref_{uuid.uuid4().hex[:8]}.wav"
        with ref_path.open("wb") as buffer:
            shutil.copyfileobj(reference_audio.file, buffer)
            
        output_path = temp_dir / f"out_{uuid.uuid4().hex[:8]}.wav"
        
        # Generate using Qwen-TTS
        tts = load_model()
        
        # Qwen3-TTS synthesis logic
        # Note: This follows the pattern from Voicebox backend
        await tts.tts_to_file(
            text=text,
            speaker_wav=str(ref_path),
            language=language,
            file_path=str(output_path)
        )
        
        return FileResponse(
            path=output_path,
            media_type="audio/wav",
            filename=f"synthesis_{uuid.uuid4().hex[:8]}.wav"
        )
        
    except Exception as e:
        print(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)

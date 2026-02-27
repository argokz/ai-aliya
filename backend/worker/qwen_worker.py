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
        
        # Prepare for generation
        import soundfile as sf
        import numpy as np
        
        tts = load_model()
        
        # generate_voice_clone returns Tuple[List[np.ndarray], int]
        audio_list, sample_rate = tts.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=str(ref_path),
            x_vector_only_mode=True
        )
        
        # Concatenate audio chunks if multiple
        if isinstance(audio_list, list) and len(audio_list) > 0:
            full_audio = np.concatenate(audio_list)
        else:
            full_audio = audio_list
            
        # Save to WAV
        sf.write(str(output_path), full_audio, sample_rate)
        
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

import httpx
import os
from pathlib import Path

def test_remote_synthesis():
    worker_url = "http://100.115.128.128:8005"
    text = "Привет! Это проверка связи с твоим графическим ускорителем. Как слышно?"
    ref_audio = Path("sample_voice/aliya_voice_golden.wav")
    
    if not ref_audio.exists():
        print(f"Error: Reference audio {ref_audio} not found!")
        return

    print(f"Sending synthesis request to {worker_url}...")
    
    try:
        with ref_audio.open("rb") as f:
            files = {"reference_audio": (ref_audio.name, f, "audio/wav")}
            data = {"text": text, "language": "ru"}
            
            response = httpx.post(
                f"{worker_url}/synthesize", 
                data=data, 
                files=files, 
                timeout=120.0
            )
            
        if response.status_code == 200:
            output_file = "output/test_qwen_remote.wav"
            Path(output_file).parent.mkdir(exist_ok=True)
            Path(output_file).write_bytes(response.content)
            print(f"Success! Remote audio saved to {output_file}")
        else:
            print(f"Error: Worker returned {response.status_code}")
            print(f"Details: {response.text}")
            
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Tip: Make sure the worker is running on the GPU machine at the specified URL.")

if __name__ == "__main__":
    test_remote_synthesis()

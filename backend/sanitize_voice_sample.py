import sys
import os
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import split_on_silence

def sanitize_audio(input_path, output_path, max_duration_sec=10):
    print(f"Processing {input_path}...")
    audio = AudioSegment.from_file(input_path)
    
    # Remove silence
    # min_silence_len: length of silence to consider (ms)
    # silence_thresh: silence threshold in dB
    chunks = split_on_silence(
        audio, 
        min_silence_len=500, 
        silence_thresh=audio.dBFS-16, 
        keep_silence=200
    )
    
    if not chunks:
        print("No audio found after silence removal!")
        return
        
    combined = sum(chunks)
    
    # Trim to max duration
    if len(combined) > max_duration_sec * 1000:
        print(f"Trimming to {max_duration_sec}s...")
        combined = combined[:max_duration_sec * 1000]
    
    # Normalize
    combined = combined.normalize()
    
    combined.export(output_path, format="wav")
    print(f"Saved preprocessed audio to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sanitize_voice_sample.py input.wav output.wav")
        sys.exit(1)
        
    sanitize_audio(sys.argv[1], sys.argv[2])

import os
import httpx
import base64
from pathlib import Path

def test_gemini_audio_direct():
    api_key = os.environ.get('GEMINI_API_KEY', 'AIzaSyArpEHtH7KFw_JSZN46rQZv46jPOoeCK8E')
    model_name = 'gemini-2.5-flash-preview-tts'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    print(f"Testing Gemini direct API call: {model_name}")
    
    payload = {
        "contents": [{
            "parts": [{
                "text": "Hello, this is a test of a female Gemini voice for better voice conversion."
            }]
        }],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Aoede"
                    }
                }
            }
        }
    }
    
    try:
        print("Sending request to Gemini API...")
        response = httpx.post(url, json=payload, timeout=60.0)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        print("Response received successfully.")
        
        if "candidates" in data:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for i, part in enumerate(candidate["content"]["parts"]):
                    print(f"Part {i} keys: {part.keys()}")
                    if "inlineData" in part:
                        audio_data = part["inlineData"]["data"]
                        mime_type = part["inlineData"].get("mimeType", "audio/wav")
                        print(f"Found audio data with mime_type: {mime_type}")
                        output_file = "test_gemini_audio_direct.wav"
                        Path(output_file).write_bytes(base64.b64decode(audio_data))
                        print(f"Success! Audio saved to {output_file} ({len(audio_data)} bytes base64)")
                        return
                    elif "text" in part:
                        print(f"Part {i} text: {part['text']}")
                    
        print(f"Full Response data structure (keys): {data.keys()}")
        if "candidates" in data:
             print(f"Candidate 0 keys: {data['candidates'][0].keys()}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_gemini_audio_direct()

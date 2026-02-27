import asyncio
import os
import shutil
from pathlib import Path

from app.config import get_settings
from app.services.llm_service import LLMService
from app.services.voice_service import VoiceService

async def main():
    # 1. Setup
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, help="TTS mode")
    args, _ = parser.parse_known_args()

    settings = get_settings()
    if args.mode:
        settings.tts_mode = args.mode
        print(f"Использование режима TTS: {args.mode}")
        
    llm = LLMService(settings)
    voice = VoiceService(settings)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    question = "Привет, Алия! Как твои дела? Расскажи что-нибудь интересное."
    print(f"Вопрос: {question}")
    
    # 2. Get LLM response
    print("Генерация ответа через LLM...")
    try:
        reply = await llm.generate_reply(question)
        print(f"Ответ Алии: {reply}")
    except Exception as e:
        print(f"Ошибка LLM: {e}")
        return

    # 3. Synthesize voice
    print("Синтез голоса (Aliya XTTS)...")
    try:
        # We use speaker_id='aliya' to trigger the special XTTS logic we implemented
        audio_path = await voice.synthesize(
            text=reply,
            speaker_id="aliya",
            language="ru"
        )
        
        # 4. Move to output folder
        final_path = output_dir / f"response_{Path(audio_path).name}"
        shutil.copy(audio_path, final_path)
        print(f"Готово! Файл сохранен в: {final_path}")
        
    except Exception as e:
        print(f"Ошибка синтеза: {e}")

if __name__ == "__main__":
    # Ensure we can import app
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(main())

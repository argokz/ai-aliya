# AI Alia: Open-Source Voice Assistant (FastAPI + Flutter)

Проект реализует MVP ассистента, где пользователь может:
- писать в чат,
- отправлять голос,
- получать ответ текстом,
- получать ответ голосом в заранее сохраненном ("клонированном") голосе.

Дополнительно есть визуальный персонаж: черный фон + оранжевые глаза, которые:
- следят за пользователем через камеру,
- моргают,
- меняют эмоцию на основе диалога.

## Что уже реализовано

- `backend` на FastAPI с API:
  - `POST /api/v1/voice/enroll` — сохранить референс голоса (1 раз).
  - `GET /api/v1/voice/speakers` — список зарегистрированных голосов.
  - `POST /api/v1/assistant/chat` — текст -> LLM -> (опционально) TTS.
  - `POST /api/v1/assistant/transcribe-and-chat` — аудио -> Whisper -> LLM -> TTS.
  - `GET /api/v1/health`.
- STT через `faster-whisper`.
- LLM через `Ollama` (по умолчанию), либо через OpenAI/Gemini (по API ключу).
- TTS + voice clone через `Coqui XTTS v2` (используется сохраненный референс-голос).
- `frontend` на Flutter:
  - чат,
  - запись аудио с микрофона,
  - отправка в backend,
  - проигрывание ответа,
  - анимированные глаза с отслеживанием лица через камеру.

## Важный момент про GPT/Gemini

Вы просили "например Gemini или GPT", но также "все бесплатно и open-source". Эти требования конфликтуют:
- Gemini/GPT — проприетарные облачные модели.
- Для 100% open-source и бесплатного режима нужен локальный LLM (например через Ollama).

Поэтому в этом MVP по умолчанию используется **локальный open-source LLM**.
Если у вас есть API-ключи, можно переключиться на OpenAI или Gemini только для LLM-части.

## Архитектура

1. Flutter отправляет текст или аудио.
2. FastAPI:
   - если аудио: `faster-whisper` делает транскрипт,
   - `LLMService` генерирует ответ,
   - `EmotionService` определяет эмоцию для глаз,
   - при наличии `speaker_id`: `VoiceService` синтезирует ответ в клонированном голосе.
3. Flutter показывает текст и воспроизводит аудио.
4. Виджет глаз получает вектор движения лица из `CameraGazeService` и анимирует взгляд/эмоции.

## Запуск backend

```bash
cd /Users/hatboy/Projects/ai-aliya/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Системные зависимости

- Для `faster-whisper` и части аудио-конвертаций нужен `ffmpeg`.
- На macOS: `brew install ffmpeg`.

### Локальный LLM (Ollama)

Установите Ollama и загрузите модель (пример):

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

Если используете другую модель/URL, поменяйте `.env`.

### Переключение на GPT или Gemini

В `.env` можно выбрать backend:

```env
LLM_BACKEND=openai
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
```

или

```env
LLM_BACKEND=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash
```

## Запуск frontend

```bash
cd /Users/hatboy/Projects/ai-aliya/frontend
flutter pub get
flutter run
```

Для Android эмулятора API по умолчанию: `http://10.0.2.2:8000/api/v1`.

### Permissions для мобильного клиента

- Android: добавьте `CAMERA`, `RECORD_AUDIO`, `INTERNET` в `AndroidManifest.xml`.
- iOS: добавьте `NSCameraUsageDescription` и `NSMicrophoneUsageDescription` в `Info.plist`.

## Пример API

### 1) Один раз сохранить голос

```bash
curl -X POST "http://localhost:8000/api/v1/voice/enroll" \
  -F "speaker_id=user-1" \
  -F "audio=@/absolute/path/to/reference.wav"
```

### 2) Текстовый запрос

```bash
curl -X POST "http://localhost:8000/api/v1/assistant/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"Привет, как дела?",
    "speaker_id":"user-1",
    "language":"ru",
    "generate_audio": true,
    "history": []
  }'
```

### 3) Аудио запрос

```bash
curl -X POST "http://localhost:8000/api/v1/assistant/transcribe-and-chat" \
  -F "audio=@/absolute/path/to/question.m4a" \
  -F "speaker_id=user-1" \
  -F "language=ru" \
  -F "generate_audio=true"
```

## Где что находится

- Backend: `/Users/hatboy/Projects/ai-aliya/backend/app`
- Frontend: `/Users/hatboy/Projects/ai-aliya/frontend/lib`

## Что улучшить дальше

1. Добавить авторизацию и приватность голосовых профилей.
2. Добавить VAD/шумоподавление перед Whisper.
3. Перенести тяжелые модели в отдельные worker-процессы.
4. Добавить fallback-режимы при недоступности LLM/TTS.
5. Добавить тесты API и e2e тесты Flutter.

100.115.128.128
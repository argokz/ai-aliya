# Whisper Worker Service

Сервис для транскрибации аудио на удалённом ПК с GPU через Tailscale.

## Установка на удалённом ПК (Ubuntu с GPU)

### 1. Установка зависимостей

```bash
# Python 3.10+
sudo apt update
sudo apt install python3-pip python3-venv

# CUDA (если ещё не установлен)
# Следуйте инструкциям NVIDIA для вашей версии

# Создание виртуального окружения
cd /path/to/worker
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Установка Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Запишите IP адрес (например, 100.115.128.128)
```

### 3. Запуск worker

```bash
# Активация venv
source venv/bin/activate

# Запуск
python main.py

# Или через uvicorn напрямую
uvicorn main:app --host 0.0.0.0 --port 8004
```

Если порт занят («Address already in use»), освободить принудительно:
```bash
fuser -k 8004/tcp
# или: kill -9 $(lsof -t -i :8004)
```

### 4. Автозапуск через systemd

Создайте файл `/etc/systemd/system/whisper-worker.service`:

```ini
[Unit]
Description=Whisper Worker Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/worker
Environment="PATH=/path/to/worker/venv/bin"
ExecStart=/path/to/worker/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable whisper-worker
sudo systemctl start whisper-worker
sudo systemctl status whisper-worker
```

## Конфигурация

Переменные окружения:
- `WORKER_PORT` — порт (по умолчанию 8004)
- `WORKER_HOST` — хост (по умолчанию 0.0.0.0)
- `WHISPER_MODEL` — модель: `medium` (по умолчанию, оптимально для GTX 1660 Ti 6GB), `large-v3`, `small`, `base`
- `WHISPER_DEVICE` — устройство: `cuda` или `cpu` (по умолчанию `cuda`)
- `WHISPER_COMPUTE_TYPE` — точность на GPU: `float16` (по умолчанию), `int8_float16`, `int8`
- `WHISPER_BEAM_SIZE` — размер луча поиска, 1=быстро (по умолчанию), 5=качество
- `WHISPER_CONDITION_PREVIOUS` — учитывать предыдущий текст: `false` (быстро), `true` (качество)
- `WHISPER_VAD_MIN_SILENCE_MS` — пауза (мс), после которой VAD режет сегмент: меньше = меньше режем, больше речи сохраняем (по умолчанию 300, было 500)

## API

- `GET /` - Health check
- `GET /health` - Detailed health check
- `POST /transcribe` - Транскрибация аудио файла

### Пример запроса транскрибации:

```bash
curl -X POST "http://100.115.128.128:8004/transcribe?language=ru" \
  -F "file=@lecture.mp3"
```

## Проверка работы

```bash
# Health check
curl http://100.115.128.128:8004/health

# Должен вернуть:
# {"status":"healthy","model":"large-v3","device":"cuda","model_loaded":true}
```

# Проверьте текущий статус
sudo ufw status

# Разрешите порт 8004 для Tailscale сети
# Вариант 1: Разрешить всем в Tailscale сети
sudo ufw allow from 100.0.0.0/8 to any port 8004

# Вариант 2: Разрешить всем (если только Tailscale машины имеют доступ)
sudo ufw allow 8004/tcp

# Или отключите firewall полностью (если только Tailscale используется)
sudo ufw disable  # НЕ рекомендуется для продакшена


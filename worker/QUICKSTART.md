# Быстрый старт Worker

## На удалённом ПК (Ubuntu с GPU)

```bash
# 1. Установите Tailscale и получите IP (например, 100.115.128.128)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 2. Скопируйте worker файлы в ~/whisper-worker
mkdir -p ~/whisper-worker
cd ~/whisper-worker
# Скопируйте: main.py, requirements.txt

# 3. Установите зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Запустите
python main.py
```

Worker будет доступен по адресу: `http://100.115.128.128:8004`

## На основном сервере (backend)

Добавьте в `.env`:

```env
WHISPER_WORKER_URL=http://100.115.128.128:8004
WHISPER_USE_REMOTE=true
```

Перезапустите backend - он автоматически будет использовать worker!

## Проверка

```bash
# На worker
curl http://localhost:8004/health

# С основного сервера
curl http://100.115.128.128:8004/health
```

## Автозапуск (systemd)

См. `README.md` для настройки systemd сервиса.


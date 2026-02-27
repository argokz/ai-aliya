#!/bin/bash
# Скрипт установки Whisper Worker на Ubuntu

set -e

echo "=== Whisper Worker Installation ==="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 не найден. Устанавливаю..."
    sudo apt update
    sudo apt install -y python3-pip python3-venv
fi

# Проверка CUDA
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  CUDA не найден. Убедитесь что CUDA установлен для работы GPU."
    echo "Продолжить без GPU? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ CUDA найден"
    nvidia-smi
fi

# Создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активация и установка зависимостей
echo "Установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Установка завершена ==="
echo ""
echo "Для запуска:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Или через systemd (см. README.md)"


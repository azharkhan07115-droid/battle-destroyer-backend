#!/bin/bash
# Render Bot Install Script
# Run: bash install.sh

echo "[*] Installing Python deps..."
pip install playwright playwright-stealth python-telegram-bot requests

echo "[*] Installing Playwright Chromium..."
playwright install chromium

echo "[*] Done! Run: python3 render_bot.py"

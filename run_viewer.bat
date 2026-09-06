@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
py whatsapp_archive_viewer.py
pause

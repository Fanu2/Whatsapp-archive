# WhatsApp Archive Viewer

A local, read-only WhatsApp export viewer with a WhatsApp-like interface.

## Automatic folder routing

The application defaults to:

`C:\Users\singh\Downloads\WhatsApp(1)`

It automatically scans that folder and routes files by type:

- `_chat.txt` / `.txt` → WhatsApp chat parser
- images → built-in image viewer
- videos → system video player
- audio → system audio player
- PDF/DOCX/XLSX/etc. → system associated application
- unknown files → system associated application

It also searches recursively, so exported media folders do not need to be manually registered.

## Run

```powershell
py -m pip install PySide6
py whatsapp_archive_viewer.py
```

If the folder is moved, use **File → Select WhatsApp Export Folder**.

The application is read-only and does not connect to WhatsApp.

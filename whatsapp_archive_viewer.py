import sys
import re
import os
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QTextBrowser, QLineEdit, QPushButton, QFileDialog,
    QSplitter, QMessageBox, QScrollArea, QFrame, QSizePolicy, QToolBar
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


DEFAULT_FOLDER = Path(r"C:\Users\singh\Downloads\WhatsApp(1)")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".3gp", ".webm"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".amr"}
DOC_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"}


def open_external(path: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def classify(path: Path):
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in DOC_EXT:
        return "document"
    return "file"


def parse_whatsapp_file(path: Path):
    """
    Handles common WhatsApp export forms:
    [dd/mm/yy, hh:mm:ss] Name: message
    dd/mm/yy, hh:mm - Name: message
    dd/mm/yyyy, hh:mm - Name: message
    """
    patterns = [
        re.compile(r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s(.*?):\s(.*)$"),
        re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?)\s-\s(.*?):\s(.*)$"),
    ]
    messages = []
    current = None

    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return []

    for line in text.splitlines():
        match = next((p.match(line) for p in patterns if p.match(line)), None)
        if match:
            if current:
                messages.append(current)
            date_s, time_s, sender, body = match.groups()
            current = {
                "date": date_s,
                "time": time_s,
                "sender": sender.strip(),
                "body": body,
            }
        elif current:
            current["body"] += "\n" + line

    if current:
        messages.append(current)

    return messages


def find_chat_files(folder: Path):
    candidates = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".txt":
            if "_chat" in p.name.lower() or "chat" in p.name.lower():
                candidates.append(p)
    # If there is only one txt file, it is probably the exported chat.
    if not candidates:
        txts = list(folder.rglob("*.txt"))
        if len(txts) == 1:
            candidates = txts
    return sorted(candidates)


class MessageBubble(QFrame):
    def __init__(self, message, mine=False, media_path=None, parent=None):
        super().__init__(parent)
        self.setObjectName("bubble")
        self.setMaximumWidth(720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 7)
        layout.setSpacing(3)

        if not mine:
            sender = QLabel(message["sender"])
            sender.setObjectName("sender")
            layout.addWidget(sender)

        body = message["body"]
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_label.setObjectName("body")
        layout.addWidget(body_label)

        time_label = QLabel(message["time"])
        time_label.setAlignment(Qt.AlignRight)
        time_label.setObjectName("time")
        layout.addWidget(time_label)

        self.setStyleSheet("""
            QFrame#bubble {
                background: #d9fdd3;
                border-radius: 10px;
            }
            QLabel#sender {
                color: #128c7e;
                font-weight: bold;
            }
            QLabel#body {
                color: #111;
                font-size: 14px;
            }
            QLabel#time {
                color: #667781;
                font-size: 10px;
            }
        """ if mine else """
            QFrame#bubble {
                background: white;
                border-radius: 10px;
            }
            QLabel#sender {
                color: #128c7e;
                font-weight: bold;
            }
            QLabel#body {
                color: #111;
                font-size: 14px;
            }
            QLabel#time {
                color: #667781;
                font-size: 10px;
            }
        """)


class ChatView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: 0; background: #efeae2; }")
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(22, 18, 22, 18)
        self.layout.setSpacing(8)
        self.layout.addStretch()
        self.setWidget(self.container)

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_messages(self, messages):
        self.clear()
        mine_name = None
        senders = defaultdict(int)
        for m in messages:
            senders[m["sender"]] += 1
        if senders:
            mine_name = max(senders, key=senders.get)

        previous_date = None
        for m in messages:
            if m["date"] != previous_date:
                date_label = QLabel(m["date"])
                date_label.setAlignment(Qt.AlignCenter)
                date_label.setStyleSheet("""
                    QLabel {
                        background: #d9fdd3;
                        color: #54656f;
                        border-radius: 8px;
                        padding: 5px 10px;
                    }
                """)
                self.layout.insertWidget(self.layout.count() - 1, date_label, 0, Qt.AlignCenter)
                previous_date = m["date"]

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            mine = m["sender"] == mine_name
            bubble = MessageBubble(m, mine)
            if mine:
                row_layout.addStretch()
                row_layout.addWidget(bubble)
            else:
                row_layout.addWidget(bubble)
                row_layout.addStretch()
            self.layout.insertWidget(self.layout.count() - 1, row)

        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class MediaViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight:bold; font-size:16px; padding:8px;")
        self.layout.addWidget(self.title)
        self.preview = QLabel("Select a media item")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(400, 300)
        self.preview.setStyleSheet("background:#202c33; color:white;")
        self.layout.addWidget(self.preview, 1)
        self.open_btn = QPushButton("Open with system application")
        self.open_btn.clicked.connect(self.open_current)
        self.layout.addWidget(self.open_btn)
        self.current = None

    def show_file(self, path: Path):
        self.current = path
        self.title.setText(path.name)
        kind = classify(path)
        if kind == "image":
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaled(
                    self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
            else:
                self.preview.setText("Image could not be displayed.")
        else:
            self.preview.setText(
                f"{kind.upper()}\n\n{path.name}\n\n"
                "Use the button below to open it with the Windows default application."
            )

    def resizeEvent(self, event):
        if self.current and classify(self.current) == "image":
            pix = QPixmap(str(self.current))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaled(
                    self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
        super().resizeEvent(event)

    def open_current(self):
        if self.current:
            open_external(self.current)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Archive Viewer")
        self.resize(1250, 800)
        self.folder = DEFAULT_FOLDER
        self.chat_files = []
        self.messages = []
        self.media = []

        self.build_ui()
        self.apply_theme()

        if self.folder.exists():
            self.scan_folder()
        else:
            self.statusBar().showMessage(
                f"WhatsApp folder not found: {self.folder}"
            )

    def build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        select = QAction("📁 Choose Export Folder", self)
        select.triggered.connect(self.choose_folder)
        toolbar.addAction(select)

        refresh = QAction("↻ Refresh", self)
        refresh.triggered.connect(self.scan_folder)
        toolbar.addAction(refresh)

        search_action = QAction("🔎 Search", self)
        search_action.triggered.connect(lambda: self.search.setFocus())
        toolbar.addAction(search_action)

        splitter = QSplitter(Qt.Horizontal)

        # Left chat/media navigator
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        left_layout.addWidget(self.folder_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search messages or files…")
        self.search.textChanged.connect(self.filter_items)
        left_layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemClicked.connect(self.item_selected)
        left_layout.addWidget(self.list)

        splitter.addWidget(left)

        # Main content
        self.chat = ChatView()
        splitter.addWidget(self.chat)

        self.media_view = MediaViewer()
        splitter.addWidget(self.media_view)

        splitter.setSizes([300, 620, 330])
        self.setCentralWidget(splitter)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background:#efeae2; }
            QToolBar { background:#075e54; color:white; padding:6px; spacing:8px; }
            QToolButton { color:white; font-weight:bold; }
            QListWidget { background:#ffffff; border:0; }
            QListWidget::item { padding:12px; border-bottom:1px solid #eee; }
            QListWidget::item:selected { background:#d9fdd3; }
            QLineEdit { padding:10px; border:1px solid #ddd; border-radius:8px; }
        """)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select WhatsApp Export Folder", str(self.folder)
        )
        if folder:
            self.folder = Path(folder)
            self.scan_folder()

    def scan_folder(self):
        if not self.folder.exists():
            QMessageBox.warning(
                self, "Folder not found",
                f"The WhatsApp export folder does not exist:\n\n{self.folder}"
            )
            return

        self.folder_label.setText(f"📁 {self.folder}")
        self.chat_files = find_chat_files(self.folder)
        self.media = []
        for p in self.folder.rglob("*"):
            if p.is_file() and classify(p) in {"image", "video", "audio", "document"}:
                self.media.append(p)

        self.list.clear()

        # Chat entries
        for chat_path in self.chat_files:
            item = QListWidgetItem(f"💬  {chat_path.stem}")
            item.setData(Qt.UserRole, ("chat", chat_path))
            self.list.addItem(item)

        # Media entries
        for p in sorted(self.media, key=lambda x: x.name.lower()):
            icons = {"image":"🖼️", "video":"🎬", "audio":"🎵", "document":"📄"}
            item = QListWidgetItem(f"{icons.get(classify(p),'📎')}  {p.name}")
            item.setToolTip(str(p))
            item.setData(Qt.UserRole, ("file", p))
            self.list.addItem(item)

        if self.chat_files:
            self.load_chat(self.chat_files[0])
        elif self.media:
            self.media_view.show_file(self.media[0])

        self.statusBar().showMessage(
            f"{len(self.chat_files)} chat file(s) • {len(self.media)} media/document file(s)"
        )

    def load_chat(self, path):
        self.messages = parse_whatsapp_file(path)
        self.chat.show_messages(self.messages)
        self.media_view.title.setText(path.name)
        self.media_view.preview.setText(
            f"WhatsApp chat loaded\n\n{len(self.messages):,} messages\n\n"
            "Select media on the left to preview it."
        )
        self.media_view.current = None

    def item_selected(self, item):
        kind, path = item.data(Qt.UserRole)
        if kind == "chat":
            self.load_chat(path)
        else:
            self.media_view.show_file(path)

    def filter_items(self, text):
        query = text.lower().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(query not in item.text().lower())

        if query and self.messages:
            filtered = [
                m for m in self.messages
                if query in m["body"].lower()
                or query in m["sender"].lower()
                or query in m["date"].lower()
            ]
            self.chat.show_messages(filtered)
        elif not query and self.messages:
            self.chat.show_messages(self.messages)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WhatsApp Archive Viewer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

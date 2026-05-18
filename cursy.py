import sys
import time
import threading
import subprocess
import requests
import re
import signal
import random
from deep_translator import GoogleTranslator

# PyQt5 imports
import os
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QMovie

# --- Backend Logic ---
DICT_URL = "https://freedictionaryapi.com/api/v1/entries/en/{}"
_cache = {}
POLL_INTERVAL = 0.1
DEBOUNCE_DELAY = 0.2  # Wait 0.8 seconds before translating

def fetch_english(word, out):
    try:
        r = requests.get(DICT_URL.format(word), timeout=5,
                         headers={"User-Agent": "Mozilla/5.0 (Ubuntu; Linux)"})
        if r.status_code == 200:
            data = r.json()
            if "entries" in data and data["entries"]:
                first_entry = data["entries"][0]
                senses = first_entry.get("senses", [])
                if senses:
                    text_def = senses[0].get("definition", "")
                    out["defn"] = re.sub(r'<[^>]+>', '', text_def)
    except Exception:
        pass

def fetch_tamil(word, out):
    try:
        out["tamil"] = GoogleTranslator(source="en", target="ta").translate(word)
    except Exception:
        pass

def lookup(word):
    word = word.strip().lower()
    if not word: return None

    if word in _cache:
        return _cache[word]

    out = {"defn": "", "tamil": ""}
    t1 = threading.Thread(target=fetch_english, args=(word, out))
    t2 = threading.Thread(target=fetch_tamil, args=(word, out))
    t1.start(); t2.start()
    t1.join(); t2.join()

    if out["defn"] or out["tamil"]:
        _cache[word] = out
        return out
    return None

def get_primary_selection():
    try:
        result = subprocess.run(
            ["xclip", "-o", "-selection", "primary"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return ""

# --- Polling Thread ---
class PollingThread(QThread):
    # Signal emitted when a new definition is found: word, defn, tamil
    definition_ready = pyqtSignal(str, str, str)
    
    def run(self):
        last = ""
        pending_word = ""
        last_changed_time = 0
        
        while True:
            current = get_primary_selection().strip()
            
            # Detect changes
            if current != last:
                last = current
                # Single word check
                if current and len(current) < 30 and " " not in current and "\n" not in current:
                    pending_word = current
                    last_changed_time = time.time()
                else:
                    pending_word = ""
            
            # Debounce
            if pending_word and (time.time() - last_changed_time > DEBOUNCE_DELAY):
                word_to_lookup = pending_word
                pending_word = ""
                
                res = lookup(word_to_lookup)
                if res and (res["defn"] or res["tamil"]):
                    defn = res["defn"] or "not found"
                    ta = res["tamil"] or "—"
                    self.definition_ready.emit(word_to_lookup, defn, ta)
            
            time.sleep(POLL_INTERVAL)

# --- GUI Application ---
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Setup frameless, translucent window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Speech Bubble
        self.bubble = QLabel("")
        self.bubble.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 240);
                color: #2b2b2b;
                border: 2px solid #aaa;
                border-radius: 15px;
                padding: 15px;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 14px;
            }
        """)
        self.bubble.setWordWrap(True)
        self.bubble.setMinimumWidth(250)
        self.bubble.setMaximumWidth(350)
        self.bubble.hide()
        
        # 2. Desktop Pet (GIF)
        self.pet = QLabel()
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dog.gif")
        self.movie = QMovie(gif_path)
        self.pet.setMovie(self.movie)
        self.movie.start()
        self.pet.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.bubble)
        layout.addWidget(self.pet)
        self.setLayout(layout)
        
        # Determine screen size
        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()
        
        # Initial position (bottom center)
        self.pet_x = self.screen_w // 2
        # Fixed bottom Y coordinate for the window
        self.pet_y = self.screen_h - 100 
        self.target_x = self.pet_x
        
        self.update_position()
        
        # Timers
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50)  # 20 FPS
        
        self.decision_timer = QTimer()
        self.decision_timer.timeout.connect(self.make_decision)
        self.decision_timer.start(3000)  # Make a choice every 3 seconds
        
        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.hide_bubble)
        self.hide_timer.setSingleShot(True)

        # Drag state
        self._dragging = False
        self._drag_offset = None
        # Movement freeze flag
        self._showing_definition = False
        
    def update_position(self):
        # Anchor the bottom of the window to pet_y
        self.move(int(self.pet_x), int(self.pet_y - self.height()))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            # Stop auto-movement while dragging
            self.target_x = self.pet_x
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_offset is not None:
            new_pos = event.globalPos() - self._drag_offset
            self.pet_x = new_pos.x()
            self.pet_y = new_pos.y() + self.height()
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # Sync target to current position so auto-movement stays put
            self.target_x = self.pet_x
            event.accept()

    def make_decision(self):
        # Don't wander while showing a definition
        if self._showing_definition or self._dragging:
            return
        # 50% chance to move
        if random.random() > 0.5:
            # Pick safe target X
            self.target_x = random.randint(50, self.screen_w - self.width() - 50)
            
    def update_animation(self):
        # Freeze movement while definition is visible or while dragging
        if self._showing_definition or self._dragging:
            return
        # Move X coordinate smoothly
        dist = self.target_x - self.pet_x
        if abs(dist) > 5:
            step = 5 if dist > 0 else -5
            self.pet_x += step
            self.update_position()
        else:
            # Idle, snap back to ground
            self.update_position()
            
    def show_definition(self, word, defn, tamil):
        self._showing_definition = True
        # Freeze position: cancel any pending movement
        self.target_x = self.pet_x
        text = f"<b style='font-size: 16px;'>{word}</b><br/><br/><i>{defn}</i><br/><br/><b>TA:</b> {tamil}"
        self.bubble.setText(text)
        self.bubble.show()
        self.adjustSize()
        
        # Ensure bubble doesn't clip off the right edge of screen
        if self.pet_x + self.width() > self.screen_w:
            self.pet_x = self.screen_w - self.width() - 20
            self.target_x = self.pet_x
            
        self.update_position()
            
        # Hide after 8 seconds
        self.hide_timer.start(8000)
        
    def hide_bubble(self):
        self._showing_definition = False
        self.bubble.hide()
        self.adjustSize()
        self.update_position()

def main():
    print("=" * 50)
    print("  Cursy Desktop Pet")
    print("=" * 50)
    print("Highlight any single word and the pet will show the meaning!")
    print("Press Ctrl+C here to stop gracefully.")
    print("Spawning pet...")

    # Enable graceful exit via Ctrl+C in terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    
    # Needs to be called before widget creation to ensure transparency on X11 sometimes
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    window = PetWindow()
    window.show()

    # Start backend polling thread
    poller = PollingThread()
    poller.definition_ready.connect(window.show_definition)
    poller.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

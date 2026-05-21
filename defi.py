import sys
import time
import threading
import subprocess
import requests
import re
import signal
import random
import queue
import json
from deep_translator import GoogleTranslator
import os

# PyQt5 imports
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QMovie

# --- API Configuration ---
API_KEY = "open route api key past here "
API_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "openai/gpt-oss-120b:free"

# --- Backend Logic ---
_cache = {}
POLL_INTERVAL   = 0.05   # 50 ms – snappy clipboard polling
DEBOUNCE_DELAY  = 0.25   # wait for selection to settle before firing

MAX_WORDS = 5
MAX_CHARS = 60

def is_valid_selection(text):
    """Accept a single word or a short technical phrase (up to 5 words)."""
    if not text:
        return False
    if len(text) > MAX_CHARS:
        return False
    words = text.split()
    if len(words) == 0 or len(words) > MAX_WORDS:
        return False
    # Reject sentence-like selections
    if re.search(r'[,;!?]', text):
        return False
    return True

def fetch_ai_definition(phrase, out):
    system_prompt = (
        "You are a concise dictionary assistant. "
        "When given a word or technical term/phrase, respond with exactly ONE short sentence "
        "that defines it clearly, the way Google's featured snippet does. "
        "Do not use bullet points, examples, greetings, or extra explanation. "
        "Only the definition sentence."
    )
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/desktop-pet",
        "X-Title": "defi_desk"
    }
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Define: {phrase}"}
        ]
    }
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=12)
        if r.status_code == 200:
            data = r.json()
            ai_text = data["choices"][0]["message"]["content"].strip()
            out["defn"] = ai_text.strip('"').strip("'")
        else:
            out["defn"] = f"API Error {r.status_code}"
    except requests.exceptions.Timeout:
        out["defn"] = "Error: request timed out."
    except Exception as e:
        out["defn"] = f"Network Error: {str(e)}"

def fetch_tamil(phrase, out):
    try:
        out["tamil"] = GoogleTranslator(source="en", target="ta").translate(phrase)
    except Exception:
        out["tamil"] = "—"

def get_primary_selection():
    try:
        result = subprocess.run(
            ["xclip", "-o", "-selection", "primary"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Polling Thread
# ---------------------------------------------------------------------------
class PollingThread(QThread):
    """
    Owns a result_queue.  Plain Python threads (from lookup_async) push results
    into it.  The QThread's run() loop drains the queue and emits Qt signals
    safely — all signal emissions happen from *this* QThread, never from a raw
    threading.Thread, so PyQt5 cross-thread signal delivery works correctly.
    """
    lookup_started   = pyqtSignal(str)        # emitted instantly on selection
    definition_ready = pyqtSignal(str, str, str)  # emitted when API finishes

    def __init__(self, parent=None):
        super().__init__(parent)
        # Thread-safe queue: plain threads push (phrase, defn, tamil) here
        self._result_queue = queue.Queue()

    def _lookup_async(self, phrase):
        """
        Spawns a daemon thread that does the API work, then pushes the result
        into self._result_queue (safe from any thread).
        """
        phrase_lower = phrase.strip().lower()
        if not phrase_lower:
            return

        # Cache hit — push immediately
        if phrase_lower in _cache:
            cached = _cache[phrase_lower]
            self._result_queue.put((phrase_lower, cached["defn"], cached["tamil"]))
            return

        def _worker(p=phrase_lower):
            out = {"defn": "", "tamil": ""}
            t1 = threading.Thread(target=fetch_ai_definition, args=(p, out))
            t2 = threading.Thread(target=fetch_tamil,         args=(p, out))
            t1.start(); t2.start()
            t1.join();  t2.join()
            defn  = out["defn"]  or "Definition not found."
            tamil = out["tamil"] or "—"
            _cache[p] = {"defn": defn, "tamil": tamil}
            # Push result into the queue — QThread.run() will emit the signal
            self._result_queue.put((p, defn, tamil))

        threading.Thread(target=_worker, daemon=True).start()

    def run(self):
        last            = ""
        pending_phrase  = ""
        last_changed    = 0
        in_flight       = ""

        while True:
            # ── 1. Drain result queue and emit signals (safe: we're in QThread) ──
            while not self._result_queue.empty():
                try:
                    phrase, defn, tamil = self._result_queue.get_nowait()
                    self.definition_ready.emit(phrase, defn, tamil)
                except queue.Empty:
                    break

            # ── 2. Check clipboard ──
            current = get_primary_selection().strip()
            if current != last:
                last = current
                if is_valid_selection(current):
                    pending_phrase = current
                    last_changed   = time.time()
                else:
                    pending_phrase = ""

            # ── 3. Debounce + fire lookup ──
            if pending_phrase and (time.time() - last_changed > DEBOUNCE_DELAY):
                phrase_to_lookup = pending_phrase
                pending_phrase   = ""

                if phrase_to_lookup.lower() == in_flight:
                    time.sleep(POLL_INTERVAL)
                    continue

                in_flight = phrase_to_lookup.lower()

                # Show loading bubble instantly (signal emitted from QThread ✓)
                self.lookup_started.emit(phrase_to_lookup)

                # Fire API calls in background; result arrives via queue
                self._lookup_async(phrase_to_lookup)

            time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        layout.setContentsMargins(0, 0, 0, 0)

        # Speech bubble
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
        self.bubble.setMaximumWidth(380)
        self.bubble.hide()

        # Desktop pet GIF
        self.pet = QLabel()
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dog.gif")
        self.movie = QMovie(gif_path)
        self.pet.setMovie(self.movie)
        self.movie.start()
        self.pet.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.bubble)
        layout.addWidget(self.pet)
        self.setLayout(layout)

        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()

        self.pet_x    = self.screen_w // 2
        self.pet_y    = self.screen_h - 100
        self.target_x = self.pet_x
        self.update_position()

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50)

        self.decision_timer = QTimer()
        self.decision_timer.timeout.connect(self.make_decision)
        self.decision_timer.start(3000)

        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.hide_bubble)
        self.hide_timer.setSingleShot(True)

        self._dragging        = False
        self._drag_offset     = None
        self._showing_def     = False
        self._current_phrase  = ""   # phrase the bubble is currently showing

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging    = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self.target_x     = self.pet_x
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_offset is not None:
            new_pos   = event.globalPos() - self._drag_offset
            self.pet_x = new_pos.x()
            self.pet_y = new_pos.y() + self.height()
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.target_x  = self.pet_x
            event.accept()

    # ── Wandering ─────────────────────────────────────────────────────────────

    def make_decision(self):
        if self._showing_def or self._dragging:
            return
        if random.random() > 0.5:
            self.target_x = random.randint(50, self.screen_w - self.width() - 50)

    def update_animation(self):
        if self._showing_def or self._dragging:
            return
        dist = self.target_x - self.pet_x
        if abs(dist) > 5:
            self.pet_x += 5 if dist > 0 else -5
        self.update_position()

    def update_position(self):
        self.move(int(self.pet_x), int(self.pet_y - self.height()))

    def _clamp_position(self):
        if self.pet_x + self.width() > self.screen_w:
            self.pet_x = self.screen_w - self.width() - 20
            self.target_x = self.pet_x
        if self.pet_x < 10:
            self.pet_x = 10
            self.target_x = self.pet_x

    # ── Bubble ────────────────────────────────────────────────────────────────

    def show_loading(self, phrase):
        """Called instantly when selection is detected."""
        self._showing_def    = True
        self._current_phrase = phrase.lower()
        self.target_x        = self.pet_x
        self.hide_timer.stop()

        self.bubble.setText(
            f"<b style='font-size:16px;'>{phrase}</b>"
            f"<br/><br/><i style='color:#888;'>⏳ Looking up…</i>"
        )
        self.bubble.show()
        self.adjustSize()
        self._clamp_position()
        self.update_position()

    def show_definition(self, phrase, defn, tamil):
        """
        Called from PollingThread (a QThread) via Qt signal — always on main thread.
        Guards against stale results if the user already moved on.
        """
        if phrase.lower() != self._current_phrase:
            return  # stale result — discard silently

        self.bubble.setText(
            f"<b style='font-size:16px;'>{phrase}</b>"
            f"<br/><br/><i>{defn}</i>"
            f"<br/><br/><b>TA:</b> {tamil}"
        )
        self.adjustSize()
        self._clamp_position()
        self.update_position()

        duration = 12000 if " " in phrase else 8000
        self.hide_timer.start(duration)

    def hide_bubble(self):
        self._showing_def    = False
        self._current_phrase = ""
        self.bubble.hide()
        self.adjustSize()
        self.update_position()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("=" * 50)
    print("  Cursy AI Desktop Pet")
    print("=" * 50)
    print(f"AI Model: {AI_MODEL}")
    print("Highlight any word or short phrase (up to 5 words).")
    print("Press Ctrl+C to stop.")

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    window = PetWindow()
    window.show()

    poller = PollingThread()
    poller.lookup_started.connect(window.show_loading)
    poller.definition_ready.connect(window.show_definition)
    poller.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

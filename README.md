# 🐾 Defi Desk — Your Desktop Dictionary Pet

> Highlight any word on your screen. Your pet tells you what it means — instantly.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Linux%20%28X11%29-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

---

## ✨ What Is Defi Desk?

**Defi Desk** is a lightweight Linux desktop pet that doubles as an instant dictionary.

It lives as a cute animated GIF at the bottom of your screen. Whenever you **highlight a single word** — in a PDF, browser, terminal, or any app — it automatically fetches the **English definition** and the **Tamil translation**, then displays them in a speech bubble above the pet.

No clicking. No tab-switching. No typing. Just **highlight and read**.

---

## 🎯 Why I Built This

I was studying from downloaded PDFs and kept hitting unfamiliar technical words. Every time, I had to:

1. Copy the word
2. Open a new browser tab
3. Search on Google
4. Read the definition
5. Close the tab and return to the PDF

That constant context-switching broke my focus. So I built **Defi Desk** — a tool that brings the definition *to me*, right on my desktop, without interrupting my workflow.

---

## 🚀 Features

- 🖱️ **Zero-click workflow** — just highlight a word, the pet does the rest
- 📖 **English definition** via [Free Dictionary API](https://freedictionaryapi.com) (no API key needed)
- 🌐 **Tamil translation** via Google Translate (`deep-translator`)
- 🐾 **Animated desktop pet** that wanders the bottom of your screen
- 💬 **Speech bubble** that auto-hides after 8 seconds
- 🖱️ **Draggable** — move the pet wherever you like
- ⚡ **In-memory cache** — repeated lookups are instant
- 🔁 **Debounced polling** — won't spam API calls while you scroll

---

## 🖥️ Demo

```
┌─────────────────────────────┐
│  ephemeral                  │
│                             │
│  lasting for a very short   │
│  time; short-lived.         │
│                             │
│  TA: தற்காலிக              │
└─────────────────────────────┘
         🐾 [dog wandering]
```

*Highlight the word → pet pops up speech bubble → auto-hides in 8s*

---

## 📦 Requirements

| Dependency     | Purpose                        |
|----------------|-------------------------------|
| Python 3.8+    | Runtime                        |
| PyQt5          | GUI framework                  |
| requests       | HTTP calls to Dictionary API   |
| deep-translator| Google Translate wrapper       |
| xclip          | Read X11 PRIMARY selection     |

---

## ⚙️ Installation

### 1. Clone or Download

```bash
git clone https://github.com/your-username/defi-desk.git
cd defi-desk
```

Or simply download `cursy.py` and a `dog.gif` into the same folder.

### 2. Install Python Dependencies

```bash
pip install PyQt5 requests deep-translator
```

### 3. Install xclip (System Dependency)

```bash
sudo apt install xclip
```

> **Note:** `xclip` is required to read highlighted text from the X11 PRIMARY selection buffer. This tool is Linux (X11) only.

---

## ▶️ Running

```bash
python cursy.py
```

The pet will appear at the **bottom-center** of your screen. Open any PDF, browser, or text file, highlight a single word, and the definition will appear in 1–2 seconds.

To **stop** the pet, press `Ctrl+C` in the terminal.

---

## 📁 Project Structure

```
defi-desk/
├── cursy.py        # Main application script
├── dog.gif         # Animated pet GIF (bring your own!)
└── README.md       # You are here
```

> 💡 You can use **any animated GIF** as your pet — just name it `dog.gif` and place it in the same directory as `cursy.py`.

---

## 🔧 Configuration

A few constants at the top of `cursy.py` that you can tweak:

```python
POLL_INTERVAL  = 0.1   # How often to check highlighted text (seconds)
DEBOUNCE_DELAY = 0.2   # Wait time before triggering a lookup (seconds)
```

And in the `PetWindow` class:

```python
self.decision_timer.start(3000)   # How often the pet picks a new direction (ms)
self.hide_timer.start(8000)       # How long the speech bubble stays visible (ms)
```

### 🌍 Change Translation Language

Open `cursy.py` and find the `fetch_tamil` function:

```python
def fetch_tamil(word, out):
    out["tamil"] = GoogleTranslator(source="en", target="ta").translate(word)
```

Change `"ta"` to any supported language code:

| Language | Code  |
|----------|-------|
| Tamil    | `ta`  |
| Hindi    | `hi`  |
| French   | `fr`  |
| Spanish  | `es`  |
| German   | `de`  |
| Japanese | `ja`  |
| Chinese  | `zh-CN` |

---

## 🏗️ How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    cursy.py Architecture                │
├────────────────┬────────────────────────────────────────┤
│ PollingThread  │  Polls xclip every 100ms               │
│ (QThread)      │  Debounces → triggers lookup           │
│                │  Emits: definition_ready signal        │
├────────────────┼────────────────────────────────────────┤
│ lookup()       │  Fires 2 threads in parallel:          │
│                │   • fetch_english() → Free Dict API    │
│                │   • fetch_tamil()   → Google Translate │
│                │  Caches results in _cache dict         │
├────────────────┼────────────────────────────────────────┤
│ PetWindow      │  Frameless, translucent PyQt5 window   │
│ (QWidget)      │  Animated GIF pet + speech bubble      │
│                │  Smooth movement via 20FPS timer       │
│                │  Draggable, screen-edge-aware          │
└────────────────┴────────────────────────────────────────┘
```

---

## 🐛 Known Issues

- **Inaccurate definitions** — The Free Dictionary API uses general English definitions. Technical terms in specialized contexts (e.g., CS papers) may not have the most precise definition.
- **Linux/X11 only** — Uses `xclip` to monitor the PRIMARY selection buffer. Does not work on Wayland, Windows, or macOS without significant modifications.
- **Single words only** — Phrases and multi-word selections are intentionally ignored to keep lookups fast and accurate.

---

## 🛣️ Roadmap

- [ ] Wayland support (`wl-paste`)
- [ ] Settings panel to choose translation language
- [ ] Support for short phrases (2–3 words)
- [ ] Offline dictionary mode (bundled wordlist)
- [ ] Custom sprite / OpenPets standard support
- [ ] Windows & macOS compatibility

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

1. Fork the repo
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — use it, modify it, share it freely.

---


*If you find this useful, give it a ⭐ on GitHub!*

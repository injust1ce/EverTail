\# 📋 EverTail



EverTail is a lightweight, fast, and anti-cheat safe clipboard manager for Windows 10/11 built with Python and PyQt6. 



Unlike many traditional clipboard tools that use low-level keyboard hooks or simulated keystrokes (`SendInput`) to paste data—which can trigger strict anti-cheat systems in competitive games—EverTail operates cleanly via standard system clipboard APIs.



\---



\## ✨ Features



\* 🛡️ \*\*100% Anti-Cheat Safe:\*\* No simulated keystrokes or suspicious background hooks. Safe to keep running in the system tray while gaming.

\* 🖼️ \*\*Text, Links \& Images:\*\* Automatically saves copied text snippets, URLs, and screenshots/images.

\* 🔒 \*\*100% Local \& Private:\*\* All history and settings are stored locally in simple `.json` and `.png` files right next to the app. Zero cloud syncing or telemetry.

\* 🎨 \*\*Clean Dark UI:\*\* Minimalist dark interface with persistent window positioning.

\* 🌐 \*\*Multi-language:\*\* Built-in instant switch between \*\*English\*\* and \*\*Russian\*\* (`EN` / `RU`).

\* 🔊 \*\*Sound Feedback:\*\* Optional audio notifications on copy actions (can be toggled in settings).



\---



\## 🚀 Installation \& Usage



\### Option 1: Portable Executable (Recommended)

1\. 1. Go to the [**Releases**](https://github.com/injust1ce/EverTail/releases) page and download the latest `EverTail.zip` (или `EverTail.exe`).

2\. Extract it to any folder and run \*\*`EverTail.exe`\*\*.

3\. The app will minimize to your system tray. Copy anything (`Ctrl + C`) and use the tray icon or main window to manage your clipboard history!



\### Option 2: Run from Source (Python)

If you prefer running the script directly or building it yourself:



```bash

\# 1. Install dependencies

pip install PyQt6 pyinstaller pillow



\# 2. Run the app

python evertail.py



\# 3. (Optional) Build standalone .exe

python -m PyInstaller --noconsole --onefile --icon="evertail.ico" --name "EverTail" evertail.py


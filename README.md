# Floatube

> [!WARNING]
> **Disclaimer:** This project is strictly for **educational and personal use only**. It is not intended for commercial use, production deployment, or mass distribution. Do not misuse this application to violate the Terms of Service of any platform. Use responsibly.

Floatube is a beautiful, frameless, and translucent floating desktop widget for YouTube Music. Built with Python and PyQt6, it provides a seamless music listening experience with a modern glassmorphism aesthetic that sits gracefully on your Windows desktop.

## Features

- **Floating & Frameless:** Sits smoothly on your desktop without bulky window borders.
- **Glassmorphism UI:** Translucent background with a modern, dark aesthetic.
- **YouTube Music Integration:** Search, queue, and play directly from YouTube Music without a browser.
- **Auto-Play/Radio:** When the queue finishes, Floatube automatically fetches related tracks to keep the music going.
- **System Tray Integration:** Minimizes to the system tray for easy background listening. Right-click the tray icon to play/pause, skip, or exit.
- **Media Keys Support:** Control playback with your keyboard's global media keys (Play/Pause, Next, Previous).
- **Persistent State:** Remembers your volume, window position, and the last track you were listening to.

## Setup & Installation

### Prerequisites

1. **Python 3.10+**
2. **mpv DLL (Required for audio playback)** 
   Floatube relies on `python-mpv` which requires the `mpv` library.

### Developer Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Floatube.git
   cd Floatube
   ```

2. **Run the setup script:**
   We have provided a setup script that will create a virtual environment and install the required dependencies:
   ```bash
   python setup_dev.py
   ```

3. **Install the mpv DLL:**
   - Go to [mpv Windows Builds](https://sourceforge.net/projects/mpv-player-windows/files/libmpv/).
   - Download the latest `mpv-dev-x86_64-*.7z` release.
   - Extract `mpv-2.dll` (or `libmpv-2.dll`) and place it directly in the root of the Floatube project folder.

## Running the App

After completing the setup, you can launch Floatube by activating the virtual environment and running `main.py`:

```bash
.\venv\Scripts\python main.py
```

## How to Use

1. **Search:** Click the Search icon (🔍) on the title bar and type the name of a song or artist.
2. **Play:** Click on any track from the search results to instantly start playing. Floatube will automatically fetch related tracks to play next.
3. **Queue:** Click the Queue icon (🎵) to see what's playing next, view your listening history, and toggle Repeat or Shuffle.
4. **Move:** Click and drag anywhere on the top title bar to move the widget around your screen.
5. **Minimize & Close:** The minimize button hides the app to your system tray. The close button completely shuts down Floatube.

## Building the Executable

If you want to build a standalone `.exe` file that you can share without needing Python installed:

```bash
.\venv\Scripts\python -m PyInstaller floatube.spec -y
```
*Note: Make sure `libmpv-2.dll` is in the project folder before building, as the executable will need it to run!*

## Technologies Used
- **PyQt6:** For the beautiful, responsive UI.
- **ytmusicapi:** For searching and retrieving YouTube Music track data.
- **yt-dlp:** For resolving high-quality audio streams.
- **python-mpv:** For robust audio playback.

## License
MIT License

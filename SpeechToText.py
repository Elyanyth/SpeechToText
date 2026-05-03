import sounddevice as sd
import numpy as np
import whisper
import pyperclip
from pynput import keyboard
import threading
import time
import pyautogui
import json
import os
import winsound
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
SAMPLE_RATE = 16000
CHANNELS = 1

DEFAULT_SETTINGS = {"hotkey": "f1", "model_size": "base", "sound_enabled": True}

KEYSYM_MAP = {
    "return": "enter", "prior": "page_up", "next": "page_down",
    "insert": "insert", "home": "home", "end": "end",
    "delete": "delete", "tab": "tab", "backspace": "backspace",
    "up": "up", "down": "down", "left": "left", "right": "right",
}
IGNORE_KEYSYMS = {
    "shift_l", "shift_r", "control_l", "control_r",
    "alt_l", "alt_r", "super_l", "super_r",
    "caps_lock", "num_lock", "scroll_lock",
}

settings = {}
recording = False
audio_data = []
stream = None
model = None
model_loading = False
listener = None
tray_icon = None
tk_root = None
settings_win = None
_lock = threading.Lock()

ICONS = {}


def _build_icons():
    for name, color in [("idle", "green"), ("recording", "red"), ("loading", "orange")]:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([4, 4, 60, 60], fill=color)
        ICONS[name] = img


def load_settings():
    global settings
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            settings = {**DEFAULT_SETTINGS, **json.load(f)}
    else:
        settings = DEFAULT_SETTINGS.copy()


def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def update_tray_icon():
    if tray_icon is None:
        return
    if model_loading:
        tray_icon.icon = ICONS["loading"]
        tray_icon.title = "SpeechToText — Loading model…"
    elif recording:
        tray_icon.icon = ICONS["recording"]
        tray_icon.title = "SpeechToText — Recording"
    else:
        tray_icon.icon = ICONS["idle"]
        tray_icon.title = "SpeechToText — Ready"


def play_beep(freq):
    if settings.get("sound_enabled", True):
        threading.Thread(target=lambda: winsound.Beep(freq, 120), daemon=True).start()


def resolve_hotkey():
    name = settings.get("hotkey", "f1")
    try:
        return keyboard.Key[name]
    except KeyError:
        return keyboard.KeyCode.from_char(name)


def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_data.append(indata.copy())


def start_recording():
    global recording, audio_data, stream
    with _lock:
        if recording or model_loading or model is None:
            return
        audio_data = []
        recording = True
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback)
    stream.start()
    update_tray_icon()
    play_beep(880)


def stop_recording():
    global recording, stream
    with _lock:
        if not recording:
            return
        recording = False
    stream.stop()
    stream.close()
    update_tray_icon()
    play_beep(440)
    threading.Thread(target=process_audio, daemon=True).start()


def process_audio():
    if not audio_data:
        return
    audio = np.concatenate(audio_data, axis=0).flatten().astype(np.float32)
    result = model.transcribe(audio)
    text = result["text"].strip()
    if text:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.press("enter")
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
        pyautogui.press("enter")


def on_press(key):
    if key == resolve_hotkey():
        start_recording()


def on_release(key):
    if key == resolve_hotkey():
        stop_recording()


def restart_listener():
    global listener
    if listener is not None:
        listener.stop()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()


def load_model_thread(model_size, on_done=None):
    global model, model_loading
    model_loading = True
    update_tray_icon()
    model = whisper.load_model(model_size)
    model_loading = False
    update_tray_icon()
    if on_done:
        on_done()


def load_model_async(model_size, on_done=None):
    threading.Thread(target=load_model_thread, args=(model_size, on_done), daemon=True).start()


def open_settings_from_tray():
    tk_root.after(0, _open_settings_window)


def _open_settings_window():
    global settings_win
    if settings_win is not None:
        try:
            if settings_win.winfo_exists():
                settings_win.lift()
                settings_win.focus_force()
                return
        except tk.TclError:
            pass

    win = tk.Toplevel(tk_root)
    win.title("SpeechToText Settings")
    win.resizable(False, False)
    settings_win = win

    pad = {"padx": 12, "pady": 6}

    tk.Label(win, text="Model Size:").grid(row=0, column=0, sticky="w", **pad)
    model_var = tk.StringVar(value=settings["model_size"])
    ttk.Combobox(
        win, textvariable=model_var,
        values=["tiny", "base", "small", "medium"],
        state="readonly", width=14
    ).grid(row=0, column=1, **pad)

    tk.Label(win, text="Hotkey:").grid(row=1, column=0, sticky="w", **pad)
    hotkey_var = tk.StringVar(value=settings["hotkey"])
    hk_btn = tk.Button(win, textvariable=hotkey_var, width=14, relief="raised")
    hk_btn.grid(row=1, column=1, **pad)

    capturing = [False]

    def start_capture():
        capturing[0] = True
        hotkey_var.set("Press a key…")
        hk_btn.config(relief="sunken")

    def on_key(event):
        if not capturing[0]:
            return
        keysym = event.keysym.lower()
        if keysym in IGNORE_KEYSYMS:
            return "break"
        capturing[0] = False
        hk_btn.config(relief="raised")
        hotkey_var.set(KEYSYM_MAP.get(keysym, keysym))
        return "break"

    hk_btn.config(command=start_capture)
    win.bind("<KeyPress>", on_key)

    sound_var = tk.BooleanVar(value=settings["sound_enabled"])
    tk.Checkbutton(win, text="Enable sounds", variable=sound_var).grid(
        row=2, column=0, columnspan=2, **pad)

    status = tk.Label(win, text="", fg="blue")
    status.grid(row=3, column=0, columnspan=2)

    def apply():
        if model_loading:
            status.config(text="Wait — model is loading…")
            return
        new_model = model_var.get()
        new_hotkey = hotkey_var.get()
        new_sound = sound_var.get()
        model_changed = new_model != settings["model_size"]
        hotkey_changed = new_hotkey != settings["hotkey"]
        settings["model_size"] = new_model
        settings["hotkey"] = new_hotkey
        settings["sound_enabled"] = new_sound
        save_settings()
        if hotkey_changed:
            restart_listener()
        if model_changed:
            status.config(text=f"Loading {new_model}…")
            def on_loaded():
                tk_root.after(0, lambda: status.config(text="Model loaded!"))
            load_model_async(new_model, on_done=on_loaded)
        else:
            status.config(text="Saved!")

    btn_frame = tk.Frame(win)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=8)
    tk.Button(btn_frame, text="Apply", command=apply, width=10).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Close", command=win.destroy, width=10).pack(side="left", padx=6)

    win.focus_force()


def toggle_sound():
    settings["sound_enabled"] = not settings["sound_enabled"]
    save_settings()


def quit_app():
    if listener:
        listener.stop()
    tray_icon.stop()
    tk_root.after(0, tk_root.destroy)


def main():
    global tray_icon, tk_root

    _build_icons()
    load_settings()

    tk_root = tk.Tk()
    tk_root.withdraw()

    load_model_async(settings["model_size"])
    restart_listener()

    menu = pystray.Menu(
        pystray.MenuItem("Settings", lambda *_: open_settings_from_tray()),
        pystray.MenuItem(
            lambda *_: f"Sound: {'On' if settings.get('sound_enabled', True) else 'Off'}",
            lambda *_: toggle_sound(),
        ),
        pystray.MenuItem("Quit", lambda *_: quit_app()),
    )

    tray_icon = pystray.Icon(
        "SpeechToText", ICONS["loading"],
        "SpeechToText — Loading model…", menu
    )

    threading.Thread(target=tray_icon.run, daemon=True).start()

    tk_root.mainloop()


if __name__ == "__main__":
    main()

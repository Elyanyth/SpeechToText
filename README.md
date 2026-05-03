# SpeechToText

A push-to-talk speech-to-text tool that transcribes your voice and automatically types it into any application. Built for use with game chat, but works anywhere.

## How it works

Hold your configured hotkey to start recording. Release it to stop — the audio is transcribed using [OpenAI Whisper](https://github.com/openai/whisper) and the resulting text is pasted into whatever window is in focus.

The app runs silently in the system tray and starts listening as soon as it launches.

## Features

- **Push-to-talk recording** — hold a key to record, release to transcribe and paste
- **System tray icon** — shows the current state at a glance:
  - Orange — loading model
  - Green — ready
  - Red — recording
- **Audio feedback** — a high beep when recording starts, a low beep when it stops
- **Settings window** — change hotkey and model size without editing any code
- **Live model switching** — swap Whisper models on the fly; the new model loads in the background without restarting
- **Sound toggle** — mute/unmute audio feedback directly from the tray menu

## Requirements

- Python 3.10+
- Dependencies:

```
pip install openai-whisper sounddevice numpy pyperclip pynput pyautogui pystray Pillow
```

## Usage

Run via `start.bat` or directly:

```
python SpeechToText.py
```

The app will appear in the system tray. Right-click the icon to access settings or quit.

## Settings

Right-click the tray icon and select **Settings** to configure:

| Setting | Description |
|---|---|
| **Hotkey** | Click the button then press any key to rebind |
| **Model Size** | `tiny` / `base` / `small` / `medium` — larger models are more accurate but slower to load |
| **Enable sounds** | Toggle audio feedback on or off |

Sound can also be toggled instantly from the tray menu without opening the settings window.

Settings are saved to `settings.json` in the project folder.

## Model sizes

| Model | Speed | Accuracy |
|---|---|---|
| `tiny` | Fastest | Basic |
| `base` | Fast | Good |
| `small` | Moderate | Better |
| `medium` | Slow | Best |

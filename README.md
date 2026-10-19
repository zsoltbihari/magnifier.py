# Cursor Magnifier / Kurzor-nagyító

A lightweight screen magnifier for Linux/X11, designed to work with IceWM and Xfce. The interface is in English. This README contains both English and Hungarian documentation.

---

# English

## Features

- A frameless magnifier that follows the mouse cursor.
- Starts at **2× zoom**. Use the mouse wheel to zoom in or out, up to the configured maximum.
- Keeps a small system-tray icon with a menu for showing/hiding the magnifier, opening Preferences, and exiting.
- `Ctrl+Alt+M` toggles the magnifier.
- `Esc` hides the magnifier without quitting the application.
- While the magnifier is visible, `C` copies the item selected in Preferences:
  1. The magnified screen area as an image.
  2. A LaTeX `xcolor` CMYK definition.
  3. A LaTeX `xcolor` RGB definition.
  4. Plain RGB values, for example `R=100, G=12, B=86`.
- Displays the sampled pixel's RGB and CMYK values.
- Optional pixel scale with its origin at the **bottom-left corner** of the magnifier's image area. Tick marks are drawn every 5 source pixels and labels every 10 pixels.
- Saves settings in `~/.config/icewm-magnifier/config.json`.

## Requirements

- Linux running an **X11** session. Wayland is not supported for the global mouse-wheel capture and may restrict screen capture or hotkeys.
- Python 3
- PySide6
- pynput
- python-xlib
- An active system tray/notification area in the desktop environment.

Install the Python modules into the same Python environment that will run the program. For example:

```bash
python3 -m pip install --user PySide6 pynput python-xlib
```

If your distribution blocks `pip --user` for system Python, use your distribution's packages or a virtual environment. Do not use `sudo pip`.

## Run

Save `icewm_cursor_magnifier_english.py` (or rename it to `icewm_cursor_magnifier.py`) in a convenient location, then run:

```bash
python3 ~/Desktop/icewm_cursor_magnifier.py
```

The tray icon should appear in the notification area. If the application reports that no system tray is available, enable a system-tray applet/plugin for the current desktop session.

## Controls

| Action | Result |
|---|---|
| `Ctrl+Alt+M` | Show or hide the magnifier |
| `Esc` | Hide the magnifier; keep the application running |
| Mouse wheel up/down | Increase/decrease magnification while the magnifier is visible |
| `C` | Copy the selected item from Preferences while the magnifier is visible |
| Right-click the magnifier | Open Preferences |
| Middle-click the magnifier | Reset zoom to the configured initial zoom |
| Tray icon, left-click | Toggle the magnifier |
| Tray icon, right-click | Open the tray menu |

## Preferences

- **Global hotkey:** defaults to `<ctrl>+<alt>+m`. Restart the application after changing it.
- **Window width/height:** size of the magnifier window in screen pixels.
- **Initial zoom:** starting magnification.
- **Maximum zoom:** maximum magnification, up to 32×.
- **Press C to copy:** choose image, LaTeX CMYK, LaTeX RGB, or plain RGB values.
- **Pixel scale:** show or hide the pixel scale and coordinates. Enabled by default.

## Start automatically with IceWM

Create an executable startup helper, for example `~/.local/bin/start-icewm-magnifier.sh`:

```bash
#!/bin/bash
APP="$HOME/Desktop/icewm_cursor_magnifier.py"
LOG_DIR="$HOME/.local/state"
LOG="$LOG_DIR/icewm-magnifier.log"

mkdir -p "$LOG_DIR"

# Avoid starting a second copy.
if pgrep -u "$(id -u)" -f '[i]cewm_cursor_magnifier.py' >/dev/null; then
    exit 0
fi

if [ -z "$DISPLAY" ]; then
    echo "$(date): ERROR: DISPLAY is not set." >> "$LOG"
    exit 1
fi

if [ ! -f "$APP" ]; then
    echo "$(date): ERROR: script not found: $APP" >> "$LOG"
    exit 1
fi

echo "$(date): Starting Cursor Magnifier." >> "$LOG"
nohup python3 "$APP" >> "$LOG" 2>&1 &
```

Make it executable:

```bash
chmod +x ~/.local/bin/start-icewm-magnifier.sh
```

Then add this line to `~/.icewm/startup`:

```bash
"$HOME/.local/bin/start-icewm-magnifier.sh" &
```

If `~/.icewm/startup` does not exist, create it. Make sure the Python interpreter used by `python3` has all required modules installed. Log output is written to `~/.local/state/icewm-magnifier.log`.

## Troubleshooting

- **No tray icon in IceWM:** the application needs an active notification-area/system-tray implementation. Check the IceWM taskbar configuration and whether a tray applet is running. Xfce and IceWM may use different tray setups.
- **Wheel capture fails:** the program uses X11 global grabs. Confirm that the session is X11, and check the error printed in the terminal.
- **Missing Python module:** install the missing dependency into the same Python environment used to launch the application.
- **Inspect the log:** `cat ~/.local/state/icewm-magnifier.log`

## Notes

This project is intended for X11 desktop sessions. The pixel scale measures source-screen pixels in the captured magnifier area, not physical millimetres or the magnifier window's own screen coordinates.

---

# Magyar

## Funkciók

- Keret nélküli nagyítóablak, amely követi az egérkurzort.
- **2× nagyítással** indul. Az egérgörgővel növelhető vagy csökkenthető a nagyítás a beállított maximumig.
- Ikon jelenik meg a rendszer értesítési területén. A menüből a nagyító megjeleníthető, elrejthető, megnyitható a Preferences, illetve kiléphetünk a programból.
- `Ctrl+Alt+M`: a nagyító megjelenítése vagy elrejtése.
- `Esc`: elrejti a nagyítót, de a program tovább fut.
- Amíg a nagyító látható, a `C` billentyű a Preferencesben kiválasztott adatot másolja:
  1. A nagyított képernyőrészletet képként.
  2. LaTeX `xcolor` CMYK-színkódot.
  3. LaTeX `xcolor` RGB-színkódot.
  4. Egyszerű RGB-értékeket, például `R=100, G=12, B=86`.
- Megjeleníti a mintavételezett képpont RGB- és CMYK-értékeit.
- Opcionális pixelbeosztás, amelynek origója a nagyított képterület **bal alsó sarka**. A jelölések 5 forrásképpontonként, a számértékek 10 képpontonként jelennek meg.
- A beállításokat a `~/.config/icewm-magnifier/config.json` fájlba menti.

## Követelmények

- Linux, **X11** grafikus munkamenettel. Wayland alatt a globális görgőfoglalás nem támogatott, a képernyőfelvétel és a gyorsbillentyűk működése is korlátozott lehet.
- Python 3
- PySide6
- pynput
- python-xlib
- Működő rendszer-tálca / értesítési terület.

A Python-modulokat ugyanabba a Python-környezetbe telepítsd, amellyel a programot indítod. Például:

```bash
python3 -m pip install --user PySide6 pynput python-xlib
```

Ha a Linux-disztribúció tiltja a `pip --user` használatát a rendszer-Pythonhoz, telepítsd a disztribúció csomagjait, vagy használj virtuális környezetet. Ne használj `sudo pip` parancsot.

## Indítás

Mentsd az `icewm_cursor_magnifier_english.py` fájlt (vagy nevezd át `icewm_cursor_magnifier.py` névre) egy megfelelő könyvtárba, majd futtasd:

```bash
python3 ~/Desktop/icewm_cursor_magnifier.py
```

Az ikonnak meg kell jelennie az értesítési területen. Ha a program azt jelzi, hogy nem érhető el rendszer-tálca, engedélyezni kell a megfelelő tálcaelemet vagy bővítményt az aktuális grafikus munkamenetben.

## Vezérlés

| Művelet | Eredmény |
|---|---|
| `Ctrl+Alt+M` | A nagyító megjelenítése vagy elrejtése |
| `Esc` | A nagyító elrejtése, a program futva marad |
| Egérgörgő fel/le | Nagyítás növelése/csökkentése, amíg a nagyító látható |
| `C` | A Preferencesben kiválasztott adat másolása, amíg a nagyító látható |
| Jobb kattintás a nagyítón | Preferences megnyitása |
| Középső kattintás a nagyítón | Visszaállás a beállított kezdő nagyításra |
| Bal kattintás a tálcaikonra | A nagyító kapcsolása |
| Jobb kattintás a tálcaikonra | A tálcamenü megnyitása |

## Preferences

- **Global hotkey:** alapértelmezése `<ctrl>+<alt>+m`. Módosítás után újra kell indítani a programot.
- **Window width/height:** a nagyítóablak mérete képernyő-pixelben.
- **Initial zoom:** kezdő nagyítás.
- **Maximum zoom:** maximális nagyítás, legfeljebb 32×.
- **Press C to copy:** a kép, a LaTeX CMYK, a LaTeX RGB vagy az egyszerű RGB-értékek közül választhatsz.
- **Pixel scale:** a pixelbeosztás és koordináták megjelenítése vagy elrejtése. Alapértelmezetten be van kapcsolva.

## Automatikus indítás IceWM alatt

Hozz létre egy futtatható indítószkriptet, például `~/.local/bin/start-icewm-magnifier.sh` néven:

```bash
#!/bin/bash
APP="$HOME/Desktop/icewm_cursor_magnifier.py"
LOG_DIR="$HOME/.local/state"
LOG="$LOG_DIR/icewm-magnifier.log"

mkdir -p "$LOG_DIR"

# Ne induljon el második példány.
if pgrep -u "$(id -u)" -f '[i]cewm_cursor_magnifier.py' >/dev/null; then
    exit 0
fi

if [ -z "$DISPLAY" ]; then
    echo "$(date): HIBA: nincs beállítva a DISPLAY." >> "$LOG"
    exit 1
fi

if [ ! -f "$APP" ]; then
    echo "$(date): HIBA: nem található a szkript: $APP" >> "$LOG"
    exit 1
fi

echo "$(date): Kurzor-nagyító indítása." >> "$LOG"
nohup python3 "$APP" >> "$LOG" 2>&1 &
```

Tedd futtathatóvá:

```bash
chmod +x ~/.local/bin/start-icewm-magnifier.sh
```

Ezután add hozzá ezt a sort a `~/.icewm/startup` fájlhoz:

```bash
"$HOME/.local/bin/start-icewm-magnifier.sh" &
```

Ha a `~/.icewm/startup` fájl még nem létezik, hozd létre. Ellenőrizd, hogy a `python3` által használt környezetben minden szükséges modul telepítve van-e. A napló a `~/.local/state/icewm-magnifier.log` fájlba kerül.

## Hibaelhárítás

- **Nincs tálcaikon IceWM alatt:** a programnak működő értesítési területre / system tray-re van szüksége. Ellenőrizd az IceWM tálcabeállításait és azt, hogy fut-e tálcaelem. Az Xfce és az IceWM eltérő tálcamegoldást használhat.
- **Nem működik a görgőfoglalás:** a program globális X11-es eseményfoglalást használ. Ellenőrizd, hogy X11 alatt fut-e a munkamenet, és nézd meg a terminál hibaüzenetét.
- **Hiányzó Python-modul:** telepítsd a hiányzó függőséget ugyanabba a Python-környezetbe, amellyel a programot indítod.
- **Napló megtekintése:** `cat ~/.local/state/icewm-magnifier.log`

## Megjegyzések

A program X11-es grafikus munkamenetekhez készült. A pixelbeosztás a nagyító által rögzített képernyőrészlet forrásképpontjait méri, nem fizikai millimétereket és nem a nagyítóablak saját képernyő-koordinátáit.

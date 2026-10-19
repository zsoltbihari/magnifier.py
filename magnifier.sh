
#!/bin/bash

# Kurzor-nagyító automatikus indítása IceWM alatt
# AV Linux / Debian / X11

APP="/usr/local/share/cursor_magnifier.py"
LOG_DIR="$HOME/.local/state"
LOG="$LOG_DIR/icewm-magnifier.log"

mkdir -p "$LOG_DIR"

# Ne induljon el kétszer.
if pgrep -u "$(id -u)" -f 'cursor_magnifier.py' >/dev/null; then
    exit 0
fi

# A grafikus környezet ellenőrzése.
if [ -z "$DISPLAY" ]; then
    echo "$(date): HIBA: nincs DISPLAY beállítva." >> "$LOG"
    exit 1
fi

# Python ellenőrzése.
PYTHON="$(command -v python3)"

if [ -z "$PYTHON" ]; then
    echo "$(date): HIBA: python3 nem található a PATH-ban." >> "$LOG"
    exit 1
fi

if [ ! -f "$APP" ]; then
    echo "$(date): HIBA: nem található: $APP" >> "$LOG"
    exit 1
fi

echo "$(date): Nagyító indítása: $PYTHON $APP" >> "$LOG"

# Háttérben indul, az IceWM-et nem blokkolja.
nohup "$PYTHON" "$APP" >> "$LOG" 2>&1 &

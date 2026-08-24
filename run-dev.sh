#!/bin/bash

# Finn ut hvem som faktisk eier mappen / kjører skriptet
if [ "$EUID" -eq 0 ]; then
    # Hvis kjørt med sudo, bruk SUDO_USER eller fall tilbake til den som eier mappen
    TARGET_USER="${SUDO_USER:-$(stat -c '%U' .)}"
else
    # Hvis kjørt som vanlig bruker, bruk den som er logget inn
    TARGET_USER="$USER"
fi

pkill -9 -f Xorg
pkill -9 -f openbox
pkill -9 -f python3
pkill -9 -f webview

VENV_DIR="/home/$TARGET_USER/kiosk-env"
PROJECT_ROOT="$(pwd)"

echo "[+] Bruker konto: $TARGET_USER"

echo "[+] Sjekker og setter opp venv med system-site-packages..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
fi

echo "[+] Installerer avhengigheter..."
if [ -f "requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi
"$VENV_DIR/bin/pip" install pywebview Pillow PyGObject

# Prøv å starte Xorg i bakgrunnen hvis den ikke allerede kjører
if ! pgrep -f "Xorg :0" > /dev/null; then
    echo "[+] Starter Xorg på :0..."
    Xorg :0 vt1 &
    XORG_PID=$!
    sleep 1
fi

echo "[+] Setter opp miljøvariabler..."
export DISPLAY=:0
export XAUTHORITY="/home/$TARGET_USER/.Xauthority"
export PYTHONPATH="$PROJECT_ROOT/src"

if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
    export DBUS_SESSION_BUS_PID
fi

# Gi tillatelse lokalt slik at skjermen godtar tegning
xhost +local:$TARGET_USER 2>/dev/null

# Start Openbox i bakgrunnen slik at vindusreglene blir aktivert
echo "[+] Starter Openbox vindushåndterer..."
if [ "$EUID" -eq 0 ]; then
    su - "$TARGET_USER" -c "export DISPLAY=:0; export XAUTHORITY='/home/$TARGET_USER/.Xauthority'; openbox &"
else
    openbox &
fi
sleep 1

echo "[+] Starter pykiosk..."
# Kjør appen direkte med venv sin python, og ta med alle argumenter ($@ slik at URL kan sendes med)
"$VENV_DIR/bin/python3" -m pykiosk.app "$@"

# Rydd opp Openbox og Xorg når skriptet avslutter
echo "[+] Rydder opp prosesser..."
pkill -x openbox 2>/dev/null
if [ ! -z "$XORG_PID" ]; then
    kill $XORG_PID 2>/dev/null
fi
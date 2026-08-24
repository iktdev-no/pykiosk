#!/bin/bash

# Finn ut hvem som faktisk eier mappen / kjører skriptet
if [ "$EUID" -eq 0 ]; then
    # Hvis kjørt med sudo, bruk SUDO_USER eller fall tilbake til kammich
    TARGET_USER="${SUDO_USER:-kammich}"
else
    # Hvis kjørt som vanlig bruker, bruk den som er logget inn
    TARGET_USER="$USER"
fi

VENV_DIR="/home/$TARGET_USER/kiosk-env"
PROJECT_ROOT="$(pwd)"

echo "[+] Bruker konto: $TARGET_USER"

echo "[+] Sjekker og setter opp venv..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
fi

echo "[+] Installerer avhengigheter..."
if [ -f "requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi
"$VENV_DIR/bin/pip" install pywebview Pillow

# Prøv å starte Xorg i bakgrunnen hvis brukeren har rettigheter (eller hoppet over hvis den alt kjører)
if ! pgrep -f "Xorg :0" > /dev/null; then
    echo "[+] Starter Xorg på :0..."
    Xorg :0 vt1 &
    XORG_PID=$!
    sleep 1
fi

echo "[+] Setter opp miljøvariabler og starter pykiosk..."
export DISPLAY=:0
export XAUTHORITY="/home/$TARGET_USER/.Xauthority"
export PYTHONPATH="$PROJECT_ROOT/src"

# Gi tillatelse lokalt slik at skjermen godtar tegning
xhost +local:$TARGET_USER 2>/dev/null

# Kjør appen direkte
"$VENV_DIR/bin/python3" -m pykiosk.app

# Rydd opp Xorg hvis vi startet den i dette skriptet
if [ ! -z "$XORG_PID" ]; then
    echo "[+] Avslutter Xorg..."
    kill $XORG_PID 2>/dev/null
fi
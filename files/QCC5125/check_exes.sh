#!/bin/bash

# --- Skript zur Analyse von .exe-Dateien ---
# Durchsucht das aktuelle Verzeichnis rekursiv nach .exe-Dateien,
# extrahiert Architektur (32/64-Bit) und min. Windows-Version
# und speichert die Ergebnisse in einer CSV-Datei.

# Name der Ausgabedatei
OUTPUT_FILE="exe_analyse.csv"

# Prüfen, ob das benötigte Werkzeug 'x86_64-w64-mingw32-objdump' installiert ist
if ! command -v x86_64-w64-mingw32-objdump &> /dev/null; then
    echo "Fehler: 'x86_64-w64-mingw32-objdump' nicht gefunden."
    echo "Bitte installiere es zuerst mit dem Befehl:"
    echo "sudo apt update && sudo apt install binutils-mingw-w64"
    exit 1
fi

# CSV-Header in die Datei schreiben (alte Datei wird überschrieben)
echo "Dateipfad;Architektur;Min. OS Version;Windows Name" > "$OUTPUT_FILE"

echo "Starte die Analyse... Ergebnisse werden in '$OUTPUT_FILE' gespeichert."

# Finde alle .exe-Dateien (Groß-/Kleinschreibung ignorieren) und verarbeite sie
# 'find' ist robuster für Dateinamen mit Leerzeichen als 'ls' oder '*'
find . -type f -iname "*.exe" | while IFS= read -r filepath; do
    echo "Verarbeite: $filepath"

    # Führe objdump aus und leite Fehler um, falls es keine gültige PE-Datei ist
    info=$(x86_64-w64-mingw32-objdump -p "$filepath" 2>/dev/null)

    # Extrahiere die relevanten Informationen
    machine=$(echo "$info" | grep 'Machine:' | awk '{print $2}')
    version=$(echo "$info" | grep 'Subsystem Version:' | awk '{print $3}')

    # Wenn keine Infos gefunden wurden (z.B. beschädigte Datei), überspringe sie
    if [[ -z "$machine" || -z "$version" ]]; then
        echo "\"$filepath\";Fehler;Konnte nicht analysiert werden;-" >> "$OUTPUT_FILE"
        continue
    fi

    # Übersetze die Maschinen-Architektur
    arch="Unbekannt"
    case "$machine" in
        "x86-64" | "I86_64")
            arch="64-Bit"
            ;;
        "i386")
            arch="32-Bit"
            ;;
    esac

    # Übersetze die OS-Version in einen lesbaren Namen
    win_name="Unbekannt"
    case "$version" in
        "10.0"*) win_name="Windows 10 / 11" ;;
        "6.3"*)  win_name="Windows 8.1" ;;
        "6.2"*)  win_name="Windows 8" ;;
        "6.1"*)  win_name="Windows 7" ;;
        "6.0"*)  win_name="Windows Vista" ;;
        "5.2"*)  win_name="Windows XP 64-Bit / Server 2003" ;;
        "5.1"*)  win_name="Windows XP" ;;
        "5.0"*)  win_name="Windows 2000" ;;
    esac

    # Schreibe die formatierte Zeile in die CSV-Datei
    # Anführungszeichen um die Werte sorgen für korrekte Darstellung, auch bei Leerzeichen
    echo "\"$filepath\";\"$arch\";\"$version\";\"$win_name\"" >> "$OUTPUT_FILE"

done

echo "Analyse abgeschlossen. Die Ergebnisse stehen in der Datei '$OUTPUT_FILE'."

#!/bin/bash

# --- Skript zur Analyse von .exe-Dateien (Version 2) ---
# Durchsucht das aktuelle Verzeichnis rekursiv nach .exe-Dateien,
# extrahiert Architektur (32/64-Bit) und min. Windows-Version
# und speichert die Ergebnisse in einer CSV-Datei.
# Diese Version ist robuster und kann verschiedene PE-Header-Formate lesen.

OUTPUT_FILE="exe_analyse.csv"

if ! command -v x86_64-w64-mingw32-objdump &> /dev/null; then
    echo "Fehler: 'x86_64-w64-mingw32-objdump' nicht gefunden."
    echo "Bitte installiere es zuerst mit dem Befehl:"
    echo "sudo apt update && sudo apt install binutils-mingw-w64"
    exit 1
fi

echo "Dateipfad;Architektur;Min. OS Version;Windows Name" > "$OUTPUT_FILE"

echo "Starte die Analyse (Version 2)... Ergebnisse werden in '$OUTPUT_FILE' gespeichert."

find . -type f -iname "*.exe" | while IFS= read -r filepath; do
    echo "Verarbeite: $filepath"

    info=$(x86_64-w64-mingw32-objdump -p "$filepath" 2>/dev/null)

    # --- Verbesserte Logik zum Extrahieren der Informationen ---
    machine=""
    version=""

    # VERSUCH 1: Standard-Format
    machine=$(echo "$info" | grep 'Machine:' | awk '{print $2}')
    version=$(echo "$info" | grep 'Subsystem Version:' | awk '{print $3}')

    # VERSUCH 2 (FALLBACK): Alternatives Format
    if [[ -z "$machine" ]]; then
        machine_line=$(echo "$info" | grep 'file format pei-')
        if [[ "$machine_line" == *"i386"* ]]; then
            machine="i386"
        elif [[ "$machine_line" == *"x86-64"* ]]; then
            machine="x86-64"
        fi
    fi

    if [[ -z "$version" ]]; then
        major_v=$(echo "$info" | grep 'MajorSubsystemVersion' | awk '{print $2}')
        minor_v=$(echo "$info" | grep 'MinorSubsystemVersion' | awk '{print $2}')
        if [[ -n "$major_v" && -n "$minor_v" ]]; then
            version="$major_v.$minor_v"
        fi
    fi
    # --- Ende der verbesserten Logik ---

    if [[ -z "$machine" || -z "$version" ]]; then
        echo "\"$filepath\";Fehler;Konnte nicht analysiert werden;-" >> "$OUTPUT_FILE"
        continue
    fi

    arch="Unbekannt"
    case "$machine" in
        "x86-64" | "I86_64")
            arch="64-Bit" ;;
        "i386")
            arch="32-Bit" ;;
    esac

    win_name="Unbekannt"
    # Die Versionen werden jetzt als "5.0" etc. korrekt zusammengesetzt
    case "$version" in
        "10.0"*) win_name="Windows 10 / 11" ;;
        "6.3"*)  win_name="Windows 8.1" ;;
        "6.2"*)  win_name="Windows 8" ;;
        "6.1"*)  win_name="Windows 7" ;;
        "6.0"*)  win_name="Windows Vista" ;;
        "5.2"*)  win_name="Windows XP 64-Bit / Server 2003" ;;
        "5.1"*)  win_name="Windows XP" ;;
        "5.0"*)  win_name="Windows 2000" ;; # Deine Dateien werden wahrscheinlich hier landen
    esac

    echo "\"$filepath\";\"$arch\";\"$version\";\"$win_name\"" >> "$OUTPUT_FILE"

done

echo "Analyse abgeschlossen. Die Ergebnisse stehen in der Datei '$OUTPUT_FILE'."

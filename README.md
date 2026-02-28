# Desk

A custom-built smart L-shaped desk with deep Home Assistant integration. The project spans hardware design (custom PCBs), embedded firmware (ESP32-S3), and software services, all tied together via MQTT.

## Overview

This repository contains all the design files and software for a DIY smart desk ecosystem. The desk houses a dedicated electronics enclosure that handles audio routing, thermal management, environmental monitoring, and a media display — all controllable from Home Assistant.

```
desk/
├── PCB/            # Main KiCad PCB & schematics (ESP32-S3, DSP, DACs, PSU, …)
├── HID/            # Input device PCBs (rotary encoders, HID controller)
├── audio.md        # Audio matrix design document
├── fan_control.md  # Fan controller design document
├── Raspi/          # MPRIS-to-MQTT bridge service (Python, systemd)
└── UI/Docker/      # Media artwork generator & HTTP server (Docker)
```

---

## Sub-Projects

| | |
|---|---|
| [Audio Matrix](audio.md) | 6-in / 4-out digital audio matrix at 96 kHz / 24-bit. ADAU1451 DSP with ASRC, controlled by ESP32-S3 over I²C. Sources include USB, S/PDIF, Bluetooth (LDAC), I²S, and analog line-in. |
| [Fan Controller](fan_control.md) | ESP32-S3 reads all component temperatures via a TI TMP468 and the Raspberry Pi's CPU temp over I²C, then drives an Arctic P8 Max PWM fan based on the system hotspot. |
| [Desk GUI](https://github.com/MaizeShark/desk-gui) | ESP32-S3 firmware (PlatformIO / LVGL) for the 4-inch touchscreen control panel. Shows current track and album art, Spotify playback controls, and drives 12× addressable RGB LEDs. |
| [MPRIS → MQTT](Raspi/) | Python systemd service on the Raspberry Pi that watches the active media player via D-Bus and publishes playback state to MQTT. See [`Raspi/README.md`](Raspi/README.md). |
| [Media Artwork Service](UI/Docker/) | Dockerised service that fetches album art from Spotify / Jellyfin, composites a 480×320 image, serves it over HTTP, and publishes the URL to MQTT. See [`UI/Docker/README.md`](UI/Docker/README.md). |

---

## Hardware

The main PCB (`PCB/Tisch.kicad_pcb`) integrates all of the above subsystems onto a single board. Schematics are split into logical sheets:

| File | Content |
|---|---|
| `esp32.kicad_sch` | Main ESP32-S3 controller |
| `ADAU1451.kicad_sch` | DSP |
| `dac.kicad_sch` | PCM5122 DAC outputs |
| `adc.kicad_sch` | PCM1809 ADC input |
| `QCC5125.kicad_sch` | Bluetooth RX |
| `bm83.kicad_sch` | Bluetooth TX |
| `spdif.kicad_sch` | S/PDIF receiver |
| `raspi.kicad_sch` | Raspberry Pi interface |
| `fan.kicad_sch` | Fan control circuit |
| `psu.kicad_sch` | Power supply |
| `display.kicad_sch` | Display connector |
| `hid.kicad_sch` | HID / encoder inputs |

The `HID/` directory contains a separate PCB for the rotary encoder input device.

---

## License

This project is licensed under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for details.

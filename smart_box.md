# Project: Ultimate Indoor Environmental Monitor

## 1. Project Goal

To design and build a comprehensive, multi-sensor device for monitoring indoor environmental conditions, with a focus on air quality, presence detection, and climate. The device will serve as the primary data source for a larger smart home ecosystem controlled by Home Assistant, providing data to automate lighting, heating, and custom alerts.

This document outlines the final component selection, the rationale behind each choice, and the intended system architecture.

---

## 2. Final Bill of Materials (BoM)

This table represents the final, optimized sensor suite for the project, balancing performance, cost, and relevance to the target environment (a bedroom/office/tinkering space).

| Category              | Selected Sensor / Module   | Primary Purpose                                       | Key Decision Rationale                                                                        |
| :-------------------- | :------------------------- | :---------------------------------------------------- | :-------------------------------------------------------------------------------------------- |
| **Ventilation**       | **Sensirion SCD41**        | **True CO2**, Temperature, Humidity                   | **The most critical sensor.** Provides a scientific measurement of air stuffiness (ventilation quality), which is essential for health and cognitive performance. Chosen over eCO2 sensors for its accuracy. |
| **Pollutants**        | **ENS160 + AHT21 Module**  | **VOCs, Odors (TVOC), eCO2, AQI**, Temp, Hum     | The best sensor for detecting chemical pollutants (fumes from soldering, cleaning, electronics). The integrated AHT21 provides the necessary temp/hum compensation for the ENS160's algorithm. |
| **Presence**          | **Hi-Link HLK-LD2450**     | **Multi-Target Positional Tracking** (X, Y Coords)      | Provides rich positional data to enable advanced, context-aware automation (e.g., zone-based lighting). Chosen over simpler presence sensors for its advanced capabilities. |
| **Motion Trigger**    | **AM312**                  | **Low-Power Motion Detection**                        | Acts as an ultra-low-power "wake-up" trigger for the system, allowing the main microcontroller and LD2450 to sleep, saving energy. Chosen for its extremely low cost and power draw. |
| **Weather/Climate**   | **Bosch BME280**           | **Barometric Pressure**                               | Adds a weather-forecasting dimension by tracking pressure trends. A low-cost, high-value addition for a complete environmental picture. Its Temp/Hum functions will be secondary. |
| **Lighting**          | **Rohm BH1750**            | **Ambient Light (Lux)**                               | Provides a direct measurement of light intensity in Lux. Perfect for auto-adjusting display brightness and logging day/night cycles. Chosen as the industry standard for its accuracy and ease of use. |

---

## 3. System Architecture & Integration

This sensor hub is not a standalone device. It is a critical node in a larger smart room ecosystem managed by **Home Assistant**.

-   **Sensor Hub (This Project):** Will likely run **ESPHome** on an ESP32 for seamless integration with Home Assistant over Wi-Fi. It will collect data from all I2C/UART sensors and publish it.
-   **Central Controller (The Brain):** **Home Assistant** will receive all sensor data, log it, and run automations.
-   **Actuators (The Muscles):**
    -   **Lighting:** `Aqara H1 EU` (Zigbee), `IKEA TRÅDFRI Driver` (Zigbee), `WLED RGBWW Strip` (Wi-Fi).
    -   **Heating:** `Moes BRT-100-TRV` (Zigbee).
-   **Alerts & Notifications:**
    -   A hacked **Amazon Echo** for voice alerts (e.g., "Open the window!").
    -   Mobile push notifications via Home Assistant.
-   **Physical Interface (The Command Center):** The custom-built L-shaped desk project with its ESP32-S3, LVGL display, and audio matrix will act as the primary physical control and visualization interface, pulling data from and sending commands to Home Assistant.

---

## 4. Detailed Sensor Decision Log

This section details the comparisons made and the rationale for choosing or rejecting specific components.

### 4.1. Air Quality Sensors

-   **True CO2 (Ventilation):** The **SCD41** was chosen for its ability to measure actual CO2 concentration. This is fundamentally different from the **ENS160's eCO2** reading, which is an inference based on VOCs. For monitoring air stuffiness from human respiration, a true CO2 sensor is non-negotiable.
-   **VOCs (Pollutants):** The **ENS160** was chosen as a best-in-class sensor for detecting a broad range of Volatile Organic Compounds, making it ideal for identifying fumes from soldering, new electronics, or cleaning products.
-   **Particulate Matter (PM2.5):** The **Plantower PMS5003** was considered and **REJECTED**.
    -   **Rationale:** The target environment is a bedroom in a rural town with no major indoor sources of particulates (no smoking, candles, or heavy cooking). The primary occasional source (soldering) is better managed by active ventilation. The ~€14 cost was better allocated to the more critical SCD41.

### 4.2. Presence and Motion

-   **Primary Presence:** The **HLK-LD2450** was chosen for its advanced multi-target positional tracking. This enables sophisticated, zone-based automations that are impossible with simple presence sensors.
-   **Wake-up Trigger:** The **AM312** PIR sensor was chosen as the system's low-power trigger.
    -   **Rationale:** At ~€0.94, its cost-effectiveness is unbeatable. Its primary role is to wake the ESP32 from deep sleep, which then powers on the more power-hungry LD2450. The professional-grade **EKMC1601111** was **REJECTED** due to its ~€9 price, which was deemed overkill for this specific role.

### 4.3. Climate Sensors (Temp, Hum, Pressure)

-   A combined approach was decided upon:
    1.  The **AHT21** (on the ENS160 module) will be the primary source for **Temperature & Humidity** readings, as this data is directly used by the ENS160 for compensation.
    2.  A separate **BME280** will be added for the sole purpose of measuring **Barometric Pressure**.
-   **Rationale:** This provides the best of all worlds. We get the necessary inputs for the ENS160, plus the added weather data from the BME280 for a minimal cost of ~€2.50. Other sensors like the **SHTC3** were considered but offered no significant advantage over this cost-effective combination.

### 4.4. Other Sensors

-   **Ambient Light:** The **BH1750** was chosen as it is the de-facto standard for hobbyist projects. It provides a direct, accurate reading in Lux, which is far superior to a simple Photoresistor (LDR). More advanced sensors like the TSL2591 were deemed overkill and not worth the extra cost.
-   **Sound/Microphone:** A microphone was considered and **REJECTED**.
    -   **Rationale:** While technically possible to add for free (parts on hand), there was no compelling use case for ambient sound level data in the target environment. The project is focused on air quality and environmental factors, and a microphone did not add valuable, actionable data to this core mission.
-   **Threat/Gas Sensors (MQ Series):** Sensors like the **MQ-2 (Smoke)** were considered and **REJECTED**.
    -   **Rationale:** The initial idea of a "yelling Echo" was clarified. The goal is to create alerts for poor air quality (high CO2/VOCs), not for new threats like smoke. The SCD41 and ENS160 are the correct, high-precision triggers for this alert, making an MQ sensor redundant and less reliable for this purpose.

---

## 5. Key Automation Examples

1.  **Intelligent Ventilation Alerts:**
    -   **Trigger:** `SCD41 CO2 > 1000 ppm` OR `ENS160 AQI > 3`.
    -   **Condition:** `HLK-LD2450 Presence = Occupied`.
    -   **Action:** Send a voice alert to the Amazon Echo: "Air quality is decreasing. Please open a window for ventilation."

2.  **Presence-Aware Lighting:**
    -   **Trigger:** `AM312 detects motion`.
    -   **Action:** Wake the system.
    -   **Logic:** `HLK-LD2450` detects presence and X/Y coordinates.
    -   **Action:** Home Assistant turns on the `Aqara H1` switch and sets the `WLED` strip to a specific scene based on the user's location (e.g., "Soldering Scene" or "PC Scene").

3.  **Smart Display Dimming:**
    -   **Trigger:** `BH1750 Lux level changes`.
    -   **Action:** The firmware on the main sensor unit (or the Desk UI) adjusts the screen brightness automatically for comfortable viewing day or night.

4.  **Accurate Climate Control:**
    -   **Trigger:** `AHT21 room temperature` is used by Home Assistant as the input for a generic thermostat controller.
    -   **Action:** The controller sends commands to the `Moes TRV` to regulate the radiator, providing more accurate heating than the TRV's built-in sensor.

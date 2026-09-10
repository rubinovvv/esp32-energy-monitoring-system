# ESP32 Energy Monitoring System

An IoT-based real-time energy monitoring system for a single-phase 230 V AC load. The project combines an **ESP32 DevKit V1**, a **PZEM-004T** energy meter, a **Python HTTP server**, **MySQL** storage, and a responsive **HTML/CSS/JavaScript dashboard**.

This repository is based on my master's dissertation project, *Instrument virtual de monitorizare a parametrilor energetici* (2026).

## What it does

The system measures and visualizes:

- Voltage (V)
- Current (A)
- Active power (W)
- Energy consumption (kWh)
- Frequency (Hz)
- Power factor

The ESP32 reads the PZEM-004T over a hardware serial interface and sends a JSON payload to the Python server over Wi-Fi using HTTP POST approximately every two seconds. The server stores both raw values and a moving average based on the latest five samples in MySQL.

The dashboard polls the server for the latest averaged values and provides live visualization, session statistics, estimated energy cost, and historical measurements.

## Architecture

```text
230 V AC load
      |
      v
  PZEM-004T
      |
      | UART
      v
 ESP32 DevKit V1
      |
      | Wi-Fi / HTTP / JSON
      v
 Python HTTP server
      |
      +------> MySQL
      |
      v
 Web dashboard
```

## Repository structure

```text
esp32-energy-monitoring-system/
├── firmware/
│   └── esp32_energy_monitor/
│       ├── esp32_energy_monitor.ino
│       └── secrets.example.h
├── server/
│   ├── server.py
│   ├── requirements.txt
│   └── .env.example
├── web/
│   └── index.html
├── .gitignore
└── README.md
```

## Tech stack

**Embedded / hardware**

- ESP32 DevKit V1
- PZEM-004T
- UART
- Arduino framework / C++

**Communication**

- Wi-Fi
- HTTP
- JSON

**Backend / data**

- Python
- MySQL
- `mysql-connector-python`

**Frontend**

- HTML
- CSS
- Vanilla JavaScript
- HTML Canvas for charts

## Data flow

A typical payload sent by the ESP32 is:

```json
{
  "voltage": 230.1,
  "current": 1.20,
  "power": 260.0,
  "energy": 0.125,
  "frequency": 50.0,
  "power_factor": 0.95
}
```

The backend exposes:

- `POST /data` — receives a measurement from the ESP32
- `GET /data` — returns the latest averaged measurement
- `GET /history?range=30m` — returns historical measurements
- `GET /history?range=1h`
- `GET /history?range=3h`
- `GET /history?range=1d`
- `GET /history?start=YYYY-MM-DDTHH:MM&end=YYYY-MM-DDTHH:MM` — custom range
- `GET /` — serves the dashboard

## Backend setup

Requirements: Python 3.10+ and access to a MySQL database.

```bash
cd server
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your local environment file from the example:

```text
server/.env.example -> server/.env
```

Fill in your own MySQL credentials:

```env
DB_HOST=your-mysql-host
DB_DATABASE=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_PORT=3306
SERVER_PORT=8000
```

Start the server from the repository root:

```bash
python server/server.py
```

Then open:

```text
http://localhost:8000
```

## ESP32 setup

The firmware requires these Arduino libraries:

- `WiFi`
- `HTTPClient`
- `PZEM004Tv30`

The project uses:

- PZEM RX: GPIO 27
- PZEM TX: GPIO 26

Copy:

```text
firmware/esp32_energy_monitor/secrets.example.h
```

to:

```text
firmware/esp32_energy_monitor/secrets.h
```

and configure your local values:

```cpp
#define WIFI_NAME "your-wifi-name"
#define WIFI_PASSWORD "your-wifi-password"
#define SERVER_URL "http://YOUR_SERVER_IP:8000/data"
```

`secrets.h` is ignored by Git and must not be committed.

## Dashboard features

- Live server connection status
- Current averaged power view
- Voltage, current, power, energy and frequency cards
- Power factor gauge
- Live chart for power, voltage, current or energy
- Session statistics
- Configurable electricity tariff and estimated cost
- Historical data from MySQL
- Preset and custom history ranges
- Informational alerts for unusual voltage, low power factor or high power

## Validation

The prototype was evaluated with different types of household loads, including an LED lamp, a laptop power supply, an electric heater and a hair dryer. Testing also covered Wi-Fi loss, invalid PZEM readings, server interruption and continuous operation.

## Security notes

No database password, Wi-Fi password, or private network address is committed to this repository. Runtime credentials are kept in ignored local configuration files.

If credentials have previously been committed or shared publicly, rotate them instead of only deleting them from the latest file version.

## Safety

> **Warning:** this project involves 230 V AC mains voltage. It is an experimental monitoring prototype, not a certified electricity meter and not suitable for billing. Work involving mains voltage should only be performed by a competent person using appropriate electrical protection and safe isolation procedures.

## Academic context

This project was developed as part of a master's dissertation in **Sisteme Informatice de Monitorizare a Mediului (SIMM)** at the Technical University "Gheorghe Asachi" of Iași, 2026.

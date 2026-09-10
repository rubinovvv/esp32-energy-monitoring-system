import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mysql.connector
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
WEB_DIR = PROJECT_DIR / "web"
INDEX_FILE = WEB_DIR / "index.html"

load_dotenv(BASE_DIR / ".env")

PORT = int(os.getenv("SERVER_PORT", "8000"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_DATABASE"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", "3306")),
}


# Last 5 raw measurements received from ESP32.
last_raw_values = []

# Initial values displayed until the ESP32 sends the first real measurement.
current_average_data = {
    "voltage": 230.0,
    "current": 1.20,
    "power": 260.0,
    "energy": 0.125,
    "frequency": 50.0,
    "power_factor": 0.95,
    "last_update": None,
    "samples_averaged": 0,
}


def current_time():
    return datetime.now()


def to_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def validate_database_config():
    missing = [
        name
        for name, value in {
            "DB_HOST": DB_CONFIG["host"],
            "DB_DATABASE": DB_CONFIG["database"],
            "DB_USER": DB_CONFIG["user"],
            "DB_PASSWORD": DB_CONFIG["password"],
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing database configuration: " + ", ".join(missing) +
            ". Copy server/.env.example to server/.env and fill in the values."
        )


def get_connection():
    validate_database_config()
    return mysql.connector.connect(**DB_CONFIG)


def init_database():
    query = """
    CREATE TABLE IF NOT EXISTS energy_measurements (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        measured_at DATETIME NOT NULL,

        raw_voltage DECIMAL(10, 3),
        raw_current DECIMAL(10, 4),
        raw_power DECIMAL(10, 3),
        raw_energy DECIMAL(14, 6),
        raw_frequency DECIMAL(10, 3),
        raw_power_factor DECIMAL(8, 4),

        avg_voltage DECIMAL(10, 3),
        avg_current DECIMAL(10, 4),
        avg_power DECIMAL(10, 3),
        avg_energy DECIMAL(14, 6),
        avg_frequency DECIMAL(10, 3),
        avg_power_factor DECIMAL(8, 4),

        samples_averaged INT NOT NULL,

        INDEX idx_measured_at (measured_at)
    )
    """
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def normalize_measurement(raw_data):
    return {
        "voltage": to_float(raw_data.get("voltage")),
        "current": to_float(raw_data.get("current")),
        "power": to_float(raw_data.get("power")),
        "energy": to_float(raw_data.get("energy")),
        "frequency": to_float(raw_data.get("frequency")),
        "power_factor": to_float(raw_data.get("power_factor", raw_data.get("pf"))),
    }


def average_last_values():
    if not last_raw_values:
        return {
            "voltage": 0.0,
            "current": 0.0,
            "power": 0.0,
            "energy": 0.0,
            "frequency": 0.0,
            "power_factor": 0.0,
            "samples_averaged": 0,
        }

    count = len(last_raw_values)
    averaged = {}

    for key in ["voltage", "current", "power", "energy", "frequency", "power_factor"]:
        averaged[key] = sum(item[key] for item in last_raw_values) / count

    averaged["samples_averaged"] = count
    return averaged


def insert_measurement(raw_data, average_data, measured_at):
    query = """
    INSERT INTO energy_measurements (
        measured_at,
        raw_voltage, raw_current, raw_power, raw_energy, raw_frequency, raw_power_factor,
        avg_voltage, avg_current, avg_power, avg_energy, avg_frequency, avg_power_factor,
        samples_averaged
    ) VALUES (
        %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s
    )
    """

    values = (
        measured_at,
        raw_data["voltage"],
        raw_data["current"],
        raw_data["power"],
        raw_data["energy"],
        raw_data["frequency"],
        raw_data["power_factor"],
        average_data["voltage"],
        average_data["current"],
        average_data["power"],
        average_data["energy"],
        average_data["frequency"],
        average_data["power_factor"],
        average_data["samples_averaged"],
    )

    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(query, values)
        connection.commit()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def get_history(query_params):
    allowed_ranges = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "3h": timedelta(hours=3),
        "1d": timedelta(days=1),
    }

    range_value = query_params.get("range", ["30m"])[0]
    start_value = query_params.get("start", [None])[0]
    end_value = query_params.get("end", [None])[0]

    if start_value and end_value:
        start_dt = datetime.fromisoformat(start_value.replace("T", " "))
        end_dt = datetime.fromisoformat(end_value.replace("T", " "))
    else:
        delta = allowed_ranges.get(range_value, allowed_ranges["30m"])
        end_dt = current_time()
        start_dt = end_dt - delta

    sql = """
    SELECT
        id,
        measured_at,
        raw_voltage,
        raw_current,
        raw_power,
        raw_energy,
        raw_frequency,
        raw_power_factor,
        avg_voltage,
        avg_current,
        avg_power,
        avg_energy,
        avg_frequency,
        avg_power_factor,
        samples_averaged
    FROM energy_measurements
    WHERE measured_at BETWEEN %s AND %s
    ORDER BY measured_at ASC
    LIMIT 1000
    """

    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, (start_dt, end_dt))
        rows = cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

    return {
        "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "rows": [
            {key: json_safe(value) for key, value in row.items()}
            for row in rows
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def send_response_body(self, body, content_type, status=200):
        if not isinstance(body, str):
            body = json.dumps(body, ensure_ascii=False)

        body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/data":
            self.send_response_body(current_average_data, "application/json")
            return

        if parsed_url.path == "/history":
            try:
                query_params = parse_qs(parsed_url.query)
                history = get_history(query_params)
                self.send_response_body(history, "application/json")
            except Exception as error:
                self.send_response_body(
                    {"error": str(error)},
                    "application/json",
                    500,
                )
            return

        try:
            self.send_response_body(INDEX_FILE.read_text(encoding="utf-8"), "text/html; charset=utf-8")
        except FileNotFoundError:
            self.send_response_body("web/index.html was not found", "text/plain", 404)

    def do_POST(self):
        global current_average_data

        parsed_url = urlparse(self.path)

        if parsed_url.path != "/data":
            self.send_response_body("Route not found", "text/plain", 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("Request body is empty")

            received_json = json.loads(self.rfile.read(length))
            measured_at = current_time()

            raw_data = normalize_measurement(received_json)

            last_raw_values.append(raw_data)
            if len(last_raw_values) > 5:
                last_raw_values.pop(0)

            average_data = average_last_values()
            average_data["last_update"] = measured_at.strftime("%Y-%m-%d %H:%M:%S")

            insert_measurement(raw_data, average_data, measured_at)

            current_average_data = average_data

            print("Raw data received:", raw_data)
            print(
                "Average of last",
                average_data["samples_averaged"],
                "measurements:",
                current_average_data,
            )

            self.send_response_body("OK", "text/plain")
        except Exception as error:
            self.send_response_body(str(error), "text/plain", 400)


if __name__ == "__main__":
    print("Initializing MySQL table...")
    init_database()

    print(f"Server running at http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

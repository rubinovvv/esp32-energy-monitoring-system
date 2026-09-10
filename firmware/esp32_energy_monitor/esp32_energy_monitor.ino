#include <WiFi.h>
#include <HTTPClient.h>
#include <PZEM004Tv30.h>
#include "secrets.h"

#define PZEM_RX_PIN 27
#define PZEM_TX_PIN 26

PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);

void connectToWiFi() {
  Serial.println();
  Serial.print("Conectare la Wi-Fi: ");
  Serial.println(WIFI_NAME);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Conectat la Wi-Fi!");
    Serial.print("IP ESP32: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Nu s-a putut conecta la Wi-Fi.");
    Serial.print("Status WiFi: ");
    Serial.println(WiFi.status());
  }
}

void sendDataToServer(
  float voltage,
  float current,
  float power,
  float energy,
  float frequency,
  float powerFactor
) {
  String json = "{";
  json += "\"voltage\":" + String(voltage, 1) + ",";
  json += "\"current\":" + String(current, 2) + ",";
  json += "\"power\":" + String(power, 1) + ",";
  json += "\"energy\":" + String(energy, 3) + ",";
  json += "\"frequency\":" + String(frequency, 1) + ",";
  json += "\"power_factor\":" + String(powerFactor, 2);
  json += "}";

  WiFiClient client;
  HTTPClient http;

  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  int responseCode = http.POST(json);

  Serial.println("JSON trimis:");
  Serial.println(json);
  Serial.print("Raspuns server: ");
  Serial.println(responseCode);

  if (responseCode < 0) {
    Serial.print("Eroare HTTP: ");
    Serial.println(http.errorToString(responseCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectToWiFi();

  Serial.println("Pornire citire PZEM-004T.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi deconectat. Reincerc conectarea.");
    connectToWiFi();
    delay(2000);
    return;
  }

  float voltage = pzem.voltage();
  float current = pzem.current();
  float power = pzem.power();
  float energy = pzem.energy();
  float frequency = pzem.frequency();
  float powerFactor = pzem.pf();

  if (
    isnan(voltage) ||
    isnan(current) ||
    isnan(power) ||
    isnan(energy) ||
    isnan(frequency) ||
    isnan(powerFactor)
  ) {
    Serial.println("Eroare: nu se pot citi datele de la PZEM-004T.");
    Serial.println("Verifica RX/TX, GND, alimentarea PZEM si conexiunea la reteaua AC.");
    delay(2000);
    return;
  }

  Serial.println("Date citite de la PZEM:");
  Serial.print("Tensiune: ");
  Serial.print(voltage);
  Serial.println(" V");

  Serial.print("Curent: ");
  Serial.print(current);
  Serial.println(" A");

  Serial.print("Putere: ");
  Serial.print(power);
  Serial.println(" W");

  Serial.print("Energie: ");
  Serial.print(energy);
  Serial.println(" kWh");

  Serial.print("Frecventa: ");
  Serial.print(frequency);
  Serial.println(" Hz");

  Serial.print("Factor de putere: ");
  Serial.println(powerFactor);

  sendDataToServer(voltage, current, power, energy, frequency, powerFactor);

  delay(2000);
}

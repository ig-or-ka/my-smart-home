#include "requests.h"
#include "config.h"
#define PULSE_PIN_HOT D5
#define PULSE_PIN_COLD D6

volatile unsigned long pulseCount_hot = 0;
volatile unsigned long pulseCount_cold = 0;
unsigned long lastTrigger_hot = 0;
unsigned long lastTrigger_cold = 0;
Requests* reqs = nullptr;



void IRAM_ATTR pulseISR_hot() {
  unsigned long now = micros();
  if (now - lastTrigger_hot > 5000) {  
    // антидребезг 5 мс
    pulseCount_hot++;
  }
  lastTrigger_hot = now;
}

void IRAM_ATTR pulseISR_cold() {
  unsigned long now = micros();
  if (now - lastTrigger_cold > 5000) {  
    // антидребезг 5 мс
    pulseCount_cold++;
  }
  lastTrigger_cold = now;
}

void setup() {
  Serial.begin(9600);
  reqs = new Requests(ssid, password);

  pinMode(PULSE_PIN_HOT, INPUT_PULLUP);
  pinMode(PULSE_PIN_COLD, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(PULSE_PIN_HOT), pulseISR_hot, FALLING);
  attachInterrupt(digitalPinToInterrupt(PULSE_PIN_COLD), pulseISR_cold, FALLING);

  DynamicJsonDocument doc(1024);
  doc["type"] = "start";
  auto r = reqs->post(host_address, host_port, "/counter_event/", doc);
  Serial.println(r);
}

void loop() {
  static unsigned long lastPrint = 0;
  static unsigned long lastHot = 0;
  static unsigned long lastCold = 0;
  if (millis() - lastPrint > 1000) {
    lastPrint = millis();
    Serial.printf("Показания: %lu импульсов cold\n", pulseCount_cold);
    Serial.printf("Показания: %lu импульсов hot\n", pulseCount_hot);

    if(pulseCount_cold > lastCold){
      unsigned long cold_pulse_current = pulseCount_cold - lastCold;
      lastCold = pulseCount_cold;

      DynamicJsonDocument doc(1024);
      doc["type"] = "cold";
      doc["value"] = cold_pulse_current;
      reqs->post(host_address, host_port, "/counter_event/", doc);
    }
    if(pulseCount_hot > lastHot){
      unsigned long hot_pulse_current = pulseCount_hot - lastHot;
      lastHot = pulseCount_hot;

      DynamicJsonDocument doc(1024);
      doc["type"] = "hot";
      doc["value"] = hot_pulse_current;
      reqs->post(host_address, host_port, "/counter_event/", doc);
    }

    // DynamicJsonDocument doc(1024);
    // doc["type"] = "ping";
    // Serial.println(reqs->post(host_address, host_port, "/counter_event/", doc));
  }
}

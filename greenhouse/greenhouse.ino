/*
 * to adafruit.io
 */

#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>
#include <AdafruitIO_WiFi.h>

#include "config.h"

// Enable verbose serial logging (disable to save current)
//#define DEBUG                      1

// Measurement period
#define SLEEP_TIME_US              (300 * 1000000)

// How long to wait for wifi
#define WIFI_WAIT_MSEC                 12000

#define DHTPIN 12     // Digital pin connected to the DHT sensor
// Feather HUZZAH ESP8266 note: use pins 3, 4, 5, 12, 13 or 14 --

#define DHTTYPE DHT11   // DHT 11
//#define DHTTYPE DHT22   // DHT 22  (AM2302), AM2321
//#define DHTTYPE DHT21   // DHT 21 (AM2301)

#define CONFIG_SW_GPIO                 14     // Causes device to go into config mode when held low at reset

DHT_Unified dht(DHTPIN, DHTTYPE);
Config config;

void setup()
{
  //sensor_t sensor;
  sensors_event_t event;
  uint32_t start = millis();

  // Start serial and initialize stdout
  Serial.begin(115200);
  //Serial.setDebugOutput(true);
  Serial.println("");

  dht.begin();
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); /* turn off LED */

  config.load();

#ifdef DEBUG
    Serial.printf("Connecting to %s", config.wifi_ssid());
#endif

  AdafruitIO_WiFi io(config.aio_username(), config.aio_key(),
                     config.wifi_ssid(),  config.wifi_pass());

  io.connect();

  while((io.status() < AIO_CONNECTED) &&
        ((millis() - start) < WIFI_WAIT_MSEC))
 {
#ifdef DEBUG
    Serial.printf(".");
#endif
    delay(500);
  }
  Serial.printf("\r\nConnection status: %s\r\n", io.statusText());

  if (io.status() == AIO_CONNECTED)
  {
#ifdef DEBUG
    Serial.printf("%ld - Update settings from cloud\r\n", millis());
#endif
    AdafruitIO_Feed *fan = io.feed("fan");
    fan->onMessage(handleCommand);
    fan->data = fan->lastValue();

    AdafruitIO_Feed *heat = io.feed("heat");
    heat->onMessage(handleCommand);
    heat->data = heat->lastValue();

    AdafruitIO_Feed *light = io.feed("light");
    heat->onMessage(handleCommand);
    light->data = light->lastValue();

    /* Do an I/O run to populate the fields above */
    io.run();

    Serial.printf("%ld - Fan: %d\r\n", millis(), fan->data->toBool());
    config.set_fan(fan->data->toInt());
    Serial.printf("%ld - Heat: %d\r\n", millis(), heat->data->toInt());
    config.set_heat(heat->data->toInt());
    Serial.printf("%ld - Light: %d\r\n", millis(), light->data->toInt());
    config.set_light(light->data->toInt());

#ifdef DEBUG
    Serial.printf("%ld - Begin readings\r\n", millis());
#endif

//    AdafruitIO_Feed *batt_mv = io.feed("batt_mv");
//    // 10-bit ADC with 1:10 voltage divider scaled up to mv: /1024 * 10 * 1000
//    batt_mv->save((uint16_t)((analogRead(A0) * 9.7656) + 0.5));

    AdafruitIO_Feed *humidity = io.feed("humidity");
    dht.humidity().getEvent(&event);
    if (!isnan(event.relative_humidity))
    {
      humidity->save(event.relative_humidity);
#ifdef DEBUG
      Serial.printf("%ld - Humidity: %.1f\r\n", millis(), event.relative_humidity);
#endif
    }

    AdafruitIO_Feed *temp_f = io.feed("temp-f");
    dht.temperature().getEvent(&event);

    if (!isnan(event.temperature))
    {
      temp_f->save(convertCtoF(event.temperature));
#ifdef DEBUG
      Serial.printf("%ld - Temp: %.1f\r\n", millis(), temp_f->data->toFloat());
#endif
    }

    io.run();

    io.wifi_disconnect();

  } else {
      Serial.printf("Unable to connect to %s\r\n", config.wifi_ssid());
  }

  Serial.printf("Uptime %0.2fS; Sleeping for %d seconds\r\n", (millis() - start) / 1000.0, SLEEP_TIME_US / 1000000);
  digitalWrite(LED_BUILTIN, HIGH);
  ESP.deepSleep(SLEEP_TIME_US);
}

void handleCommand(AdafruitIO_Data *data) {

#ifdef DEBUG
  Serial.print("received <- ");
  Serial.print(data->feedName());

  Serial.print(":");
  Serial.print(data->toInt());
  Serial.println("");
#endif

  if (!strcmp(data->feedName(), "fan"))
  {
    config.set_fan(data->toInt());
  }
  else if (!strcmp(data->feedName(), "light"))
  {
    config.set_light(data->toInt());
  }
  else if (!strcmp(data->feedName(), "heat"))
  {
    config.set_heat(data->toInt());
  }
  else
  {
    Serial.printf("Unhandled feed (%s) sent data: 0x%x\r\n",
                  data->feedName(), data->toInt());
  }
}

void loop() {
}

float convertCtoF(float c) { return c * 1.8 + 32; }

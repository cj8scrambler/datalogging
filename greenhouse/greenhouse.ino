/*
 * to adafruit.io
 */

#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>
#include <Adafruit_BMP3XX.h>
#include "Adafruit_VEML6075.h"
#include <AdafruitIO_WiFi.h>
#include <Wire.h>

#include "config.h"

// Enable verbose serial logging (disable to save current)
//#define DEBUG                      1

// Measurement period
#define SLEEP_TIME_US              (300 * 1000000)

// How long to wait for wifi
#define WIFI_WAIT_MSEC                 15000

DHT_Unified dht(12, DHT22);
Adafruit_BMP3XX bmp; // I2C
Adafruit_VEML6075 uv = Adafruit_VEML6075();
Config config;

void setup()
{
  bool have_bmp = false;
  bool have_veml = false;

  sensors_event_t event;
  uint32_t start = millis();

  Serial.begin(115200);
  //Serial.setDebugOutput(true);
  Serial.println("");

  pinMode(LED_BUILTIN, OUTPUT);

  digitalWrite(LED_BUILTIN, LOW); /* turn on */

  config.load();

#ifdef DEBUG
    Serial.printf("%ld - Connecting to %s\r\n", millis(), config.wifi_ssid());
#endif

  AdafruitIO_WiFi io(config.aio_username(), config.aio_key(),
                     config.wifi_ssid(),  config.wifi_pass());

  dht.begin();

  if (uv.begin())
  {
    /*
     * Use default open-air coefficients from:
     * https://cdn.sparkfun.com/assets/3/9/d/4/1/designingveml6075.pdf
     */
    uv.setCoefficients(2.22, 1.33, 2.95, 1.74, 0.001461, 0.002591);
    have_veml = true;
  } else {
    Serial.printf("%ld - No VEML6075 found\r\n", millis());
  }

  if (bmp.begin())
  {
    have_bmp = true;
    // Set up oversampling and filter initialization
    bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_8X);
    bmp.setPressureOversampling(BMP3_OVERSAMPLING_4X);
    bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3);

    /* First reading always seems bad, so waste it now */
    bmp.performReading();
  } else {
    Serial.printf("%ld - No BMP388 found\r\n", millis());
  }

  io.connect();

  while((io.status() < AIO_CONNECTED) &&
        ((millis() - start) < WIFI_WAIT_MSEC))
  {
#ifdef DEBUG
    Serial.printf(".");
#endif
    delay(500);
  }
  Serial.printf("\r\n%ld - Connection status: %s\r\n", millis(), io.statusText());

  if (io.status() == AIO_CONNECTED)
  {
    Serial.setDebugOutput(false);
#if 0
#ifdef DEBUG
    Serial.printf("%ld - Update settings from cloud\r\n", millis());
#endif
    AdafruitIO_Feed *fan = io.feed("fan");
    fan->onMessage(handleCommand);
    fan->data = fan->lastValue();
    config.set_fan(fan->data->toInt());

    AdafruitIO_Feed *heat = io.feed("heat");
    heat->onMessage(handleCommand);
    heat->data = heat->lastValue();
    config.set_heat(heat->data->toInt());

    AdafruitIO_Feed *light = io.feed("light");
    heat->onMessage(handleCommand);
    light->data = light->lastValue();
    config.set_light(light->data->toInt());

#ifdef DEBUG
    Serial.printf("%ld - Fan: %d\r\n", millis(), fan->data->toBool());
    Serial.printf("%ld - Heat: %d\r\n", millis(), heat->data->toInt());
    Serial.printf("%ld - Light: %d\r\n", millis(), light->data->toInt());
#endif
#endif

#ifdef DEBUG
    Serial.printf("%ld - Begin readings\r\n", millis());
#endif

    AdafruitIO_Feed *batt_v = io.feed("batt_v");
    // 1.0V reference for a 10-bit ADC connected to Bat (0-5V) with
    // a 14.83k/84.4k voltage divider; scale up to mv and round to an int:
    //  =round(((X/1024) * 1.0) * (84.4 / 14.83)) == (X * 0.006644)
    int raw = analogRead(A0);
    batt_v->save(raw * .006644);
#ifdef DEBUG
    Serial.printf("%ld - Raw A/D count: %d  scaled to: %.1f\r\n", millis(), raw, (raw * .006644));
#endif

    if (have_bmp) {
      if (bmp.performReading()) {
        AdafruitIO_Feed *bmp_temp_f = io.feed("bmp-temp-f");
        bmp_temp_f->save(bmp.temperature * (9.0/5.0) + 32.0);
#ifdef DEBUG
        Serial.printf("%ld - BMP Temp C: %.1f\r\n", millis(), bmp.temperature);
        Serial.printf("%ld - BMP Temp f: %.1f\r\n", millis(), bmp.temperature * (9.0/5.0) + 32.0);
#endif

        AdafruitIO_Feed *pressure = io.feed("pressure");
        pressure->save(bmp.pressure / 3386.0);
#ifdef DEBUG
        Serial.printf("%ld - BMP Pressure hPa: %.1f\r\n", millis(), bmp.pressure / 100.0);
        Serial.printf("%ld - BMP Pressure in Hg: %.1f\r\n", millis(), bmp.pressure / 3386.0);
#endif
      } else {
        Serial.printf("%ld - BMP readings failed\r\n", millis());
      }
    }

    AdafruitIO_Feed *humidity = io.feed("humidity");
    dht.humidity().getEvent(&event);
    if (!isnan(event.relative_humidity))
    {
      humidity->save(event.relative_humidity);
#ifdef DEBUG
      Serial.printf("%ld - Humidity: %.1f\r\n", millis(), event.relative_humidity);
#endif
    }
#ifdef DEBUG
    else
    {
      Serial.printf("%ld - Unable to get humidity from DHT\r\n", millis());
    }
#endif

    AdafruitIO_Feed *dht_temp_f = io.feed("dht-temp-f");
    dht.temperature().getEvent(&event);

    if (!isnan(event.temperature))
    {
      dht_temp_f->save(convertCtoF(event.temperature));
#ifdef DEBUG
      Serial.printf("%ld - Temp: %.1f\r\n", millis(), dht_temp_f->data->toFloat());
#endif
    }
#ifdef DEBUG
    else
    {
      Serial.printf("%ld - Unable to get temperature from DHT\r\n", millis());
    }
#endif

    if (have_veml) {
      float uvi = uv.readUVI();
      AdafruitIO_Feed *uv_index = io.feed("UV-Index");
      if (!isnan(uvi))
      {
        uv_index->save(uvi);
#ifdef DEBUG
        Serial.printf("%ld - UV Index: %.1f\r\n", millis(), uv_index->data->toFloat());
#endif
      }

      float uva = uv.readUVA();
      AdafruitIO_Feed *uv_a = io.feed("UV-A");
      if (!isnan(uva))
      {
        uv_a->save(uva);
#ifdef DEBUG
        Serial.printf("%ld - UV-A: %.1f\r\n", millis(), uv_a->data->toFloat());
#endif
      }

      float uvb = uv.readUVB();
      AdafruitIO_Feed *uv_b = io.feed("UV-B");
      if (!isnan(uvb))
      {
        uv_b->save(uvb);
#ifdef DEBUG
        Serial.printf("%ld - UV-B: %.1f\r\n", millis(), uv_b->data->toFloat());
#endif
      }
    }

    /* assume about another 600ms to send data and shut down */
    AdafruitIO_Feed *uptime = io.feed("uptime");
    uptime->save(millis()+600);
#ifdef DEBUG
    Serial.printf("%ld - Logging uptime as: %ld\r\n", millis(), uptime->data->toInt());
#endif

    /* Do all the cloud I/O */
    io.run();

    io.wifi_disconnect();

  } else {
      Serial.printf("%ld - Unable to connect to %s\r\n", millis(), config.wifi_ssid());
  }

  digitalWrite(LED_BUILTIN, HIGH); /* turn off LED */
  Serial.printf("%ld - Uptime %0.2fS; Sleeping for %d seconds\r\n",
                millis(), (millis() - start) / 1000.0, SLEEP_TIME_US / 1000000);
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

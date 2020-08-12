//#define DEBUG                          1      // Enable verbose serial logging

#include <Arduino.h>
#include <EEPROM.h>
#include "config.h"

/* buffer sizes */
#define SSID_MAX_LEN                   32
#define PASS_MAX_LEN                   32
#define USERNAME_MAX_LEN               32
#define KEY_MAX_LEN                    48

#define MAX_LINE_SIZE                  80
#define BLANK_EEPROM_BYTE            0xff

Config::Config()
{
}

void Config::load()
{
  EEPROM.begin(sizeof(systemConfig));

  _config = (systemConfig *)EEPROM.getDataPtr();

  /* Make sure the strings are sane */
  if (_config->wifi_ssid[0] == BLANK_EEPROM_BYTE)
    _config->wifi_ssid[0] = '\0';
  else
    _config->wifi_ssid[SSID_MAX_LEN-1] = '\0';

  if (_config->wifi_pass[0] == BLANK_EEPROM_BYTE)
    _config->wifi_pass[0] = '\0';
  else
    _config->wifi_pass[PASS_MAX_LEN-1] = '\0';

  if (_config->aio_username[0] == BLANK_EEPROM_BYTE)
    _config->aio_username[0] = '\0';
  else
    _config->aio_username[USERNAME_MAX_LEN-1] = '\0';

  if (_config->aio_key[0] == BLANK_EEPROM_BYTE)
    _config->aio_key[0] = '\0';
  else
    _config->aio_key[KEY_MAX_LEN-1] = '\0';

#ifdef DEBUG
  Serial.printf("Loaded %d bytes of data from EEPROM (version %d)\r\n",
                sizeof(systemConfig), _config->version);
  dumpConfig();
#endif

  if ((_config->wifi_ssid[0] == '\0') ||
      (_config->wifi_pass[0] == '\0') ||
      (_config->aio_username[0] == '\0') ||
      (_config->aio_key[0] == '\0') ||
       _config->version != CONFIG_VERSION)
  {
#ifdef DEBUG
  Serial.println("Forcing RECONFIG based on missing data");
#endif
    reconfig();
  }
}

void Config::reconfig()
{
  int i;
  char buff[MAX_LINE_SIZE];

  _config->version = CONFIG_VERSION;

  /* Turn off all external devices to be safe */
  _config->heat_level = 0;
  _config->fan_level = 0;
  _config->light_level = 0;

  snprintf(buff, MAX_LINE_SIZE, "SSID [%s]: ", _config->wifi_ssid);
  readFromSerial(buff, buff, SSID_MAX_LEN, 0, false);
  if (strlen(buff))
  {
    strcpy(_config->wifi_ssid, buff);
  }

  strcpy(buff, "Wifi Password [");
  for (i = 0; i < strlen(_config->wifi_pass); i++)
  {
    strcat(buff, "*");
  }
  strcat(buff, "]: ");
  readFromSerial(buff, buff, PASS_MAX_LEN, 0, true);
  if (strlen(buff))
  {
    strcpy(_config->wifi_pass, buff);
  }

  snprintf(buff, MAX_LINE_SIZE, "AdafruitIO aio_username [%s]: ", _config->aio_username);
  readFromSerial(buff, buff, USERNAME_MAX_LEN, 0, false);
  if (strlen(buff))
  {
    strcpy(_config->aio_username, buff);
  }

  snprintf(buff, MAX_LINE_SIZE, "AdafruitIO aio_key [%s]: ", _config->aio_key);
  readFromSerial(buff, buff, KEY_MAX_LEN, 0, false);
  if (strlen(buff))
  {
    strcpy(_config->aio_key, buff);
  }

  saveSettings();
}

const char *Config::wifi_ssid()
{
  return _config->wifi_ssid;
}

const char *Config::wifi_pass()
{
  return _config->wifi_pass;
}

const char *Config::aio_username()
{
  return _config->aio_username;
}

const char *Config::aio_key()
{
  return _config->aio_key;
}

uint8_t Config::get_light()
{
  return _config->light_level;
}

void Config::set_light(uint8_t level)
{
  if (level != _config->light_level)
  {
    _config->light_level = level;
    saveSettings();
    Serial.printf("Updated light level to: %d\r\n", _config->light_level);
  }
}

uint8_t Config::get_heat()
{
  return _config->heat_level;
}

void Config::set_heat(uint8_t level)
{
  if (level != _config->heat_level)
  {
    _config->heat_level = level;
    saveSettings();
    Serial.printf("Updated heat level to: %d\r\n", _config->heat_level);
  }
}

uint8_t Config::get_fan()
{
  return _config->fan_level;
}

void Config::set_fan(uint8_t level)
{
  if (level != _config->fan_level)
  {
    _config->fan_level = level;
    saveSettings();
    Serial.printf("Updated fan level to: %d\r\n", _config->fan_level);
  }
}

/*****************************************************************************
 *   Private Members
 ****************************************************************************/

void Config::saveSettings()
{
#ifdef DEBUG
  Serial.printf("Saving %d bytes of data to EEPROM:\r\n", sizeof(systemConfig));
  dumpConfig();
#endif
  EEPROM.commit();
}

void Config::dumpConfig()
{
#ifdef DEBUG
  uint8_t *ptr = EEPROM.getDataPtr();
  Serial.printf("Wifi SSID: [%s] (offset %d)\r\n", _config->wifi_ssid, (((uint8_t *)&(_config->wifi_ssid))-ptr));
  Serial.printf("Wifi Pass: [%s] (offset %d)\r\n", _config->wifi_pass, (((uint8_t *)&(_config->wifi_pass))-ptr));
  Serial.printf("AIO Username: [%s] (offset %d)\r\n", _config->aio_username, (((uint8_t *)&(_config->aio_username))-ptr));
  Serial.printf("AIO Key: [%s] (offset %d)\r\n", _config->aio_key, (((uint8_t *)&(_config->aio_key))-ptr));
  Serial.printf("Heat Level: [%d] (offset %d)\r\n", _config->heat_level, (((uint8_t *)&(_config->heat_level))-ptr));
  Serial.printf("Fan Level: [%d] (offset %d)\r\n", _config->fan_level, (((uint8_t *)&(_config->fan_level))-ptr));
  Serial.printf("Light Level: [%d] (offset %d)\r\n", _config->light_level, (((uint8_t *)&(_config->light_level))-ptr));
#endif
}

/* Promt the user, then read a string back.  Reading ends when max limit
 * reached, timeout occurs or CR encountered.  Newline is printed at the end
 *
 *    prompt   - message to present to user
 *    buf      - location to store user input
 *    maxLen   - buf length
 *    timeout  - timeout waiting for user input (returns data entered so far)
 *    hide     - 1: show '*'; 0: show user input
 */
bool Config::readFromSerial(char * prompt, char * buf, int maxLen, int timeout, bool hide)
{
    unsigned long begintime = millis();
    bool timedout = false;
    int loc=0;
    char newchar;

    if(maxLen <= 0)
    {
        // nothing can be read
        return false;
    }

    /* consume all the pending serial data first */
    while (0xFF != (newchar = Serial.read())) {
      delay(5);
    };

    Serial.print(prompt);
    do {
        while (0xFF == (newchar = Serial.read())) {
            delay(10);
            if ((timeout > 0) && ((millis() - begintime) >= timeout)) {
              break;
            }
        }
        buf[loc++] = newchar;
        if (hide)
            Serial.print('*');
        else
            Serial.print((char)buf[loc-1]);

        if (timeout > 0)
            timedout = ((millis() - begintime) >= timeout);
      
      /* stop at max length, CR or timeout */
    } while ((loc < maxLen) && (buf[loc-1] != '\r') && !timedout);

    /* If carriage return was cause of the break, then erase it */
    if ((loc > 0) && (buf[loc-1] == '\r')) {
        loc--;
    }

    /* NULL terminate if there's room, but sometimes 1 single char is passed */
    if (loc < maxLen)
        buf[loc] = '\0';

    Serial.println("");
    return true;
}

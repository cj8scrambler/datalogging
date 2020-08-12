#ifndef Config_h
#define Config_h

#define CONFIG_VERSION                  2
#define SSID_MAX_LEN                   32
#define PASS_MAX_LEN                   32
#define USERNAME_MAX_LEN               32
#define KEY_MAX_LEN                    48

typedef struct config {
  uint8_t version;
  /* User supplied settings */
  char wifi_ssid[SSID_MAX_LEN];
  char wifi_pass[PASS_MAX_LEN];
  char aio_username[USERNAME_MAX_LEN];
  char aio_key[KEY_MAX_LEN];

  /* System saved values */
  uint8_t fan_level;
  uint8_t light_level;
  uint8_t heat_level;
} systemConfig;

class Config
{
  public:
    Config();
    void load();
    void reconfig();
    const char *wifi_ssid();
    const char *wifi_pass();
    const char *aio_username();
    const char *aio_key();

    uint8_t get_light();
    void set_light(uint8_t level);
    uint8_t get_heat();
    void set_heat(uint8_t level);
    uint8_t get_fan();
    void set_fan(uint8_t level);
  private:
    systemConfig *_config;
    bool readFromSerial(char * prompt, char * buf, int maxLen, int timeout, bool hide);
    void saveSettings();
    void dumpConfig();
};

#endif

#pragma once
#include <ESP8266WiFi.h>
#include "ArduinoJson.h"

class Requests{
private:
    String ssid;
    String password;
    void init_wifi();
    String read_response(WiFiClient& client);
    String read_content(WiFiClient& client, int content_length);
    bool check_headers(String header, int& content_length);

public:
    Requests(String ssid, String password);      
    String get(String host, int port, String path);
    String post(String host, int port, String path, DynamicJsonDocument& params);
};

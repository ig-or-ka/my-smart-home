#include "requests.h"
#include "utils.h"


Requests::Requests(String ssid, String password){
    this->ssid = ssid;
    this->password = password;

    init_wifi();
}


void Requests::init_wifi(){
    WiFi.mode(WIFI_STA);       
    WiFi.begin(ssid.c_str(), password.c_str());

    byte tries = 11;
    while (--tries && WiFi.status() != WL_CONNECTED)
    {
        Serial.print(".");
        delay(1000);
    }
    Serial.println("");

    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("WiFi connect error");
    }
    else {        
        Serial.println("WiFi connected");
        Serial.println("IP address: ");
        Serial.println(WiFi.localIP());
    }
}


String Requests::get(String host, int port, String path){
    WiFiClient client;

    if (!client.connect(host, port)) {
        return "ERROR: Connection to host failed";
    }

    client.println("GET " + path + " HTTP/1.1");
    client.println("Host: " + host);
    client.println("Accept: application/json");
    client.println("Connection: keep-alive");
    client.println();

    return read_response(client);
}


String Requests::post(String host, int port, String path, DynamicJsonDocument& params){
    WiFiClient client;

    if (!client.connect(host, port)) {
        return "ERROR: Connection to host failed";
    }

    String out = "";
    serializeJson(params, out);

    client.println("POST " + path + " HTTP/1.1");
    client.println("Host: " + host);
    client.println("Accept: application/json");
    client.println("Content-Type: application/json");
    client.println("Content-Length: " + String(out.length()));
    client.println("Connection: keep-alive");
    client.println();    
    client.print(out);

    return read_response(client);
}


String Requests::read_response(WiFiClient& client){
    String line = "";
    int content_length = -1;
    String data = "";

    //TODO set timeout
    while(client.connected()) {            
        if(client.available()){
            char c = client.read();
            
            if(c == '\n'){
                if(line.length() == 0){
                    if(content_length == -1){
                        data = "ERROR: No content length header";
                        break;
                    }                   

                    data = read_content(client, content_length);
                    break;
                }
                else if(!check_headers(line, content_length)){
                    data = "ERROR: HTTP code not 200";
                    break;
                }

                line = "";
            }
            else if(c != '\r'){
                line += c;
            }                
        }            
    }

    client.stop();
    return data;
}


bool Requests::check_headers(String header, int& content_length){
    std::vector<String> res;
    SplitLine(res, header, ": ");

    if(res.size() == 1){
        res.clear();
        SplitLine(res, header, " ");

        if(res[0] == "HTTP/1.1"){
            if(res[1] != "200" || res[2] != "OK"){
                Serial.print("Request ERROR ");
                Serial.println(header);
                return false;
            }
        }
    }
    else{
        if(res[0] == "Content-Length"){
            content_length = res[1].toInt();
        }
    }

    return true;
}


String Requests::read_content(WiFiClient& client, int content_length){
    String data = "";

    for(int i = 0; i < content_length; i++){
        if(!client.connected()){
            return "ERROR: Request DATA read ERROR";
        }

        if(client.available()){
            data += (char)client.read();
        }
        else{
            i--;
        }
    }

    return data;
}
/*********************************************************************
  ESP32-S3-CAM + Robot Head – 4-position photo sequence + WebSocket
  ✅ Uses YOUR hardware pins and RobotHead class
  ✅ Adds Tailscale Funnel WebSocket connection (port 443)
*********************************************************************/

#include "esp_camera.h"
#include "SD_MMC.h"
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "base64.h"

// ==================== WIFI CONFIGURATION ====================
const char* ssid = "ISDN300C";
const char* password = "12345678";

// ==================== SERVER CONFIGURATION (Tailscale Funnel) ====================
const char* SERVER_HOST = "inx-fiona.tail4fb9a3.ts.net"; 
const int SERVER_PORT = 443;  // ✅ Tailscale Funnel uses HTTPS port 443
const char* CLIENT_ID = "esp32_robot_camera";

// WebSocket path
String wsPath = "/vision/ws/esp32/camera/" + String(CLIENT_ID);

// ==================== CAMERA PINS (GOOUUU ESP32-S3-CAM) ====================
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     15
#define SIOD_GPIO_NUM     4
#define SIOC_GPIO_NUM     5

#define Y9_GPIO_NUM       16
#define Y8_GPIO_NUM       17
#define Y7_GPIO_NUM       18
#define Y6_GPIO_NUM       12
#define Y5_GPIO_NUM       10
#define Y4_GPIO_NUM       8
#define Y3_GPIO_NUM       9
#define Y2_GPIO_NUM       11

#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM     7
#define PCLK_GPIO_NUM     13

// ===================== SERVO SETTINGS =====================
const uint8_t SERVO_HORIZONTAL = 21;   // Left-Right
const uint8_t SERVO_NOD        = 20;   // Up-Down
const uint8_t BUTTON_PIN       = 45;

// Timing constants
const int STEP_DELAY   = 30;    // ms between each servo degree
const int HOLD_TIME    = 2000;  // ms to hold each position before photo

// ===================== GLOBAL OBJECTS =====================
WebSocketsClient webSocket;
bool ws_connected = false;
int photo_counter = 1;

// ===================== RobotHead Class =====================
class RobotHead {
  public:
    void setupPins(uint8_t hPin, uint8_t nPin, uint8_t btnPin = 0);
    void begin();
    void moveH(int target);
    void moveN(int target);

  private:
    Servo servoH, servoN;
    uint8_t pinH = 0, pinN = 0, pinButton = 0;
    int posH = 45, posN = 45;

    void moveSmooth(Servo &servo, int target, int &current);
};

void RobotHead::setupPins(uint8_t hPin, uint8_t nPin, uint8_t btnPin) {
  pinH = hPin;  pinN = nPin;  pinButton = btnPin;
}

void RobotHead::begin() {
  if (pinH == 0 || pinN == 0) {
    Serial.println("ERROR: Servo pins not set!");
    while (true) delay(100);
  }

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  servoH.setPeriodHertz(50);
  servoN.setPeriodHertz(50);
  servoH.attach(pinH, 500, 2400);
  servoN.attach(pinN, 500, 2400);

  servoH.write(45);
  servoN.write(45);
  posH = posN = 45;

  Serial.println("RobotHead servos initialized – centered");
}

void RobotHead::moveSmooth(Servo &servo, int target, int &current) {
  while (current != target) {
    current += (current < target) ? 1 : -1;
    servo.write(current);
    delay(STEP_DELAY);
  }
}

void RobotHead::moveH(int target) { moveSmooth(servoH, target, posH); }
void RobotHead::moveN(int target) { moveSmooth(servoN, target, posN); }

RobotHead head;

// ==================== WEBSOCKET HANDLERS ====================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%lu] ❌ WebSocket disconnected\n", millis());
      ws_connected = false;
      break;
      
    case WStype_CONNECTED:
      {
        Serial.printf("[%lu] ✅ WebSocket connected via Tailscale Funnel!\n", millis());
        ws_connected = true;
        
        // Send registration
        DynamicJsonDocument doc(512);
        doc["type"] = "register";
        doc["client_id"] = CLIENT_ID;
        doc["device_type"] = "esp32_robot_camera";
        
        String msg;
        serializeJson(doc, msg);
        Serial.println("📤 Sending: " + msg);
        webSocket.sendTXT(msg);
      }
      break;
      
    case WStype_TEXT:
      {
        Serial.printf("📨 Message: %s\n", payload);
        
        DynamicJsonDocument doc(4096);
        DeserializationError error = deserializeJson(doc, payload);
        
        if (!error) {
          String msgType = doc["type"];
          
          if (msgType == "registered") {
            Serial.println("✅ Registered with server");
          }
          else if (msgType == "inference_result") {
            int detectionCount = doc["detections"].size();
            Serial.printf("🎨 Received %d detections from server\n", detectionCount);
          }
          else if (msgType == "keepalive") {
            // Silent acknowledgment
          }
          else if (msgType == "error") {
            String errorMsg = doc["message"];
            Serial.println("❌ Server error: " + errorMsg);
          }
        }
      }
      break;
      
    case WStype_ERROR:
      Serial.println("❌ WebSocket ERROR!");
      break;
  }
}

// ==================== SEND IMAGE VIA WEBSOCKET ====================
void sendImageToServer(camera_fb_t* fb, int photo_num, const char* position_name) {
  if (!ws_connected) {
    Serial.println("⚠️ Not connected - skipping upload");
    return;
  }
  
  if (!fb || fb->len == 0) {
    Serial.println("❌ Invalid image buffer!");
    return;
  }
  
  Serial.printf("📤 Sending #%d [%s] (%u KB)...\n", photo_num, position_name, fb->len / 1024);
  
  // Send in chunks
  const size_t CHUNK_SIZE = 32000;
  size_t offset = 0;
  int chunk_id = 0;
  
  while (offset < fb->len) {
    size_t remaining = fb->len - offset;
    size_t current_chunk_size = (remaining < CHUNK_SIZE) ? remaining : CHUNK_SIZE;
    
    String encoded = base64::encode(fb->buf + offset, current_chunk_size);
    
    DynamicJsonDocument doc(encoded.length() + 512);
    doc["type"] = "image_chunk";
    doc["image"] = encoded;
    doc["chunk_id"] = chunk_id;
    doc["offset"] = offset;
    doc["chunk_size"] = current_chunk_size;
    doc["photo_num"] = photo_num;
    doc["position"] = position_name;
    doc["timestamp"] = millis();
    
    if (chunk_id == 0) {
      doc["format"] = "image/jpeg";
      doc["width"] = fb->width;
      doc["height"] = fb->height;
      doc["total_size"] = fb->len;
      doc["sequence_num"] = photo_num;
      doc["camera_position"] = position_name;
    }
    
    String msg;
    serializeJson(doc, msg);
    webSocket.sendTXT(msg);
    
    offset += current_chunk_size;
    chunk_id++;
    
    yield();
    delay(20);
  }
  
  // Send completion
  DynamicJsonDocument completeDoc(256);
  completeDoc["type"] = "image_complete";
  completeDoc["total_chunks"] = chunk_id;
  completeDoc["photo_num"] = photo_num;
  completeDoc["position"] = position_name;
  completeDoc["timestamp"] = millis();
  completeDoc["client_id"] = CLIENT_ID;
  
  String completeMsg;
  serializeJson(completeDoc, completeMsg);
  webSocket.sendTXT(completeMsg);
  
  Serial.printf("✅ Sent! (%d chunks)\n", chunk_id);
}

// ===================== Helper: Take & Save Photo =====================
void takePhoto(int number, const char* position_name) {
  Serial.printf("Taking photo %d/4 [%s]... ", number, position_name);

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("FAILED");
    return;
  }

  char filename[64];
  snprintf(filename, sizeof(filename), "/robot_pos%d_%s.jpg", number, position_name);

  File file = SD_MMC.open(filename, FILE_WRITE);
  if (!file) {
    Serial.println("File open failed!");
  } else {
    file.write(fb->buf, fb->len);
    file.close();
    Serial.printf("SAVED %s (%u bytes)\n", filename, fb->len);
  }
  
  // Send via WebSocket
  if (ws_connected) {
    sendImageToServer(fb, photo_counter, position_name);
    photo_counter++;
  } else {
    Serial.println("⚠️ WebSocket not connected - photo saved to SD only");
  }
  
  esp_camera_fb_return(fb);
}

void capture();

// ===================== Setup =====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("\n=== ESP32-S3-CAM + Robot Head + WebSocket (Tailscale Funnel) ===");

  // ---------- Camera ----------
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_UXGA;   // 1600×1200
  config.jpeg_quality = 10;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed!");
    while (1) delay(1000);
  }
  Serial.println("Camera OK");

  // Slight image tweaks
  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_contrast(s, 1);
  s->set_whitebal(s, 1);

  // ---------- SD Card (1-bit mode) ----------
  SD_MMC.setPins(39, 38, 40);  // CLK, CMD, D0
  if (!SD_MMC.begin("/sdcard", true)) {
    Serial.println("SD Card mount failed!");
    while (1) delay(1000);
  }
  Serial.println("SD Card OK");

  // ---------- Servos ----------
  Serial.println("Start init servos");
  head.setupPins(SERVO_HORIZONTAL, SERVO_NOD, BUTTON_PIN);
  head.begin();  // Moves to center (45,45)
  delay(1000);
  Serial.println("Init servos completed");

  // ---------- Button ----------
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("Button setup completed");

  // ---------- WiFi ----------
  Serial.println("\n========================================");
  Serial.println("📡 WIFI CONNECTION");
  Serial.println("========================================");
  Serial.printf("SSID: %s\n", ssid);
  Serial.println("Attempting connection...");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempts < 30) {
    delay(500);
    Serial.print(".");
    wifi_attempts++;
    
    if (wifi_attempts % 10 == 0) {
      Serial.printf("\n[Attempt %d/30] Status: %d\n", wifi_attempts, WiFi.status());
    }
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi CONNECTED!");
    Serial.printf("   IP Address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("   Signal: %d dBm\n", WiFi.RSSI());
    
    // ---------- WebSocket ----------
    Serial.println("\n========================================");
    Serial.println("🔌 WEBSOCKET CONNECTION");
    Serial.println("========================================");
    Serial.printf("Server: %s\n", SERVER_HOST);
    Serial.printf("Port: %d (HTTPS)\n", SERVER_PORT);
    Serial.printf("Path: %s\n", wsPath.c_str());
    Serial.printf("Full URL: wss://%s%s\n", SERVER_HOST, wsPath.c_str());
    Serial.println("\nInitializing WebSocket client with SSL...");
    
    webSocket.beginSSL(SERVER_HOST, SERVER_PORT, wsPath.c_str());
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    webSocket.enableHeartbeat(15000, 3000, 2);
    
    Serial.println("✅ WebSocket client initialized");
    Serial.println("   Waiting for connection...");
  } else {
    Serial.println("\n========================================");
    Serial.println("❌ WIFI CONNECTION FAILED");
    Serial.println("========================================");
    Serial.printf("Status code: %d\n", WiFi.status());
    Serial.println("Continuing in offline mode (SD card only)");
  }

  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("========================================");
  Serial.println("Press button on GPIO 45 to start 4-photo sequence");
  Serial.println("Connection: Tailscale Funnel (HTTPS)");
  Serial.println("========================================\n");

  delay(1000);
}
 
void loop() {
  webSocket.loop();
  
  // Send keepalive ping
  static unsigned long lastPing = 0;
  if (ws_connected && (millis() - lastPing > 15000)) {
    webSocket.sendTXT("{\"type\":\"ping\"}");
    lastPing = millis();
  }
  
  // Check button
  if(digitalRead(BUTTON_PIN) == LOW){
    delay(50);  // Debounce
    if(digitalRead(BUTTON_PIN) == LOW){
      capture();
      while(digitalRead(BUTTON_PIN) == LOW) delay(10);  // Wait for release
    }
  }
  delay(10);
}

void capture(){
  // ---------- 4-Position Photo Sequence ----------
  Serial.println("\n🎬 Starting 4-photo sequence...\n");

  // 1. Left + Down
  Serial.println("📍 Position 1: left-down");
  head.moveH(0);  head.moveN(0);
  delay(HOLD_TIME);
  takePhoto(1, "left-down");

  // 2. Right + Down
  Serial.println("📍 Position 2: right-down");
  head.moveH(90);
  delay(HOLD_TIME);
  takePhoto(2, "right-down");

  // 3. Right + Up
  Serial.println("📍 Position 3: right-up");
  head.moveN(90);
  delay(HOLD_TIME);
  takePhoto(3, "right-up");

  // 4. Left + Up
  Serial.println("📍 Position 4: left-up");
  head.moveH(0);
  delay(HOLD_TIME);
  takePhoto(4, "left-up");

  // Back to center
  Serial.println("\n🎯 Returning to center position...");
  head.moveH(45);
  head.moveN(45);

  Serial.println("\n✅ All 4 photos taken and saved!");
  Serial.println("Files: /robot_pos1_left-down.jpg ... /robot_pos4_left-up.jpg");
  Serial.println("Ready for next button press.\n");
}
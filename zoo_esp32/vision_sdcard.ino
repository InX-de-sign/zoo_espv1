/*********************************************************************
  GOOUUU ESP32-S3-CAM: 4-Shot Burst to SD Card + WebSocket
  Hardware-optimized: Matches proven SD card code settings
*********************************************************************/

#include <Arduino.h>
#include "esp_camera.h"
#include "SD_MMC.h"
#include "FS.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "base64.h"

// ==================== CAMERA MODEL ====================
#define CAMERA_MODEL_ESP32S3_EYE
#include "camera_pins.h"

// ==================== WIFI CONFIGURATION ====================
const char* ssid = "ISDN300C";
const char* password = "12345678";

// ==================== SERVER CONFIGURATION ====================
const char* SERVER_HOST = "inx-fiona.tail4fb9a3.ts.net"; 
const int SERVER_PORT = 443;  // Tailscale funnel port
const char* CLIENT_ID = "esp32_camera_1";

// WebSocket path
String wsPath = "/vision/ws/esp32/camera/" + String(CLIENT_ID);

// ==================== USER SETTINGS (MATCHES YOUR WORKING CODE) ====================
const int NUM_SHOTS = 4;                    // EXACTLY 4 photos per burst
const int DELAY_BETWEEN_SHOTS_MS = 300;     // EXACTLY 300ms between shots
// ==================================================================================

// ==================== GLOBAL OBJECTS ====================
WebSocketsClient webSocket;
bool ws_connected = false;
bool sending_in_progress = false;
bool sd_card_available = false;

int photo_counter = 1; // Running counter for filenames

// ==================== WEBSOCKET HANDLERS ====================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%lu] ❌ WebSocket disconnected\n", millis());
      ws_connected = false;
      break;
      
    case WStype_CONNECTED:
      {
        Serial.printf("[%lu] ✅ WebSocket connected!\n", millis());
        ws_connected = true;
        
        // Send registration
        DynamicJsonDocument doc(512);
        doc["type"] = "register";
        doc["client_id"] = CLIENT_ID;
        doc["device_type"] = "esp32_camera";
        
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
void sendImageToServer(camera_fb_t* fb, int photo_num) {
  if (!ws_connected) {
    Serial.println("⚠️ Not connected - skipping upload");
    return;
  }
  
  if (!fb || fb->len == 0) {
    Serial.println("❌ Invalid image buffer!");
    return;
  }
  
  Serial.printf("📤 Sending #%d (%u KB)...\n", photo_num, fb->len / 1024);
  
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
    doc["timestamp"] = millis();
    
    if (chunk_id == 0) {
      doc["format"] = "image/jpeg";
      doc["width"] = fb->width;
      doc["height"] = fb->height;
      doc["total_size"] = fb->len;
      doc["sequence_num"] = photo_num;
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
  completeDoc["timestamp"] = millis();
  completeDoc["client_id"] = CLIENT_ID;
  
  String completeMsg;
  serializeJson(completeDoc, completeMsg);
  webSocket.sendTXT(completeMsg);
  
  Serial.printf("✅ Sent! (%d chunks)\n", chunk_id);
}

// ==================== 4-SHOT BURST (MATCHES YOUR WORKING CODE) ====================
void runBurstSequence() {
  Serial.println("\n🎬 Starting 4-shot burst...\n");
  
  sending_in_progress = true;

  for (int i = 1; i <= NUM_SHOTS; i++) {
    Serial.printf("📷 Capturing photo %d/%d...\n", i, NUM_SHOTS);

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("❌ Camera capture failed!");
      i--; // retry this shot
      delay(500);
      continue;
    }

    Serial.printf("✓ Photo captured: %dx%d | %u bytes\n", 
                  fb->width, fb->height, fb->len);

    // === SAVE TO SD CARD (EXACTLY LIKE YOUR WORKING CODE) ===
    if (sd_card_available) {
      char filename[32];
      snprintf(filename, sizeof(filename), "/photo_%03d.jpg", i);

      Serial.printf("💾 Saving %s (%u bytes)... ", filename, fb->len);

      File file = SD_MMC.open(filename, FILE_WRITE);
      if (!file) {
        Serial.println("Failed to open file for writing");
      } else {
        file.write(fb->buf, fb->len);
        file.close();
        Serial.println("SAVED!");
      }
    } else {
      Serial.println("⚠️ SD card not available - skipping save");
    }

    // === SEND VIA WEBSOCKET ===
    if (ws_connected) {
      sendImageToServer(fb, photo_counter);
      photo_counter++;
    } else {
      Serial.println("⚠️ WebSocket not connected - skipping upload");
    }

    esp_camera_fb_return(fb);

    // EXACT DELAY FROM YOUR CODE: 300ms between shots
    if (i < NUM_SHOTS) {
      delay(DELAY_BETWEEN_SHOTS_MS);
    }
  }

  Serial.println("\n✅ Burst sequence complete!");
  
  if (sd_card_available) {
    Serial.println("📂 Files on SD card:");
    Serial.println("   photo_001.jpg");
    Serial.println("   photo_002.jpg");
    Serial.println("   photo_003.jpg");
    Serial.println("   photo_004.jpg");
  }
  
  sending_in_progress = false;
  
  Serial.println("⏳ Ready for next burst...\n");
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("\n=== GOOUUU ESP32-S3-CAM - 4-Shot Burst to SD Card + WebSocket ===");

  // ==================== CAMERA INIT (EXACT SETTINGS FROM YOUR CODE) ====================
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
  config.xclk_freq_hz = 20000000;           // 20MHz works best
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_UXGA;       // 1600x1200 (EXACT MATCH)
  config.jpeg_quality = 10;                 // 10-12 = good quality (EXACT MATCH)
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    while (1) delay(1000);
  }
  Serial.println("✅ Camera initialized successfully!");

  // EXACT SENSOR SETTINGS FROM YOUR CODE
  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_contrast(s, 1);
  s->set_saturation(s, 0);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_gainceiling(s, (gainceiling_t)4);

  // ==================== SD CARD INIT (EXACT MATCH TO YOUR CODE) ====================
  Serial.println("💾 Initializing SD card in 1-bit mode...");

  // CRITICAL: Use correct pins for GOOUUU board
  SD_MMC.setPins(
    39,  // CLK
    38,  // CMD
    40   // D0   ← Only D0 is used in 1-bit mode
  );

  // 1-bit mode = more reliable on GOOUUU boards
  if (!SD_MMC.begin("/sdcard", true)) {  // true = 1-bit mode
    Serial.println("⚠️ SD Card Mount Failed!");
    // Try again with slower clock
    if (!SD_MMC.begin("/sdcard", true, false, SDMMC_FREQ_PROBING)) {
      Serial.println("⚠️ SD Card Mount Failed - continuing without SD");
      sd_card_available = false;
    }
  }

  if (sd_card_available || SD_MMC.cardType() != CARD_NONE) {
    uint8_t cardType = SD_MMC.cardType();
    if (cardType == CARD_NONE) {
      Serial.println("⚠️ No SD card - continuing without SD");
      sd_card_available = false;
    } else {
      Serial.print("✅ SD Card Type: ");
      if (cardType == CARD_MMC) Serial.println("MMC");
      else if (cardType == CARD_SD) Serial.println("SDSC");
      else if (cardType == CARD_SDHC) Serial.println("SDHC");
      else Serial.println("UNKNOWN");
      
      uint64_t cardSize = SD_MMC.cardSize() / (1024 * 1024);
      Serial.printf("   Size: %llu MB\n", cardSize);
      sd_card_available = true;
    }
  }

  // ==================== WIFI ====================
  Serial.println("\n📡 Connecting to WiFi...");
  WiFi.begin(ssid, password);
  
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempts < 20) {
    delay(500);
    Serial.print(".");
    wifi_attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connected!");
    Serial.print("   IP: ");
    Serial.println(WiFi.localIP());
    
    // ==================== WEBSOCKET ====================
    Serial.printf("\n🔌 Connecting to ws://%s:%d%s\n", 
                  SERVER_HOST, SERVER_PORT, wsPath.c_str());
    
    webSocket.beginSSL(SERVER_HOST, SERVER_PORT, wsPath.c_str());
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    webSocket.enableHeartbeat(15000, 3000, 2);
    // webSocket.setExtraHeaders("Origin: http://inx-fiona.tail4fb9a3.ts.net:5000");
  } else {
    Serial.println("\n⚠️ WiFi connection failed - continuing without network");
  }

  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("Hardware: GOOUUU ESP32-S3-CAM");
  Serial.printf("Mode: 4-shot burst (300ms between shots)\n");
  Serial.println("========================================\n");
  
  delay(2000);
}

// ==================== MAIN LOOP - CONTINUOUS 4-SHOT BURSTS ====================
void loop() {
  webSocket.loop();
  
  // Run burst sequence continuously
  if (!sending_in_progress) {
    runBurstSequence();
    // Immediately start next burst (no delay)
  }
  
  delay(10);
  yield();
}
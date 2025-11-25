/*********************************************************************
  ESP32-S3-CAM – Image Capture + WebSocket Sender (CORRECTED)
  Takes photos and sends them to server via WebSocket
*********************************************************************/

#include <Arduino.h>
#include "esp_camera.h"
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
const int SERVER_PORT = 443;
const char* CLIENT_ID = "esp32_camera_1";

// IMPORTANT: Update this path if using path-based routing
String wsPath = "/vision/ws/esp32/camera/" + String(CLIENT_ID);
// If using path-based routing: String wsPath = "/vision/ws/esp32/camera/" + String(CLIENT_ID);

// ==================== CONFIGURABLE SETTINGS ====================
const uint8_t NUM_PHOTOS        = 2;        // How many photos per sequence
const uint16_t DELAY_BETWEEN_MS = 800;      // Delay between each photo
const uint32_t DELAY_AFTER_SEQ  = 25000;    // Delay after full sequence

// ==================== GLOBAL OBJECTS ====================
WebSocketsClient webSocket;
bool ws_connected = false;
bool sending_in_progress = false;

// Array to hold photo frame buffers
camera_fb_t* photos[10] = {nullptr};

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

// ==================== HELPER FUNCTIONS ====================
camera_fb_t* takePhoto() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture FAILED!");
    return nullptr;
  }
  Serial.printf("Photo OK: %dx%d | %u KB\n", 
                fb->width, fb->height, fb->len / 1024);
  return fb;
}

void freeAllPhotos() {
  for (int i = 0; i < NUM_PHOTOS; i++) {
    if (photos[i]) {
      esp_camera_fb_return(photos[i]);
      photos[i] = nullptr;
    }
  }
  Serial.printf("All %d photos freed from RAM\n", NUM_PHOTOS);
}

// ==================== SEND IMAGE VIA WEBSOCKET ====================
void sendImageToServer(camera_fb_t* fb, int photo_num) {
  if (!ws_connected) {
    Serial.println("❌ Not connected to server!");
    return;
  }
  
  if (!fb || fb->len == 0) {
    Serial.println("❌ Invalid image buffer!");
    return;
  }
  
  Serial.printf("📤 Sending image %d (%u KB) to server...\n", photo_num, fb->len / 1024);
  
  // Send in chunks to avoid message size limits
  const size_t CHUNK_SIZE = 32000; // ~32KB chunks
  size_t offset = 0;
  int chunk_id = 0;
  
  while (offset < fb->len) {
    size_t remaining = fb->len - offset;
    size_t current_chunk_size = (remaining < CHUNK_SIZE) ? remaining : CHUNK_SIZE;
    
    // Encode this chunk
    String encoded = base64::encode(fb->buf + offset, current_chunk_size);
    
    DynamicJsonDocument doc(encoded.length() + 512);
    doc["type"] = "image_chunk";
    doc["image"] = encoded;
    doc["chunk_id"] = chunk_id;
    doc["offset"] = offset;
    doc["chunk_size"] = current_chunk_size;
    doc["photo_num"] = photo_num;
    doc["timestamp"] = millis();
    
    // Only include metadata in first chunk
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
    
    if (chunk_id % 3 == 0) {
      Serial.printf("  ✓ Chunk %d: %d bytes\n", chunk_id, current_chunk_size);
    }
    
    offset += current_chunk_size;
    chunk_id++;
    
    yield(); // Prevent watchdog
    delay(20); // Small delay between chunks
  }
  
  // Send completion message
  DynamicJsonDocument completeDoc(256);
  completeDoc["type"] = "image_complete";
  completeDoc["total_chunks"] = chunk_id;
  completeDoc["photo_num"] = photo_num;
  completeDoc["timestamp"] = millis();
  completeDoc["client_id"] = CLIENT_ID;
  
  String completeMsg;
  serializeJson(completeDoc, completeMsg);
  webSocket.sendTXT(completeMsg);
  
  Serial.printf("✅ Image sent! (%d chunks)\n", chunk_id);
}

// ==================== ONE FULL CYCLE ====================
void runPhotoSequence() {
  Serial.printf("\n🎬 Starting %d-photo sequence...\n", NUM_PHOTOS);

  // Free any previous photos
  freeAllPhotos();
  
  sending_in_progress = true;

  // Take and send all photos
  for (uint8_t i = 0; i < NUM_PHOTOS; i++) {
    Serial.printf("📷 Capturing photo %d/%d... ", i + 1, NUM_PHOTOS);
    photos[i] = takePhoto();
    
    if (photos[i] == nullptr) {
      Serial.println("Failed! Skipping rest of sequence.");
      break;
    }
    
    // Send to server immediately after capture
    if (ws_connected) {
      sendImageToServer(photos[i], i + 1);
    } else {
      Serial.println("⚠️ Not connected - photo not sent");
    }
    
    if (i < NUM_PHOTOS - 1) {
      delay(DELAY_BETWEEN_MS);
    }
  }

  Serial.printf("✅ Sequence complete!\n");

  // Free memory
  freeAllPhotos();
  sending_in_progress = false;

  Serial.printf("⏳ Waiting %d seconds before next round...\n", DELAY_AFTER_SEQ / 1000);
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("ESP32-S3 Camera → Server");
  Serial.println("WebSocket Edition");
  Serial.println("========================================\n");
  
  Serial.printf("Config: %d photos per sequence, %d ms between shots\n", NUM_PHOTOS, DELAY_BETWEEN_MS);

  // === CAMERA CONFIG ===
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
  config.xclk_freq_hz = 16000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_SVGA;      // 800x600
  config.jpeg_quality = 6;                   // 1-63, lower = better quality
  config.fb_count     = 2;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_LATEST;
 
  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("❌ Camera init FAILED!");
    while (true) delay(1000);
  }

  // === SENSOR TWEAKS ===
  sensor_t *s = esp_camera_sensor_get();
  s->set_exposure_ctrl(s, 0);
  s->set_aec_value(s, 4000);
  s->set_gain_ctrl(s, 1);
  s->set_gainceiling(s, (gainceiling_t)4);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);

  Serial.println("✅ Camera ready: 800x600 JPEG");
  
  // === WIFI ===
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected!");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
  
  // === WEBSOCKET (CORRECTED ORDER) ===
  Serial.printf("📌 Connecting to wss://%s:%d%s\n", SERVER_HOST, SERVER_PORT, wsPath.c_str());
  webSocket.beginSSL(SERVER_HOST, SERVER_PORT, wsPath.c_str());
//   webSocket.setInsecure();  // Skip SSL certificate verification
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);

  webSocket.setExtraHeaders("Origin: https://inx-fiona.tail4fb9a3.ts.net");
  
  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("========================================\n");
  
  delay(3000);
}

// ==================== MAIN LOOP ====================
void loop() {
  webSocket.loop();
  
  if (!sending_in_progress && ws_connected) {
    runPhotoSequence();
    delay(DELAY_AFTER_SEQ);
  }
  
  delay(10);
  yield();
}
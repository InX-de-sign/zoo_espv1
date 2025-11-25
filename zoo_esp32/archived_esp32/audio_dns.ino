/**
 * ESP32 Audio Recorder with Server Upload
 * 
 * Records audio and sends to Docker server for processing
 * Also plays back response audio from server
 */

#include "driver/i2s.h"
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <esp_psram.h>
#include <ESPmDNS.h>
#include "base64.h"

// ==================== WIFI CONFIGURATION ====================
const char* ssid = "ISD-Project-22Fall";         // ← CHANGE to your shared WiFi
const char* password = "isd@2022Fall";     // ← CHANGE to WiFi password

// ==================== SERVER CONFIGURATION ====================
const char* SERVER_HOST = "192.168.50.193"; // ipconfig
const int SERVER_PORT = 8000;               // Docker chatbot port :8000
const char* WEBSOCKET_PATH = "/ws/esp32/audio/esp32_teammate"; // WebSocket endpoint

// ==================== HARDWARE PINS ====================
#define BUTTON_PIN 5
#define I2S_BCLK_MIC 18
#define I2S_LRC_MIC 17
#define I2S_DIN_MIC 15
#define I2S_BCLK_SPK 3
#define I2S_LRC_SPK 8
#define I2S_DOUT_SPK 16
#define I2S_SD_SPK 46

// ==================== AUDIO SETTINGS ====================
#define PLAYBACK_GAIN 8  // Volume multiplier

const int SAMPLE_RATE = 16000;
const int BITS_PER_SAMPLE = 16;
const int RECORD_DURATION_SEC = 5;
const int AUDIO_BUFFER_SIZE = RECORD_DURATION_SEC * SAMPLE_RATE * (BITS_PER_SAMPLE / 8);

// ==================== GLOBAL OBJECTS ====================
WebServer server(80);
WebSocketsClient webSocket;
HTTPClient http;

int16_t *audio_buffer = NULL;
uint8_t *playback_buffer = NULL;
size_t playback_size = 0;
bool wav_ready = false;
bool ws_connected = false;
bool waiting_for_response = false;
bool audio_received = false;

String deviceId = "esp32_teammate";

// ==================== WAV HEADER ====================
void buildWavHeader(uint8_t* header, uint32_t dataSize) {
  uint32_t fileSize = dataSize + 36;
  memcpy(header, "RIFF", 4); 
  memcpy(header + 4, &fileSize, 4);
  memcpy(header + 8, "WAVE", 4); 
  memcpy(header + 12, "fmt ", 4);
  uint32_t fmtSize = 16; 
  memcpy(header + 16, &fmtSize, 4);
  uint16_t format = 1; 
  memcpy(header + 20, &format, 2);
  uint16_t channels = 1; 
  memcpy(header + 22, &channels, 2);
  memcpy(header + 24, &SAMPLE_RATE, 4);
  uint32_t byteRate = SAMPLE_RATE * channels * (BITS_PER_SAMPLE/8);
  memcpy(header + 28, &byteRate, 4);
  uint16_t blockAlign = channels * (BITS_PER_SAMPLE/8);
  memcpy(header + 32, &blockAlign, 2);
  memcpy(header + 34, &BITS_PER_SAMPLE, 2);
  memcpy(header + 36, "data", 4); 
  memcpy(header + 40, &dataSize, 4);
}

// ==================== WEB SERVER HANDLERS ====================
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<title>ESP32 → Server Recorder</title>"
                "<style>body{font-family:Arial;text-align:center;margin-top:40px;}"
                "button{padding:15px 30px;font-size:18px;background:#2196F3;color:white;"
                "border:none;border-radius:8px;cursor:pointer;margin:10px;}"
                "button:hover{background:#1976D2;}"
                ".status{padding:10px;margin:20px;border-radius:5px;}"
                ".connected{background:#4CAF50;color:white;}"
                ".disconnected{background:#f44336;color:white;}</style></head>"
                "<body><h1>🎤 ESP32 Audio Recorder</h1>";
  
  html += "<div class='status " + String(ws_connected ? "connected" : "disconnected") + "'>";
  html += ws_connected ? "✅ Connected to Server" : "❌ Not Connected to Server";
  html += "</div>";
  
  html += "<p><strong>Server:</strong> " + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "</p>";
  
  if (wav_ready) {
    html += "<p><strong>✅ Last Recording Available</strong></p>"
            "<a href='/download'><button>📥 Download Recording</button></a>";
  }
  
  html += "<p>Press the button on ESP32 to record and send to server.</p>";
  html += "<button onclick='location.reload()'>🔄 Refresh Status</button>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
}

void handleDownload() {
  if (!wav_ready) {
    server.send(404, "text/plain", "No recording available.");
    return;
  }
  
  // Create WAV file
  uint8_t wav_file[44 + AUDIO_BUFFER_SIZE];
  buildWavHeader(wav_file, AUDIO_BUFFER_SIZE);
  memcpy(wav_file + 44, audio_buffer, AUDIO_BUFFER_SIZE);
  
  server.sendHeader("Content-Disposition", "attachment; filename=recording.wav");
  server.send_P(200, "audio/wav", (const char*)wav_file, 44 + AUDIO_BUFFER_SIZE);
}

// ==================== WEBSOCKET HANDLERS ====================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket disconnected");
      ws_connected = false;
      break;
      
    case WStype_CONNECTED:
      {
        Serial.println("✅ WebSocket connected!");
        ws_connected = true;
        
        // Send registration
        DynamicJsonDocument doc(512);
        doc["type"] = "register";
        doc["client_id"] = deviceId;
        JsonObject audioSettings = doc.createNestedObject("audio_settings");
        audioSettings["sample_rate"] = SAMPLE_RATE;
        audioSettings["channels"] = 1;
        audioSettings["format"] = "audio/wav";
        
        String msg;
        serializeJson(doc, msg);
        webSocket.sendTXT(msg);
        
        Serial.println("📤 Registration sent");
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
          else if (msgType == "stt_result") {
            String text = doc["text"].as<String>();
            Serial.println("📝 Transcription: " + text);
          }
          else if (msgType == "ai_response_text") {
            String text = doc["text"].as<String>();
            Serial.println("💬 AI Response: " + text);
          }
          else if (msgType == "tts_start") {
            Serial.println("🔊 Audio incoming from server...");
            
            // Allocate playback buffer
            size_t expectedBytes = doc["total_bytes"];
            if (playback_buffer) free(playback_buffer);
            playback_buffer = (uint8_t*)heap_caps_malloc(expectedBytes + 1000, MALLOC_CAP_SPIRAM);
            playback_size = 0;
            audio_received = false;
          }
          else if (msgType == "tts_complete") {
            Serial.printf("✅ Audio received: %d bytes\n", playback_size);
            audio_received = true;
            waiting_for_response = false;
          }
          else if (msgType == "error") {
            String errorMsg = doc["message"];
            Serial.println("❌ Server error: " + errorMsg);
            waiting_for_response = false;
          }
        }
      }
      break;
      
    case WStype_BIN:
      {
        // Receiving audio data from server
        Serial.printf("📦 Audio chunk: %d bytes\n", length);
        
        if (playback_buffer && playback_size + length < 200000) {
          memcpy(playback_buffer + playback_size, payload, length);
          playback_size += length;
        }
      }
      break;
  }
}

// ==================== AUDIO FUNCTIONS ====================
void record_audio() {
  Serial.println("🎤 Recording...");
  
  if (audio_buffer) free(audio_buffer);
  audio_buffer = (int16_t*)heap_caps_malloc(AUDIO_BUFFER_SIZE, MALLOC_CAP_SPIRAM);
  
  if (!audio_buffer) {
    Serial.println("❌ PSRAM allocation failed!");
    return;
  }
  
  size_t bytes_read;
  i2s_read(I2S_NUM_0, audio_buffer, AUDIO_BUFFER_SIZE, &bytes_read, portMAX_DELAY);
  
  // Apply gain
  size_t samples = bytes_read / 2;
  for (size_t i = 0; i < samples; i++) {
    int32_t v = (int32_t)audio_buffer[i] * PLAYBACK_GAIN;
    audio_buffer[i] = (v > 32767) ? 32767 : (v < -32768) ? -32768 : (int16_t)v;
  }
  
  wav_ready = true;
  Serial.printf("✅ Recorded %d bytes\n", bytes_read);
}

void send_audio_to_server() {
  if (!ws_connected) {
    Serial.println("❌ Not connected to server!");
    return;
  }
  
  Serial.println("📤 Sending audio to server...");
  
  // Create WAV with header
  uint8_t wav_chunk[AUDIO_BUFFER_SIZE + 44];
  buildWavHeader(wav_chunk, AUDIO_BUFFER_SIZE);
  memcpy(wav_chunk + 44, audio_buffer, AUDIO_BUFFER_SIZE);
  
  // Encode to base64
  String encoded = base64::encode(wav_chunk, AUDIO_BUFFER_SIZE + 44);
  
  // Send as audio chunk
  DynamicJsonDocument doc(encoded.length() + 512);
  doc["type"] = "audio_chunk";
  doc["audio"] = encoded;
  doc["chunk_id"] = 0;
  doc["timestamp"] = millis();
  doc["format"] = "audio/wav";
  doc["sample_rate"] = SAMPLE_RATE;
  doc["channels"] = 1;
  
  String msg;
  serializeJson(doc, msg);
  webSocket.sendTXT(msg);
  
  // Send complete signal
  delay(100);
  DynamicJsonDocument completeDoc(256);
  completeDoc["type"] = "audio_complete";
  completeDoc["total_chunks"] = 1;
  completeDoc["timestamp"] = millis();
  completeDoc["client_id"] = deviceId;
  
  String completeMsg;
  serializeJson(completeDoc, completeMsg);
  webSocket.sendTXT(completeMsg);
  
  Serial.println("✅ Audio sent!");
  waiting_for_response = true;
}

void play_response_audio() {
  if (!audio_received || playback_size <= 44) {
    Serial.println("⚠️ No audio to play");
    return;
  }
  
  Serial.println("🔊 Playing response...");
  
  // Enable speaker
  digitalWrite(I2S_SD_SPK, HIGH);
  delay(20);
  
  // Skip WAV header (first 44 bytes)
  size_t audio_data_size = playback_size - 44;
  size_t written;
  
  i2s_write(I2S_NUM_1, playback_buffer + 44, audio_data_size, &written, portMAX_DELAY);
  
  // Disable speaker
  digitalWrite(I2S_SD_SPK, LOW);
  
  Serial.println("✅ Playback complete!");
  audio_received = false;
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial); 
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 Audio → Server Recorder");
  Serial.println("========================================\n");
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(I2S_SD_SPK, OUTPUT);
  digitalWrite(I2S_SD_SPK, LOW);
  
  if (!psramFound()) {
    Serial.println("❌ NO PSRAM! This code requires PSRAM.");
    while (1);
  }
  Serial.println("✅ PSRAM detected");
  
  // I2S Microphone setup
  i2s_config_t rx = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 1024
  };
  i2s_pin_config_t pin_rx = {
    .bck_io_num = I2S_BCLK_MIC,
    .ws_io_num = I2S_LRC_MIC,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_DIN_MIC
  };
  i2s_driver_install(I2S_NUM_0, &rx, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_rx);
  Serial.println("✅ Microphone initialized");
  
  // I2S Speaker setup
  i2s_config_t tx = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 1024
  };
  i2s_pin_config_t pin_tx = {
    .bck_io_num = I2S_BCLK_SPK,
    .ws_io_num = I2S_LRC_SPK,
    .data_out_num = I2S_DOUT_SPK,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  i2s_driver_install(I2S_NUM_1, &tx, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pin_tx);
  Serial.println("✅ Speaker initialized");
  
  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected!");
  Serial.print("IP Address: http://");
  Serial.println(WiFi.localIP());
  
  // mDNS
  if (MDNS.begin("esp32")) {
    Serial.println("✅ mDNS: http://esp32.local");
  }
  
  // WebSocket
  Serial.printf("🔌 Connecting to ws://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH);
  webSocket.begin(SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  // Web server
  server.on("/", handleRoot);
  server.on("/download", handleDownload);
  server.begin();
  Serial.println("✅ Web server running!");
  
  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("========================================");
  Serial.println("Press button to record and send to server");
  Serial.println("Server will process and send response audio");
  Serial.println("========================================\n");
}

// ==================== MAIN LOOP ====================
void loop() {
  server.handleClient();
  webSocket.loop();
  
  // Button press detection
  static bool lastButtonState = HIGH;
  bool currentButtonState = digitalRead(BUTTON_PIN);
  
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(50); // Debounce
    
    if (!waiting_for_response) {
      Serial.println("\n🎬 Button pressed - Starting workflow...\n");
      
      // Step 1: Record
      record_audio();
      
      // Step 2: Send to server
      send_audio_to_server();
      
      // Step 3: Wait for response (handled by WebSocket events)
      Serial.println("⏳ Waiting for server response...");
    } else {
      Serial.println("⚠️ Still waiting for previous response...");
    }
  }
  
  lastButtonState = currentButtonState;
  
  // Play audio when received
  if (audio_received && !waiting_for_response) {
    play_response_audio();
  }
  
  delay(10);
}
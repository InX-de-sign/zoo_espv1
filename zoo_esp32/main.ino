/**
 * ESP32 Zoo Chatbot - Complete System with Audio Streaming
 * 
 * Updated to work with new server audio streaming system
 * Server endpoint: ws://SERVER_IP:9000/ws/esp32/audio/{client_id}
 * 
 * Features:
 * 1. Audio input streaming to server
 * 2. Audio output streaming from server (16kHz WAV)
 * 3. Pressure sensor activation
 * 4. Camera 10fps streaming to YOLO
 * 5. Servo animation
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include <ESP32Servo.h>
#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "base64.h"

// ==================== CONFIGURATION ====================

// WiFi Configuration
const char* WIFI_SSID = "YourWiFiSSID";
const char* WIFI_PASSWORD = "YourWiFiPassword";

// Server Configuration
const char* SERVER_HOST = "192.168.1.100";  // Your PC's IP running Docker
const int WEBSOCKET_PORT = 9000;            // Updated port for zoo_api.py
const int YOLO_PORT = 5000;

// WebSocket Endpoint (UPDATED - single endpoint for complete workflow)
const char* AUDIO_WS_PATH = "/ws/esp32/audio/esp32_zoo_001";

// HTTP Endpoints
char CV_INFERENCE_URL[100];

// Device ID
String deviceId = "esp32_zoo_001";

// Hardware Pins
const int SERVO_PIN = 13;
const int PRESSURE_SENSOR_PIN = 34;

// I2S Microphone Pins (INMP441)
const int I2S_MIC_WS = 25;
const int I2S_MIC_SD = 26;
const int I2S_MIC_SCK = 27;

// I2S Speaker Pins (MAX98357A)
const int I2S_SPK_WS = 32;
const int I2S_SPK_SD = 33;
const int I2S_SPK_SCK = 14;

// Audio Settings
const int SAMPLE_RATE = 16000;  // 16kHz matches server output
const int CHANNELS = 1;
const int BITS_PER_SAMPLE = 16;
const int RECORDING_DURATION_MS = 5000;

// Camera Settings
const int CAMERA_FPS = 10;
const int CAMERA_INTERVAL_MS = 1000 / CAMERA_FPS;

// Pressure sensor threshold
const int PRESSURE_THRESHOLD = 500;

// ==================== CAMERA CONFIG ====================

#define CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ==================== GLOBAL OBJECTS ====================

WebSocketsClient webSocket;  // Single WebSocket for complete workflow
Servo animalServo;
HTTPClient http;

// State machine
enum SystemState {
  IDLE,
  WAITING_FOR_TRIGGER,
  RECORDING_AUDIO,
  WAITING_STT,
  WAITING_AI_RESPONSE,
  RECEIVING_AUDIO,
  PLAYING_AUDIO
};

SystemState currentState = IDLE;

// Audio recording
uint8_t* audioRecordBuffer = nullptr;
size_t audioRecordedSize = 0;
bool isRecording = false;
int audioChunkCounter = 0;

// Audio playback
uint8_t* audioPlaybackBuffer = nullptr;
size_t audioPlaybackSize = 0;
size_t audioPlaybackPosition = 0;
bool isPlayingAudio = false;
bool receivingAudioChunks = false;
size_t expectedTotalBytes = 0;
size_t receivedBytes = 0;

// Camera streaming
bool cameraStreamingEnabled = false;
unsigned long lastFrameTime = 0;

// Flags
bool wsConnected = false;
String sttResult = "";
bool waitingForSTT = false;
unsigned long sttStartTime = 0;

// Task handles
TaskHandle_t audioRecordTaskHandle = NULL;
TaskHandle_t audioPlaybackTaskHandle = NULL;
TaskHandle_t cameraStreamTaskHandle = NULL;

// ==================== FUNCTION DECLARATIONS ====================

void connectWiFi();
void setupWebSocket();
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);

bool initCamera();
bool initMicrophone();
bool initSpeaker();
void initServo();
void initPressureSensor();

void startRecording();
void stopRecording();
void audioRecordTask(void* parameter);
void streamAudioChunk(uint8_t* data, size_t length);
void sendAudioComplete();

void audioPlaybackTask(void* parameter);
void startAudioPlayback();
void stopAudioPlayback();

void cameraStreamTask(void* parameter);
bool captureAndSendFrame();

void moveServo(int angle);
void animateServo();
int readPressure();
bool isPressureDetected();

void createWAVHeader(uint8_t* buffer, uint32_t dataSize);
void handleError(String error);
void printStatus();

// ==================== SETUP ====================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 Zoo Chatbot - Audio Streaming");
  Serial.println("========================================\n");
  
  // Build URLs
  sprintf(CV_INFERENCE_URL, "http://%s:%d/predict/", SERVER_HOST, YOLO_PORT);
  
  // Allocate audio buffers
  audioRecordBuffer = (uint8_t*)heap_caps_malloc(
    SAMPLE_RATE * 2 * 6 + 1024, 
    MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
  );
  
  audioPlaybackBuffer = (uint8_t*)heap_caps_malloc(
    200000,  // 200KB for playback buffer (enough for ~6 seconds at 16kHz)
    MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
  );
  
  if (!audioRecordBuffer || !audioPlaybackBuffer) {
    Serial.println("❌ Failed to allocate audio buffers!");
    while(1) delay(1000);
  }
  
  Serial.println("🔡 Connecting to WiFi...");
  connectWiFi();
  
  Serial.println("🔌 Setting up WebSocket...");
  setupWebSocket();
  
  Serial.println("📷 Initializing camera...");
  if (!initCamera()) {
    Serial.println("⚠️ Camera init failed");
  } else {
    Serial.println("✅ Camera ready");
  }
  
  Serial.println("🎤 Initializing microphone...");
  if (!initMicrophone()) {
    handleError("Microphone init failed");
  } else {
    Serial.println("✅ Microphone ready");
  }
  
  Serial.println("🔊 Initializing speaker...");
  if (!initSpeaker()) {
    handleError("Speaker init failed");
  } else {
    Serial.println("✅ Speaker ready");
  }
  
  Serial.println("🦾 Initializing servo...");
  initServo();
  Serial.println("✅ Servo ready");
  
  Serial.println("👆 Initializing pressure sensor...");
  initPressureSensor();
  Serial.println("✅ Pressure sensor ready");
  
  // Create tasks
  xTaskCreatePinnedToCore(
    audioPlaybackTask,
    "AudioPlayback",
    16384,
    NULL,
    2,
    &audioPlaybackTaskHandle,
    0
  );
  
  xTaskCreatePinnedToCore(
    cameraStreamTask,
    "CameraStream",
    16384,
    NULL,
    1,
    &cameraStreamTaskHandle,
    1
  );
  
  Serial.println("\n✅ System ready!");
  Serial.println("📹 Camera streaming at 10fps to YOLO");
  currentState = WAITING_FOR_TRIGGER;
  
  cameraStreamingEnabled = true;
  
  printStatus();
}

// ==================== MAIN LOOP ====================

void loop() {
  static unsigned long lastCheck = 0;
  
  webSocket.loop();
  
  switch (currentState) {
    case WAITING_FOR_TRIGGER:
      if (millis() - lastCheck > 100) {
        lastCheck = millis();
        
        if (isPressureDetected()) {
          Serial.println("\n👆 PRESSURE DETECTED!");
          Serial.println("Starting conversation...\n");
          
          animateServo();
          delay(500);
          
          currentState = RECORDING_AUDIO;
        }
      }
      break;
      
    case RECORDING_AUDIO:
      Serial.println("🎤 Recording audio (5 seconds)...");
      Serial.println("Speak now!");
      
      waitingForSTT = true;
      sttResult = "";
      sttStartTime = millis();
      
      startRecording();
      delay(RECORDING_DURATION_MS);
      stopRecording();
      
      Serial.println("✅ Recording complete");
      Serial.println("⏳ Waiting for transcription...");
      
      currentState = WAITING_STT;
      break;
      
    case WAITING_STT:
      if (sttResult.length() > 0) {
        Serial.println("✅ Transcription: " + sttResult);
        Serial.println("🤖 Waiting for AI response...");
        currentState = WAITING_AI_RESPONSE;
        waitingForSTT = false;
      } else if (millis() - sttStartTime > 15000) {
        Serial.println("❌ STT timeout");
        currentState = WAITING_FOR_TRIGGER;
        waitingForSTT = false;
      }
      break;
      
    case WAITING_AI_RESPONSE:
      // Wait for audio to start coming in
      if (receivingAudioChunks) {
        currentState = RECEIVING_AUDIO;
      } else if (millis() - sttStartTime > 30000) {
        Serial.println("❌ AI response timeout");
        currentState = WAITING_FOR_TRIGGER;
      }
      break;
      
    case RECEIVING_AUDIO:
      // Wait for complete audio transfer
      if (!receivingAudioChunks && audioPlaybackSize > 0) {
        Serial.println("✅ Audio received, starting playback...");
        startAudioPlayback();
        currentState = PLAYING_AUDIO;
      }
      break;
      
    case PLAYING_AUDIO:
      if (!isPlayingAudio) {
        delay(500);
        Serial.println("✅ Conversation complete!\n");
        
        // Reset audio buffers
        audioPlaybackSize = 0;
        audioPlaybackPosition = 0;
        receivedBytes = 0;
        
        currentState = WAITING_FOR_TRIGGER;
        printStatus();
      }
      break;
  }
  
  delay(10);
}

// ==================== WIFI ====================

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WiFi connection failed!");
    ESP.restart();
  }
}

// ==================== WEBSOCKET ====================

void setupWebSocket() {
  webSocket.begin(SERVER_HOST, WEBSOCKET_PORT, AUDIO_WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  Serial.println("⏳ Connecting to WebSocket...");
  
  unsigned long startTime = millis();
  while (!wsConnected && (millis() - startTime < 10000)) {
    webSocket.loop();
    delay(100);
  }
  
  if (wsConnected) {
    Serial.println("✅ WebSocket connected!");
  } else {
    Serial.println("⚠️ WebSocket connection incomplete");
  }
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket disconnected");
      wsConnected = false;
      break;
      
    case WStype_CONNECTED:
      {
        Serial.println("✅ WebSocket connected");
        wsConnected = true;
        
        // Send registration
        DynamicJsonDocument doc(512);
        doc["type"] = "register";
        doc["client_id"] = deviceId;
        JsonObject audioSettings = doc.createNestedObject("audio_settings");
        audioSettings["sample_rate"] = SAMPLE_RATE;
        audioSettings["channels"] = CHANNELS;
        audioSettings["format"] = "audio/wav";
        
        String msg;
        serializeJson(doc, msg);
        webSocket.sendTXT(msg);
        
        Serial.println("📤 Registration sent");
      }
      break;
      
    case WStype_TEXT:
      {
        DynamicJsonDocument doc(4096);
        DeserializationError error = deserializeJson(doc, payload);
        
        if (!error) {
          String msgType = doc["type"];
          
          if (msgType == "registered") {
            Serial.println("✅ Registered with server");
          }
          else if (msgType == "stt_processing") {
            Serial.println("⏳ Server processing speech...");
          }
          else if (msgType == "stt_result") {
            sttResult = doc["text"].as<String>();
            Serial.println("📝 STT: " + sttResult);
          }
          else if (msgType == "openai_processing") {
            Serial.println("🤖 Getting AI response...");
          }
          else if (msgType == "ai_response_text") {
            String text = doc["text"].as<String>();
            Serial.println("💬 AI: " + text);
          }
          else if (msgType == "tts_start") {
            // Audio streaming is about to start
            expectedTotalBytes = doc["total_bytes"];
            int sampleRate = doc["sample_rate"];
            int channels = doc["channels"];
            
            Serial.printf("🔊 TTS audio incoming: %d bytes (%dHz, %dch)\n", 
                         expectedTotalBytes, sampleRate, channels);
            
            // Reset buffers
            audioPlaybackSize = 0;
            audioPlaybackPosition = 0;
            receivedBytes = 0;
            receivingAudioChunks = true;
          }
          else if (msgType == "tts_complete") {
            int totalBytes = doc["total_bytes"];
            Serial.printf("✅ Audio transfer complete: %d bytes\n", totalBytes);
            receivingAudioChunks = false;
          }
          else if (msgType == "error") {
            String errorMsg = doc["message"];
            Serial.println("❌ Server error: " + errorMsg);
          }
        }
      }
      break;
      
    case WStype_BIN:
      {
        // Binary audio data from server (16kHz WAV chunks)
        Serial.printf("📦 Audio chunk: %d bytes\n", length);
        
        // Append to playback buffer
        if (audioPlaybackSize + length < 200000) {
          memcpy(audioPlaybackBuffer + audioPlaybackSize, payload, length);
          audioPlaybackSize += length;
          receivedBytes += length;
          
          // Show progress
          if (expectedTotalBytes > 0) {
            float progress = (float)receivedBytes / expectedTotalBytes * 100;
            Serial.printf("📊 Progress: %.1f%%\n", progress);
          }
        } else {
          Serial.println("⚠️ Playback buffer full!");
        }
      }
      break;
  }
}

// ==================== AUDIO RECORDING ====================

bool initMicrophone() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };
  
  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (err != ESP_OK) return false;
  
  err = i2s_set_pin(I2S_NUM_0, &pin_config);
  return (err == ESP_OK);
}

void startRecording() {
  isRecording = true;
  audioChunkCounter = 0;
  audioRecordedSize = 44;
  
  xTaskCreatePinnedToCore(
    audioRecordTask,
    "AudioRecord",
    8192,
    NULL,
    2,
    &audioRecordTaskHandle,
    1
  );
}

void audioRecordTask(void* parameter) {
  const int bufferSize = 1024;
  int16_t buffer[bufferSize];
  size_t bytesRead;
  
  while (isRecording) {
    esp_err_t result = i2s_read(I2S_NUM_0, buffer, bufferSize * 2, &bytesRead, portMAX_DELAY);
    
    if (result == ESP_OK && bytesRead > 0) {
      if (audioRecordedSize + bytesRead < SAMPLE_RATE * 2 * 6) {
        memcpy(audioRecordBuffer + audioRecordedSize, buffer, bytesRead);
        audioRecordedSize += bytesRead;
      }
      
      if (wsConnected) {
        streamAudioChunk((uint8_t*)buffer, bytesRead);
      }
    }
    
    vTaskDelay(1);
  }
  
  vTaskDelete(NULL);
}

void streamAudioChunk(uint8_t* data, size_t length) {
  uint8_t wavChunk[length + 44];
  createWAVHeader(wavChunk, length);
  memcpy(wavChunk + 44, data, length);
  
  String encoded = base64::encode(wavChunk, length + 44);
  
  DynamicJsonDocument doc(encoded.length() + 512);
  doc["type"] = "audio_chunk";
  doc["audio"] = encoded;
  doc["chunk_id"] = audioChunkCounter++;
  doc["timestamp"] = millis();
  doc["format"] = "audio/wav";
  doc["sample_rate"] = SAMPLE_RATE;
  doc["channels"] = CHANNELS;
  
  String msg;
  serializeJson(doc, msg);
  webSocket.sendTXT(msg);
}

void stopRecording() {
  isRecording = false;
  delay(100);
  
  createWAVHeader(audioRecordBuffer, audioRecordedSize - 44);
  Serial.printf("📼 Recorded %d bytes\n", audioRecordedSize);
  
  sendAudioComplete();
}

void sendAudioComplete() {
  DynamicJsonDocument doc(256);
  doc["type"] = "audio_complete";
  doc["total_chunks"] = audioChunkCounter;
  doc["timestamp"] = millis();
  doc["client_id"] = deviceId;
  
  String msg;
  serializeJson(doc, msg);
  webSocket.sendTXT(msg);
  
  Serial.println("✅ Audio complete signal sent");
}

void createWAVHeader(uint8_t* buffer, uint32_t dataSize) {
  uint32_t fileSize = dataSize + 36;
  uint32_t byteRate = SAMPLE_RATE * CHANNELS * (BITS_PER_SAMPLE / 8);
  uint16_t blockAlign = CHANNELS * (BITS_PER_SAMPLE / 8);
  
  memcpy(buffer + 0, "RIFF", 4);
  memcpy(buffer + 4, &fileSize, 4);
  memcpy(buffer + 8, "WAVE", 4);
  memcpy(buffer + 12, "fmt ", 4);
  uint32_t fmtSize = 16;
  memcpy(buffer + 16, &fmtSize, 4);
  uint16_t audioFormat = 1;
  memcpy(buffer + 20, &audioFormat, 2);
  uint16_t numChannels = CHANNELS;
  memcpy(buffer + 22, &numChannels, 2);
  uint32_t sampleRate = SAMPLE_RATE;
  memcpy(buffer + 24, &sampleRate, 4);
  memcpy(buffer + 28, &byteRate, 4);
  memcpy(buffer + 32, &blockAlign, 2);
  uint16_t bitsPerSample = BITS_PER_SAMPLE;
  memcpy(buffer + 34, &bitsPerSample, 2);
  memcpy(buffer + 36, "data", 4);
  memcpy(buffer + 40, &dataSize, 4);
}

// ==================== AUDIO PLAYBACK ====================

bool initSpeaker() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SPK_SCK,
    .ws_io_num = I2S_SPK_WS,
    .data_out_num = I2S_SPK_SD,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  esp_err_t err = i2s_driver_install(I2S_NUM_1, &i2s_config, 0, NULL);
  if (err != ESP_OK) return false;
  
  err = i2s_set_pin(I2S_NUM_1, &pin_config);
  return (err == ESP_OK);
}

void startAudioPlayback() {
  if (audioPlaybackSize <= 44) {
    Serial.println("⚠️ No audio data to play");
    return;
  }
  
  audioPlaybackPosition = 44;  // Skip WAV header
  isPlayingAudio = true;
  
  Serial.printf("🔊 Starting playback: %d bytes\n", audioPlaybackSize - 44);
}

void audioPlaybackTask(void* parameter) {
  const int chunkSize = 1024;
  size_t bytesWritten;
  
  while (1) {
    if (isPlayingAudio && audioPlaybackPosition < audioPlaybackSize) {
      // Calculate how much to play
      size_t remainingBytes = audioPlaybackSize - audioPlaybackPosition;
      size_t toPlay = (remainingBytes < chunkSize) ? remainingBytes : chunkSize;
      
      // Write to I2S
      i2s_write(I2S_NUM_1, 
                audioPlaybackBuffer + audioPlaybackPosition, 
                toPlay, 
                &bytesWritten, 
                portMAX_DELAY);
      
      audioPlaybackPosition += bytesWritten;
      
      // Check if done
      if (audioPlaybackPosition >= audioPlaybackSize) {
        isPlayingAudio = false;
        Serial.println("✅ Playback complete");
      }
    }
    
    vTaskDelay(10);
  }
}

void stopAudioPlayback() {
  isPlayingAudio = false;
  audioPlaybackPosition = 0;
}

// ==================== CAMERA STREAMING ====================

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
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
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  return (esp_camera_init(&config) == ESP_OK);
}

void cameraStreamTask(void* parameter) {
  while (1) {
    if (cameraStreamingEnabled) {
      unsigned long now = millis();
      
      if (now - lastFrameTime >= CAMERA_INTERVAL_MS) {
        lastFrameTime = now;
        captureAndSendFrame();
      }
    }
    
    vTaskDelay(50);
  }
}

bool captureAndSendFrame() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    return false;
  }
  
  http.begin(CV_INFERENCE_URL);
  http.addHeader("Content-Type", "image/jpeg");
  http.setTimeout(2000);
  
  int httpCode = http.POST((uint8_t*)fb->buf, fb->len);
  
  if (httpCode == 200) {
    // Optional: Parse detection results
    String response = http.getString();
  }
  
  http.end();
  esp_camera_fb_return(fb);
  
  return (httpCode == 200);
}

// ==================== SERVO ====================

void initServo() {
  animalServo.attach(SERVO_PIN);
  animalServo.write(90);
  delay(500);
}

void moveServo(int angle) {
  animalServo.write(constrain(angle, 0, 180));
}

void animateServo() {
  for (int i = 0; i < 3; i++) {
    moveServo(60);
    delay(300);
    moveServo(120);
    delay(300);
  }
  moveServo(90);
}

// ==================== PRESSURE SENSOR ====================

void initPressureSensor() {
  pinMode(PRESSURE_SENSOR_PIN, INPUT);
}

int readPressure() {
  return analogRead(PRESSURE_SENSOR_PIN);
}

bool isPressureDetected() {
  return readPressure() > PRESSURE_THRESHOLD;
}

// ==================== UTILITIES ====================

void handleError(String error) {
  Serial.println("❌ ERROR: " + error);
}

void printStatus() {
  Serial.println("\n========================================");
  Serial.println("SYSTEM STATUS");
  Serial.println("========================================");
  Serial.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
  Serial.printf("WebSocket: %s\n", wsConnected ? "Connected" : "Disconnected");
  Serial.printf("Camera: %s @ 10fps\n", cameraStreamingEnabled ? "Streaming" : "Stopped");
  Serial.printf("Device ID: %s\n", deviceId.c_str());
  Serial.println("========================================\n");
  Serial.println("👆 Press sensor to start conversation");
  Serial.println("📹 Camera continuously streaming to YOLO");
}
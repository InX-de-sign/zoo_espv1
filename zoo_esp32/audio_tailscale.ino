/**
 * ESP32 Audio Recorder with Server Upload - Tailscale Funnel VERSION
 * 
 * Records audio and sends to Docker server for processing
 * Uses Tailscale Funnel accessing port 443, via https://inx-fiona.tail4fb9a3.ts.net
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

// Audio Stream Queue System
#define MAX_AUDIO_STREAMS 5
#define STREAM_BUFFER_SIZE 524288  // 512KB per stream (WAV files are large!)

struct AudioStream {
    uint8_t* data;
    size_t size;
    size_t capacity;
    bool complete;
    unsigned long streamId;
};

class AudioStreamQueue {
private:
    AudioStream streams[MAX_AUDIO_STREAMS];
    int readIndex = 0;      // Points to the stream being played
    int writeIndex = 0;     // Points to the stream currently receiving data
    int nextStreamIndex = 0; // Points to where the NEXT stream will be allocated
    int count = 0;

public:
    bool startNewStream(unsigned long streamId) {
        if (count >= MAX_AUDIO_STREAMS) {
            Serial.println("⚠️ Queue full!");
            return false;
        }
        
        // Use nextStreamIndex for allocation
        if (streams[nextStreamIndex].data) {
            heap_caps_free(streams[nextStreamIndex].data);
            streams[nextStreamIndex].data = nullptr;
        }
        
        streams[nextStreamIndex].data = (uint8_t*)heap_caps_malloc(STREAM_BUFFER_SIZE, MALLOC_CAP_SPIRAM);
        if (!streams[nextStreamIndex].data) {
            Serial.println("❌ Stream allocation failed!");
            return false;
        }
        
        streams[nextStreamIndex].capacity = STREAM_BUFFER_SIZE;
        streams[nextStreamIndex].size = 0;
        streams[nextStreamIndex].complete = false;
        streams[nextStreamIndex].streamId = streamId;
        
        Serial.printf("✅ Started stream %d (ID: %lu)\n", nextStreamIndex, streamId);
        
        // Set writeIndex to the stream we just allocated
        writeIndex = nextStreamIndex;
        
        count++;
        nextStreamIndex = (nextStreamIndex + 1) % MAX_AUDIO_STREAMS;
        
        return true;
    }
    
    bool addData(const uint8_t* data, size_t len) {
        if (count == 0 || !streams[writeIndex].data) {
            return false;
        }
        
        if (streams[writeIndex].size + len > streams[writeIndex].capacity) {
            Serial.printf("⚠Stream %d buffer full!\n", writeIndex);
            Serial.printf("⚠Failed to add %d bytes\n", len);
            return false;
        }
        
        memcpy(streams[writeIndex].data + streams[writeIndex].size, data, len);
        streams[writeIndex].size += len;
        return true;
    }
    
    void completeCurrentStream() {
        if (count == 0) return;
        
        streams[writeIndex].complete = true;
        Serial.printf("✅ Stream %d complete: %d bytes\n", writeIndex, streams[writeIndex].size);
    }
    
    AudioStream* getCurrentPlaybackStream() {
        if (count == 0) return nullptr;
        return &streams[readIndex];
    }
    
    void advancePlayback() {
        if (count == 0) return;
        
        // Free the completed stream
        if (streams[readIndex].data) {
            heap_caps_free(streams[readIndex].data);
            streams[readIndex].data = nullptr;
        }
        streams[readIndex].size = 0;
        streams[readIndex].complete = false;
        
        count--;
        readIndex = (readIndex + 1) % MAX_AUDIO_STREAMS;
        
        Serial.printf("Advanced to stream %d (%d remaining)\n", readIndex, count);
    }
    
    int getCount() const {
        return count;
    }
    
    bool hasCompleteStream() {
        if (count == 0) return false;
        return streams[readIndex].complete;
    }
    
    // ADD THIS METHOD - it's what your code is calling!
    bool hasStreams() {
        return count > 0;
    }
    
    void clear() {
        for (int i = 0; i < MAX_AUDIO_STREAMS; i++) {
            if (streams[i].data) {
                heap_caps_free(streams[i].data);
                streams[i].data = nullptr;
            }
            streams[i].size = 0;
            streams[i].complete = false;
        }
        readIndex = 0;
        writeIndex = 0;
        nextStreamIndex = 0;
        count = 0;
    }
};

// Simple Circular Buffer for Audio Streaming
template<typename T, size_t SIZE>
class SimpleCircularBuffer {
private:
    T* buffer;
    size_t head = 0;
    size_t tail = 0;
    size_t count = 0;
    bool allocated = false;
    
public:
    // CHANGE: Don't allocate in constructor
    SimpleCircularBuffer() : buffer(nullptr), allocated(false) {
        // Don't allocate here! Wait for init()
    }
    
    bool init() {
        if (allocated) return true;  // Already allocated
        
        buffer = (T*)heap_caps_malloc(SIZE * sizeof(T), MALLOC_CAP_SPIRAM);
        if (buffer) {
            allocated = true;
            head = tail = count = 0;
            Serial.printf("✅ Circular buffer allocated: %d bytes\n", SIZE * sizeof(T));
            return true;
        } else {
            Serial.println("❌ Circular buffer allocation failed!");
            return false;
        }
    }
    
    ~SimpleCircularBuffer() {
        if (buffer && allocated) {
            heap_caps_free(buffer);
            buffer = nullptr;
            allocated = false;
        }
    }
    
    bool push(T item) {
        if (!allocated || count >= SIZE) return false;
        buffer[head] = item;
        head = (head + 1) % SIZE;
        count++;
        return true;
    }
    
    bool pop(T& item) {
        if (!allocated || count == 0) return false;
        item = buffer[tail];
        tail = (tail + 1) % SIZE;
        count--;
        return true;
    }
    
    size_t available() { return count; }
    size_t free() { return SIZE - count; }
    bool isEmpty() { return count == 0; }
    bool isFull() { return count >= SIZE; }
    
    void clear() { 
        if (allocated) {
            head = tail = count = 0;
            Serial.println("🔄 Circular buffer cleared");
        }
    }
    
    bool isAllocated() { return allocated; }
};

// ==================== WIFI CONFIGURATION ====================
// const char* ssid = "ISDN300C";
// const char* password = "12345678";
const char* ssid = "ISD-Project-22Fall";
const char* password = "isd@2022Fall";

// ==================== SERVER CONFIGURATION (Tailscale Funnel) ====================
const char* SERVER_HOST = "inx-fiona.tail4fb9a3.ts.net"; 
const int SERVER_PORT = 443;
const char* CLIENT_ID = "esp32_1"; // Unique ID for this ESP32
String wsPath = "/ws/esp32/audio/" + String(CLIENT_ID);

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
#define PLAYBACK_GAIN 16

const int SAMPLE_RATE = 16000;
const int BITS_PER_SAMPLE = 16;
const int RECORD_DURATION_SEC = 5;
const int AUDIO_BUFFER_SIZE = RECORD_DURATION_SEC * SAMPLE_RATE * (BITS_PER_SAMPLE / 8);

// ==================== GLOBAL OBJECTS ====================
WebServer server(80);
WebSocketsClient webSocket;
HTTPClient http;

int16_t *audio_buffer = NULL;
bool wav_ready = false;
bool ws_connected = false;
bool waiting_for_response = false;
bool audio_received = false;

String deviceId = CLIENT_ID;


// ==================== GLOBAL OBJECTS ====================
AudioStreamQueue audioQueue;
bool isPlayingAudio = false;
unsigned long currentStreamId = 0;
int streamCounter = 0;

// ==================== CONNECTION TEST ====================
bool testServerConnection() {
  Serial.println("🔍 Testing Tailscale Funnel connection...");
  
  HTTPClient http;
  String url = "https://" + String(SERVER_HOST) + "/health";
  
  http.begin(url);
  http.setTimeout(10000);
  int httpCode = http.GET();
  
  if (httpCode > 0) {
    Serial.printf("✅ Server reachable! HTTP Code: %d\n", httpCode);
    String response = http.getString();
    Serial.println("Response: " + response);
    http.end();
    return true;
  } else {
    Serial.printf("❌ Server unreachable! Error: %s\n", http.errorToString(httpCode).c_str());
    Serial.println("\n💡 Tailscale Funnel Troubleshooting:");
    Serial.println("   1. Check Tailscale Funnel URL: " + String(SERVER_HOST));
    Serial.println("   2. Verify Tailscale Funnel is running: tailscale funnel status");
    Serial.println("   3. Docker container must be running on PC");
    Serial.println("   4. Check PC has internet connection");
    http.end();
    return false;
  }
}

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
                "<title>ESP32 Audio Recorder (Tailscale Funnel)</title>"
                "<style>body{font-family:Arial;text-align:center;margin-top:40px;}"
                "button{padding:15px 30px;font-size:18px;background:#2196F3;color:white;"
                "border:none;border-radius:8px;cursor:pointer;margin:10px;}"
                "button:hover{background:#1976D2;}"
                ".status{padding:10px;margin:20px;border-radius:5px;}"
                ".connected{background:#4CAF50;color:white;}"
                ".disconnected{background:#f44336;color:white;}"
                ".info{background:#e3f2fd;padding:15px;margin:20px;border-radius:5px;}"
                "</style></head>"
                "<body><h1>🎤 ESP32 Audio Recorder</h1>";
  
  html += "<div class='status " + String(ws_connected ? "connected" : "disconnected") + "'>";
  html += ws_connected ? "✅ Connected to Server" : "❌ Not Connected to Server";
  html += "</div>";
  
  html += "<div class='info'>";
  html += "<strong>Configuration:</strong><br>";
  html += "Tailscale Funnel: " + String(SERVER_HOST) + "<br>";
  html += "ESP32 IP: " + WiFi.localIP().toString() + "<br>";
  html += "Connection: Remote via Tailscale Funnel (HTTPS)";
  html += "</div>";
  
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
  
  uint8_t* wav_file = (uint8_t*)heap_caps_malloc(44 + AUDIO_BUFFER_SIZE, MALLOC_CAP_SPIRAM);
  if (!wav_file) {
    server.send(500, "text/plain", "Memory allocation failed!");
    return;
  }

  buildWavHeader(wav_file, AUDIO_BUFFER_SIZE);
  memcpy(wav_file + 44, audio_buffer, AUDIO_BUFFER_SIZE);
  
  server.sendHeader("Content-Disposition", "attachment; filename=recording.wav");
  server.send_P(200, "audio/wav", (const char*)wav_file, 44 + AUDIO_BUFFER_SIZE);

  free(wav_file);
}

// ==================== WEBSOCKET HANDLERS ====================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%lu] ❌ WebSocket disconnected\n", millis());
      ws_connected = false;
      waiting_for_response = false;
      break;
      
    case WStype_CONNECTED:
      {
        Serial.printf("[%lu] ✅ WebSocket connected via Tailscale Funnel!\n", millis());
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
          else if (msgType == "stt_result") {
            String text = doc["text"].as<String>();
            Serial.println("🔊 Transcription: " + text);
          }
          else if (msgType == "keepalive") {
            // Silent acknowledgment - don't spam logs
            // Connection is kept alive automatically
          }
          else if (msgType == "ai_response_text") {
            String text = doc["text"].as<String>();
            Serial.println("💬 AI Response: " + text);
          }
          else if (msgType == "audio_start" || msgType == "tts_start") {
            Serial.println("🎵 Audio incoming from server...");
            
            // Start a new stream
            streamCounter++;
            if (audioQueue.startNewStream(streamCounter)) {
                Serial.printf("✅ Stream %d started\n", streamCounter);
            } else {
                Serial.println("❌ Failed to start stream - queue full");
            }
          }
          else if (msgType == "audio_complete" || msgType == "tts_complete") {
              if (audioQueue.getCount() > 0) {  // Only if we have streams
                  audioQueue.completeCurrentStream();
                  
                  if (!isPlayingAudio && audioQueue.hasStreams()) {
                      Serial.println("▶️ Starting playback queue...");
                      isPlayingAudio = true;
                  }
              }
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
            // Add to current stream in queue
            if (audioQueue.addData(payload, length)) {
                // Data added successfully
                if (length > 4096) {  // Log large chunks
                    Serial.printf("Added %d bytes to stream\n", length);
                }
            } else {
                Serial.printf("⚠️Failed to add %d bytes\n", length);
            }
            
            // Start playback once first stream has enough data
            if (!isPlayingAudio && audioQueue.hasStreams()) {
                AudioStream* stream = audioQueue.getCurrentPlaybackStream();
                if (stream && stream->size > 8192) {  // 8KB threshold
                    Serial.println("Starting playback...");
                    isPlayingAudio = true;
                }
            }
            
            yield();
        }
        break;

    case WStype_ERROR:
      Serial.println("❌ WebSocket ERROR!");
      waiting_for_response = false;
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
  
  Serial.println("📤 Sending audio to Tailscale Funnel server...");
  
  uint8_t* wav_chunk = (uint8_t*)heap_caps_malloc(AUDIO_BUFFER_SIZE + 44, MALLOC_CAP_SPIRAM);
  if (!wav_chunk) {
    Serial.println("❌ Failed to allocate memory for WAV chunk!");
    return;
  }

  buildWavHeader(wav_chunk, AUDIO_BUFFER_SIZE);
  memcpy(wav_chunk + 44, audio_buffer, AUDIO_BUFFER_SIZE);
  
  size_t total_size = AUDIO_BUFFER_SIZE + 44;
  
  const size_t CHUNK_SIZE = 8192;  // 8KB chunks (safe for WebSocket)
  size_t total_chunks = (total_size + CHUNK_SIZE - 1) / CHUNK_SIZE;

  Serial.printf("📦 Sending %d bytes in %d chunks\n", total_size, total_chunks);

  for (size_t i = 0; i < total_chunks; i++) {
    size_t offset = i * CHUNK_SIZE;
    size_t chunk_len = min(CHUNK_SIZE, total_size - offset);
    
    // Encode this chunk
    String encoded = base64::encode(wav_chunk + offset, chunk_len);
    
    // Create JSON for this chunk
    DynamicJsonDocument doc(encoded.length() + 256);
    doc["type"] = "audio_chunk";
    doc["audio"] = encoded;
    doc["chunk_id"] = i;
    doc["total_chunks"] = total_chunks;
    doc["total_size"] = total_size;

    if (i == 0) {
      // First chunk includes metadata
      doc["timestamp"] = millis();
      doc["format"] = "audio/wav";
      doc["sample_rate"] = SAMPLE_RATE;
      doc["channels"] = 1;
    }
    
    String msg;
    serializeJson(doc, msg);
    
    // Send chunk
    webSocket.sendTXT(msg);
    
    // Progress indicator
    if (i % 5 == 0 || i == total_chunks - 1) {
      Serial.printf("📤 Sent chunk %d/%d (%.0f%%)\n", 
                    i + 1, total_chunks, 
                    ((i + 1) * 100.0) / total_chunks);
    }

    delay(10);
    yield();
  }

  delay(50);
  DynamicJsonDocument completeDoc(256);
  completeDoc["type"] = "audio_complete";
  completeDoc["total_chunks"] = total_chunks;
  completeDoc["timestamp"] = millis();
  completeDoc["client_id"] = deviceId;
  
  String completeMsg;
  serializeJson(completeDoc, completeMsg);
  webSocket.sendTXT(completeMsg);
  
  // Clean up
  free(wav_chunk);
  
  Serial.println("✅ Audio sent via Tailscale Funnel!");
  waiting_for_response = true;
}

void play_response_audio() {
    static size_t playbackOffset = 44;  // Skip WAV header
    static bool headerSkipped = false;  
    static unsigned long finishTime = 0;  // Track when playback finishes
    static unsigned long drainDelay = 0;   // Calculated drain time
    
    if (!audioQueue.hasStreams()) {
        if (isPlayingAudio) {
            digitalWrite(I2S_SD_SPK, LOW);
            Serial.println("✅ All streams played!");
            isPlayingAudio = false;
            playbackOffset = 44;
            headerSkipped = false;
            finishTime = 0;
            drainDelay = 0;
            waiting_for_response = false;
        }
        return;
    }
    
    AudioStream* current = audioQueue.getCurrentPlaybackStream();
    if (!current || !current->data) {
        return;
    }

    const size_t MIN_BUFFER_SIZE = 4096;

    if (!headerSkipped) {
        if (current->size < MIN_BUFFER_SIZE) {
            static int bufferWaitCount = 0;
            if (++bufferWaitCount % 10 == 0) {
                Serial.printf("⏳ Buffering: %d/%d bytes...\n", current->size, MIN_BUFFER_SIZE);
            }
            return;
        }
        
        Serial.printf("📊 Playing WAV stream: %d bytes\n", current->size);
        
        // Calculate drain time: (samples / sample_rate) * 1000 + buffer margin
        // WAV data = total - 44 bytes header
        size_t audioDataBytes = current->size - 44;
        size_t samples = audioDataBytes / 2;  // 16-bit = 2 bytes per sample
        drainDelay = (samples * 1000 / SAMPLE_RATE) + 200;  // Add 200ms margin
        Serial.printf("🕐 Drain delay: %lu ms\n", drainDelay);
        
        digitalWrite(I2S_SD_SPK, HIGH);
        playbackOffset = 44;
        headerSkipped = true;
        finishTime = 0;
    }

    const size_t CHUNK_SIZE = 1024;
    
    if (playbackOffset < current->size) {
        size_t remaining = current->size - playbackOffset;
        size_t toPlay = (remaining > CHUNK_SIZE) ? CHUNK_SIZE : remaining;
        
        size_t written = 0;
        i2s_write(I2S_NUM_1, current->data + playbackOffset, toPlay, &written, portMAX_DELAY);
        playbackOffset += written;
        
        // Reset finish time since we're still writing
        finishTime = 0;
    } else {
        // All data sent - now wait for I2S buffer to drain
        if (finishTime == 0) {
            finishTime = millis();
            Serial.printf("⏳ Waiting %lu ms for I2S buffer to drain...\n", drainDelay);
        }
        
        // Wait for calculated drain time
        if (millis() - finishTime > drainDelay) {
            if (current->complete || audioQueue.getCount() > 1) {
                Serial.printf("✅ Stream complete: %d bytes played\n", playbackOffset);
                
                audioQueue.advancePlayback();
                playbackOffset = 44;
                headerSkipped = false;
                finishTime = 0;
                drainDelay = 0;
                
                if (!audioQueue.hasStreams()) {
                    digitalWrite(I2S_SD_SPK, LOW);
                    isPlayingAudio = false;
                    waiting_for_response = false;
                }
            }
        }
    }
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial); 
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 Audio → Server Recorder");
  Serial.println("Tailscale Funnel VERSION");
  Serial.println("========================================\n");
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(I2S_SD_SPK, OUTPUT);
  digitalWrite(I2S_SD_SPK, LOW);
  
  if (!psramFound()) {
    Serial.println("❌ NO PSRAM! This code requires PSRAM.");
    while (1);
  }
  Serial.println("✅ PSRAM detected");
  
  // I2S Microphone
  i2s_config_t rx = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
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

  // I2S Speaker (legacy driver)
  i2s_config_t tx = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
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
  Serial.print("ESP32 IP: http://");
  Serial.println(WiFi.localIP());
  
  // Test server connection
  if (!testServerConnection()) {
    Serial.println("\n⚠️ WARNING: Cannot reach Tailscale Funnel server!");
    Serial.println("Will keep trying to connect...\n");
  }
  
  // mDNS
  if (MDNS.begin("esp32")) {
    Serial.println("✅ mDNS: http://esp32.local");
  }
  
  // WebSocket (SSL for Tailscale Funnel)
  Serial.printf("🔌 Connecting to wss://%s:%d%s\n", SERVER_HOST, SERVER_PORT, wsPath.c_str());
  webSocket.beginSSL(SERVER_HOST, SERVER_PORT, wsPath.c_str());
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
  Serial.println("Tailscale Funnel: https://" + String(SERVER_HOST));
  Serial.println("Press button to record and send");
  Serial.println("========================================\n");
}

// ==================== MAIN LOOP ====================
void loop() {
  server.handleClient();
  webSocket.loop();
  
  static unsigned long lastPing = 0;
  if (ws_connected && (millis() - lastPing > 15000)) {
    webSocket.sendTXT("{\"type\":\"ping\"}");
    lastPing = millis();
    Serial.println("📡 Keepalive ping sent");
  }

  static bool lastButtonState = HIGH;
  bool currentButtonState = digitalRead(BUTTON_PIN);
  
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(50);
    
    if (!waiting_for_response) {
      // normal once record flow
      Serial.println("\n🎬 Button pressed - Starting workflow...\n");
      
      size_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
      Serial.printf("Free PSRAM: %d bytes\n", free_psram);
      
      if (free_psram < 200000) {
        Serial.println("⚠️ Low memory! Skipping...");
        return;
      }

      record_audio();
      send_audio_to_server();
      Serial.println("⏳ Waiting for server response...");

    } else{
        // Interruption - clear queue
        Serial.println("Interrupting previous response...");
        
        audioQueue.clear();  // Clear all queued streams
        isPlayingAudio = false;
        
        Serial.println("Starting new recording...\n");
        
        record_audio();
        send_audio_to_server();
        Serial.println("Waiting for server response...");
    }
  }
  
  lastButtonState = currentButtonState;
  
  if (isPlayingAudio) {
    play_response_audio();
  }

  yield();
  delay(5);
}
#include "driver/i2s.h"
#include <WiFi.h>
#include <WebServer.h>
#include <esp_psram.h>
#include <ESPmDNS.h>  // ← for http://esp32.local

// ==================== CHANGE THESE ====================
const char* ssid = "YourWiFiName";      // ← CHANGE
const char* password = "YourWiFiPass";  // ← CHANGE
// =====================================================

#define BUTTON_PIN 5
#define I2S_BCLK_MIC 18
#define I2S_LRC_MIC 17
#define I2S_DIN_MIC 15
#define I2S_BCLK_SPK 3
#define I2S_LRC_SPK 8
#define I2S_DOUT_SPK 16
#define I2S_SD_SPK 46

#define PLAYBACK_GAIN 8  // MAX VOLUME

const int SAMPLE_RATE = 16000;
const int BITS_PER_SAMPLE = 16;
const int RECORD_DURATION_SEC = 5;
const int AUDIO_BUFFER_SIZE = RECORD_DURATION_SEC * SAMPLE_RATE * (BITS_PER_SAMPLE / 8);

WebServer server(80);
int16_t *audio_buffer = NULL;
uint8_t wav_file[44 + AUDIO_BUFFER_SIZE];
bool wav_ready = false;

void buildWavHeader(uint8_t* header, uint32_t dataSize) {
  uint32_t fileSize = dataSize + 36;
  memcpy(header, "RIFF", 4); memcpy(header + 4, &fileSize, 4);
  memcpy(header + 8, "WAVE", 4); memcpy(header + 12, "fmt ", 4);
  uint32_t fmtSize = 16; memcpy(header + 16, &fmtSize, 4);
  uint16_t format = 1; memcpy(header + 20, &format, 2);
  uint16_t channels = 1; memcpy(header + 22, &channels, 2);
  memcpy(header + 24, &SAMPLE_RATE, 4);
  uint32_t byteRate = SAMPLE_RATE * channels * (BITS_PER_SAMPLE/8);
  memcpy(header + 28, &byteRate, 4);
  uint16_t blockAlign = channels * (BITS_PER_SAMPLE/8);
  memcpy(header + 32, &blockAlign, 2);
  memcpy(header + 34, &BITS_PER_SAMPLE, 2);
  memcpy(header + 36, "data", 4); memcpy(header + 40, &dataSize, 4);
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<title>ESP32 Recorder</title>"
                "<style>body{font-family:Arial;text-align:center;margin-top:60px;}"
                "button{padding:20px 40px;font-size:20px;background:#2196F3;color:white;"
                "border:none;border-radius:12px;cursor:pointer;}"
                "button:hover{background:#1976D2;}</style></head>"
                "<body><h1>ESP32 Audio Recorder</h1>";
  if (wav_ready) {
    html += "<p><strong>Recording ready!</strong></p>"
            "<a href='/download'><button>Download recording.wav</button></a>";
  } else {
    html += "<p>Press the button on ESP32 to record.</p>"
            "<p>Then refresh this page.</p>";
  }
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleDownload() {
  if (!wav_ready) {
    server.send(404, "text/plain", "No recording yet.");
    return;
  }
  server.sendHeader("Content-Disposition", "attachment; filename=recording.wav");
  server.send_P(200, "audio/wav", (const char*)wav_file, 44 + (RECORD_DURATION_SEC * SAMPLE_RATE * 2));
}

void record_and_playback() {
  audio_buffer = (int16_t*)heap_caps_malloc(AUDIO_BUFFER_SIZE, MALLOC_CAP_SPIRAM);
  if (!audio_buffer) { Serial.println("PSRAM fail"); return; }

  size_t bytes_read;
  i2s_read(I2S_NUM_0, audio_buffer, AUDIO_BUFFER_SIZE, &bytes_read, portMAX_DELAY);

  // 8x GAIN
  size_t samples = bytes_read / 2;
  for (size_t i = 0; i < samples; i++) {
    int32_t v = (int32_t)audio_buffer[i] * PLAYBACK_GAIN;
    audio_buffer[i] = (v > 32767) ? 32767 : (v < -32768) ? -32768 : (int16_t)v;
  }

  // Build WAV
  buildWavHeader(wav_file, bytes_read);
  memcpy(wav_file + 44, audio_buffer, bytes_read);
  wav_ready = true;

  // Play loud
  digitalWrite(I2S_SD_SPK, HIGH);
  delay(20);
  size_t written;
  i2s_write(I2S_NUM_1, audio_buffer, bytes_read, &written, portMAX_DELAY);
  digitalWrite(I2S_SD_SPK, LOW);

  Serial.println("Recording done! Open http://<IP> or http://esp32.local");
}

void setup() {
  Serial.begin(115200);
  while (!Serial); delay(1000);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(I2S_SD_SPK, OUTPUT);
  digitalWrite(I2S_SD_SPK, LOW);

  if (!psramFound()) { Serial.println("NO PSRAM!"); while (1); }

  // I2S MIC
  i2s_config_t rx = { .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE, .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0, .dma_buf_count = 8, .dma_buf_len = 1024 };
  i2s_pin_config_t pin_rx = { .bck_io_num = I2S_BCLK_MIC, .ws_io_num = I2S_LRC_MIC,
    .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = I2S_DIN_MIC };
  i2s_driver_install(I2S_NUM_0, &rx, 0, NULL); i2s_set_pin(I2S_NUM_0, &pin_rx);

  // I2S SPEAKER
  i2s_config_t tx = { .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE, .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0, .dma_buf_count = 8, .dma_buf_len = 1024 };
  i2s_pin_config_t pin_tx = { .bck_io_num = I2S_BCLK_SPK, .ws_io_num = I2S_LRC_SPK,
    .data_out_num = I2S_DOUT_SPK, .data_in_num = I2S_PIN_NO_CHANGE };
  i2s_driver_install(I2S_NUM_1, &tx, 0, NULL); i2s_set_pin(I2S_NUM_1, &pin_tx);

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi connected!");

  // PRINT IP HERE
  Serial.print("IP Address: http://");
  Serial.println(WiFi.localIP());
  Serial.println("OR: http://esp32.local");

  // mDNS
  if (MDNS.begin("esp32")) {
    Serial.println("mDNS: http://esp32.local");
  }

  server.on("/", handleRoot);
  server.on("/download", handleDownload);
  server.begin();
  Serial.println("Web server running!");
}

void loop() {
  server.handleClient();

  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(50);
    while (digitalRead(BUTTON_PIN) == LOW);
    delay(100);
    if (audio_buffer) free(audio_buffer);
    wav_ready = false;
    record_and_playback();
  }
}

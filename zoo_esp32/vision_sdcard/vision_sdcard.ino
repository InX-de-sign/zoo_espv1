/*********************************************************************
  ESP32-S3-CAM + Robot Head - HTTP Post upload + Web Server
*********************************************************************/

#include "esp_camera.h"
#include "SD_MMC.h"
#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WebServer.h>

// ==================== WIFI CONFIGURATION ====================
const char* ssid = "ISDN300C";
const char* password = "12345678";

// ==================== SERVER CONFIGURATION ====================
const char* SERVER_HOST = "inx-fiona.tail4fb9a3.ts.net";
const char* UPLOAD_URL = "https://inx-fiona.tail4fb9a3.ts.net/vision/upload";
const char* CLIENT_ID = "esp32_robot_camera";

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
const uint8_t SERVO_HORIZONTAL = 21;
const uint8_t SERVO_NOD        = 20;
const uint8_t BUTTON_PIN       = 45;

const int STEP_DELAY   = 30;
const int HOLD_TIME    = 2000;

// ===================== GLOBAL OBJECTS =====================
int photo_counter = 1;
bool wifi_connected = false;
bool is_capturing = false;

// ✅ FIXED: Declare server globally
WebServer server(80);

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

// ==================== HTTP UPLOAD FUNCTION ====================
bool uploadImageHTTP(const char* position_name, int photo_number) {
  if (!wifi_connected) {
    Serial.println("Warning: WiFi not connected - skipping upload");
    return false;
  }

  // Build the exact same filename that was used in takePhoto()
  char filename[64];
  snprintf(filename, sizeof(filename), "/robot_pos%d_%s.jpg", photo_number, position_name);

  File file = SD_MMC.open(filename, FILE_READ);
  if (!file) {
    Serial.printf("Error: Cannot open file for upload: %s\n", filename);
    return false;
  }

  size_t fileSize = file.size();
  if (fileSize == 0) {
    Serial.println("Error: File is empty!");
    file.close();
    return false;
  }

  Serial.printf("Uploading from SD: %s (%u KB)\n", filename, fileSize / 1024);

  WiFiClientSecure client;
  client.setInsecure();  // Only for HTTPS servers with self-signed certs

  HTTPClient http;
  http.begin(client, UPLOAD_URL);
  http.setTimeout(45000);  // Longer timeout for big files / slow connection

  String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
  String contentType = "multipart/form-data; boundary=" + boundary;

  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"file\"; filename=\"image.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";

  String tail = "\r\n--" + boundary + "--\r\n";

  // We stream directly from SD card → no need to load entire file into RAM!
  http.addHeader("Content-Type", contentType);
  http.addHeader("X-Client-ID", CLIENT_ID);
  http.addHeader("X-Position", position_name);
  http.addHeader("X-Photo-Number", String(photo_number));
  http.addHeader("X-Timestamp", String(millis()));

  // Start the multipart POST
  bool success = http.sendRequest("POST", (uint8_t*)head.c_str(), head.length());

  if (!success) {
    Serial.println("Error: Failed to send multipart header");
    file.close();
    http.end();
    return false;
  }

  // Stream the file in chunks (no full RAM load!)
  size_t bytesSent = 0;
  uint8_t buf[1024];
  while (file.available()) {
    size_t len = file.read(buf, sizeof(buf));
    if (http.sendRequest("POST", buf, len) != len) {
      Serial.println("Error: Failed to send file chunk");
      success = false;
      break;
    }
    bytesSent += len;
    // Optional: show progress
    if (bytesSent % (20 * 1024) == 0) {
      Serial.printf("   ...sent %u KB\n", bytesSent / 1024);
    }
  }

  // Send the closing boundary
  if (success) {
    http.sendRequest("POST", (uint8_t*)tail.c_str(), tail.length());
  }

  int httpResponseCode = http.getResponseCode();

  file.close();
  http.end();

  if (httpResponseCode == 200 || httpResponseCode == 201) {
    Serial.printf("Upload successful! (%s) Code: %d\n", filename, httpResponseCode);
    String response = http.getString();
    if (response.length() > 0 && response.length() < 500) {
      Serial.println("Server: " + response);
    }
    return true;
  } else {
    Serial.printf("Upload failed! Code: %d\n", httpResponseCode);
    String response = http.getString();
    if (response.length() > 0) Serial.println("Error: " + response);
    return false;
  }
}

// ===================== Helper: Take & Save Photo =====================
void takePhoto(int number, const char* position_name) {
  Serial.printf("📷 Taking photo %d/4 [%s]...\n", number, position_name);

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("❌ Camera capture FAILED!");
    return;
  }

  Serial.printf("✓ Captured: %dx%d | %u bytes\n", fb->width, fb->height, fb->len);

  char filename[64];
  snprintf(filename, sizeof(filename), "/robot_pos%d_%s.jpg", number, position_name);

  File file = SD_MMC.open(filename, FILE_WRITE);
  if (!file) {
    Serial.println("❌ SD card write failed!");
  } else {
    file.write(fb->buf, fb->len);
    file.close();
    Serial.printf("💾 Saved to SD: %s\n", filename);
  }
 
  if (wifi_connected) {
    bool success = uploadImageHTTP(position_name, number);  // note: parameters swapped
    if (success) {
      photo_counter++;
      // Optional: delete file after successful upload to save space
      // SD_MMC.remove(filename);
    }
  } else {
    Serial.println("Warning: WiFi not connected - photo saved to SD only");
  }
}

void capture();

// ===================== Setup =====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("\n=== ESP32-S3-CAM + Robot Head + Web Server ===");

  // Camera
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
  config.frame_size = FRAMESIZE_UXGA;
  config.jpeg_quality = 10;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("❌ Camera init failed!");
    while (1) delay(1000);
  }
  Serial.println("✅ Camera OK");

  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_contrast(s, 1);
  s->set_whitebal(s, 1);

  // SD Card
  SD_MMC.setPins(39, 38, 40);
  if (!SD_MMC.begin("/sdcard", true)) {
    Serial.println("❌ SD Card mount failed!");
    while (1) delay(1000);
  }
  Serial.println("✅ SD Card OK");

  // Servos
  Serial.println("Initializing servos...");
  head.setupPins(SERVO_HORIZONTAL, SERVO_NOD, BUTTON_PIN);
  head.begin();
  delay(1000);
  Serial.println("✅ Servos ready");

  // Button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("✅ Button setup complete (GPIO 45, active LOW)");

  // WiFi
  Serial.println("\n========================================");
  Serial.println("📡 WIFI CONNECTION");
  Serial.println("========================================");
  Serial.printf("SSID: %s\n", ssid);
 
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
 
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
    if (attempts % 10 == 0) Serial.printf("\n[%d/30]", attempts);
  }
  Serial.println();
 
  if (WiFi.status() == WL_CONNECTED) {
    wifi_connected = true;
    Serial.println("✅ WiFi CONNECTED!");
    Serial.printf("   IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("   Signal: %d dBm\n", WiFi.RSSI());
    Serial.printf("   Upload URL: %s\n", UPLOAD_URL);
   
    // ✅ Setup web server routes
    server.on("/", HTTP_GET, []() {
      String html = "<html><head><title>ESP32 Camera</title></head>";
      html += "<body><h1>ESP32 Robot Camera</h1>";
      html += "<p><a href='/list'>View Photos</a></p>";
      html += "</body></html>";
      server.send(200, "text/html", html);
    });
   
    server.on("/list", HTTP_GET, []() {
      String html = "<html><head><title>Photo Gallery</title>";
      html += "<style>body{font-family:Arial;padding:20px;} ";
      html += "ul{list-style:none;} li{margin:10px;} ";
      html += "a{text-decoration:none;color:#0066cc;font-size:18px;}</style></head>";
      html += "<body><h1>📸 SD Card Photos</h1><ul>";
     
      File root = SD_MMC.open("/");
      File file = root.openNextFile();
     
      while(file) {
        if (!file.isDirectory()) {
          String filename = String(file.name());
          if (filename.endsWith(".jpg")) {
            html += "<li>📷 <a href='/photo?file=" + filename + "'>" + filename + "</a></li>";
          }
        }
        file = root.openNextFile();
      }
     
      html += "</ul><p><a href='/'>← Back</a></p></body></html>";
      server.send(200, "text/html", html);
    });
   
    server.on("/photo", HTTP_GET, []() {
      String filename = server.arg("file");
     
      if (filename.indexOf("..") >= 0) {  // Security check
        server.send(400, "text/plain", "Invalid filename");
        return;
      }
     
      File file = SD_MMC.open("/" + filename);
     
      if (!file) {
        server.send(404, "text/plain", "File not found: " + filename);
        return;
      }
     
      server.streamFile(file, "image/jpeg");
      file.close();
    });
   
    server.begin();
    Serial.println("\n✅ Web server started on port 80");
    Serial.printf("   View photos at: http://%s/list\n", WiFi.localIP().toString().c_str());
  } else {
    wifi_connected = false;
    Serial.println("❌ WiFi FAILED - continuing offline");
  }

  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("========================================");
  Serial.println("Method: HTTP POST upload + Web Server");
  Serial.println("Press button (GPIO 45) to start");
  Serial.println("========================================\n");

  delay(1000);
 
  // Test button
  Serial.println("🔍 Testing button...");
  for (int i = 0; i < 10; i++) {
    int buttonState = digitalRead(BUTTON_PIN);
    Serial.printf("Button state: %s\n", buttonState == HIGH ? "HIGH (not pressed)" : "LOW (pressed)");
    delay(100);
  }
  Serial.println("Button test complete. Ready for input.\n");
}
 
void loop() {
  // Button debouncing
  static bool lastStableState = HIGH;
  static bool lastReading = HIGH;
  static unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 50;
 
  bool currentReading = digitalRead(BUTTON_PIN);
 
  if (currentReading != lastReading) {
    lastDebounceTime = millis();
    lastReading = currentReading;
  }
 
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (currentReading != lastStableState) {
      lastStableState = currentReading;
     
      if (currentReading == LOW && !is_capturing) {
        Serial.println("\n🔘 BUTTON PRESSED!");
        is_capturing = true;
        capture();
        is_capturing = false;
       
        while (digitalRead(BUTTON_PIN) == LOW) {
          delay(10);
        }
        Serial.println("🔘 Button released, ready for next press\n");
      }
    }
  }
 
  // ✅ Handle web server requests
  if (wifi_connected) {
    server.handleClient();
  }
 
  delay(10);
}

void capture() {
  Serial.println("\n🎬 Starting 4-photo sequence...\n");

  Serial.println("📍 Position 1: left-down");
  head.moveH(0);  head.moveN(0);
  delay(HOLD_TIME);
  takePhoto(1, "left-down");

  Serial.println("📍 Position 2: right-down");
  head.moveH(90);
  delay(HOLD_TIME);
  takePhoto(2, "right-down");

  Serial.println("📍 Position 3: right-up");
  head.moveN(90);
  delay(HOLD_TIME);
  takePhoto(3, "right-up");

  Serial.println("📍 Position 4: left-up");
  head.moveH(0);
  delay(HOLD_TIME);
  takePhoto(4, "left-up");

  Serial.println("\n🎯 Returning to center...");
  head.moveH(45);
  head.moveN(45);

  Serial.println("✅ Sequence complete!\n");
}
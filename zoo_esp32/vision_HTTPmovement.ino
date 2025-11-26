/*********************************************************************
  ESP32-S3-CAM + Robot Head - HTTP Post upload (FIXED BUTTON)
*********************************************************************/

#include "esp_camera.h"
#include "SD_MMC.h"
#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

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
bool is_capturing = false;  // Prevent multiple captures

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
bool uploadImageHTTP(camera_fb_t* fb, const char* position_name) {
  if (!wifi_connected) {
    Serial.println("⚠️ WiFi not connected - skipping upload");
    return false;
  }
  
  if (!fb || fb->len == 0) {
    Serial.println("❌ Invalid image buffer!");
    return false;
  }
  
  Serial.printf("📤 Uploading [%s] (%u KB) via HTTP...\n", position_name, fb->len / 1024);
  
  WiFiClientSecure client;
  client.setInsecure();  // Skip SSL certificate verification
  
  HTTPClient http;
  http.begin(client, UPLOAD_URL);
  http.setTimeout(30000);  // 30 second timeout

  String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
  String contentType = "multipart/form-data; boundary=" + boundary;
  
  // Build multipart body
  String bodyStart = "--" + boundary + "\r\n";
  bodyStart += "Content-Disposition: form-data; name=\"file\"; filename=\"image.jpg\"\r\n";
  bodyStart += "Content-Type: image/jpeg\r\n\r\n";
  
  String bodyEnd = "\r\n--" + boundary + "--\r\n";
  
  int totalLength = bodyStart.length() + fb->len + bodyEnd.length();
  
  // Create full payload
  uint8_t* payload = (uint8_t*)malloc(totalLength);
  if (!payload) {
    Serial.println("❌ Memory allocation failed!");
    return false;
  }
  
  // Assemble payload
  memcpy(payload, bodyStart.c_str(), bodyStart.length());
  memcpy(payload + bodyStart.length(), fb->buf, fb->len);
  memcpy(payload + bodyStart.length() + fb->len, bodyEnd.c_str(), bodyEnd.length());

  
  // Set headers
  http.addHeader("Content-Type", contentType);
  http.addHeader("X-Client-ID", CLIENT_ID);
  http.addHeader("X-Position", position_name);
  http.addHeader("X-Photo-Number", String(photo_counter));
  http.addHeader("X-Timestamp", String(millis()));
  
  // Send POST
  int httpResponseCode = http.POST(payload, totalLength);
  
  free(payload);
  
  if (httpResponseCode == 200) {
    Serial.printf("✅ Upload successful! Response: %d\n", httpResponseCode);
    String response = http.getString();
    if (response.length() > 0 && response.length() < 500) {
      Serial.println("Server response: " + response);
    }
    http.end();
    return true;
  } else {
    Serial.printf("❌ Upload failed! Response: %d\n", httpResponseCode);
    String response = http.getString();
    if (response.length() > 0) {
      Serial.println("Error: " + response);
    }
    http.end();
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

  // Save to SD card
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
  
  // Upload via HTTP
  if (wifi_connected) {
    bool success = uploadImageHTTP(fb, position_name);
    if (success) {
      photo_counter++;
    }
  } else {
    Serial.println("⚠️ WiFi not connected - photo saved to SD only");
  }
  
  esp_camera_fb_return(fb);
}

void capture();

// ===================== Setup =====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("\n=== ESP32-S3-CAM + Robot Head (HTTP Upload) ===");

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
  } else {
    wifi_connected = false;
    Serial.println("❌ WiFi FAILED - continuing offline");
  }

  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY");
  Serial.println("========================================");
  Serial.println("Method: HTTP POST upload");
  Serial.println("Press button (GPIO 45) to start");
  Serial.println("========================================\n");

  delay(1000);
  
  // Test button at startup
  Serial.println("🔍 Testing button...");
  for (int i = 0; i < 10; i++) {
    int buttonState = digitalRead(BUTTON_PIN);
    Serial.printf("Button state: %s\n", buttonState == HIGH ? "HIGH (not pressed)" : "LOW (pressed)");
    delay(100);
  }
  Serial.println("Button test complete. Ready for input.\n");
}
 
void loop() {
  // ✅ FIXED: Proper button debouncing with state tracking
  static bool lastStableState = HIGH;      // Last confirmed stable state
  static bool lastReading = HIGH;          // Last raw reading
  static unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 50;  // 50ms debounce
  
  // Read current button state
  bool currentReading = digitalRead(BUTTON_PIN);
  
  // If reading changed, reset debounce timer
  if (currentReading != lastReading) {
    lastDebounceTime = millis();
    lastReading = currentReading;
  }
  
  // If reading has been stable for debounce period
  if ((millis() - lastDebounceTime) > debounceDelay) {
    // Check if state actually changed
    if (currentReading != lastStableState) {
      lastStableState = currentReading;
      
      // Button pressed (HIGH → LOW transition) and not already capturing
      if (currentReading == LOW && !is_capturing) {
        Serial.println("\n🔘 BUTTON PRESSED!");
        is_capturing = true;
        capture();
        is_capturing = false;
        
        // Wait for button release
        while (digitalRead(BUTTON_PIN) == LOW) {
          delay(10);
        }
        Serial.println("🔘 Button released, ready for next press\n");
      }
    }
  }
  
  delay(10);
}

void capture() {
  Serial.println("\n🎬 Starting 4-photo sequence...\n");

  // Position 1: Left + Down
  Serial.println("📍 Position 1: left-down");
  head.moveH(0);  head.moveN(0);
  delay(HOLD_TIME);
  takePhoto(1, "left-down");

  // Position 2: Right + Down
  Serial.println("📍 Position 2: right-down");
  head.moveH(90);
  delay(HOLD_TIME);
  takePhoto(2, "right-down");

  // Position 3: Right + Up
  Serial.println("📍 Position 3: right-up");
  head.moveN(90);
  delay(HOLD_TIME);
  takePhoto(3, "right-up");

  // Position 4: Left + Up
  Serial.println("📍 Position 4: left-up");
  head.moveH(0);
  delay(HOLD_TIME);
  takePhoto(4, "left-up");

  // Return to center
  Serial.println("\n🎯 Returning to center...");
  head.moveH(45);
  head.moveN(45);

  Serial.println("✅ Sequence complete!\n");
}
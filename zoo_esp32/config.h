/**
 * config.h - ESP32 Zoo Chatbot Configuration
 * 
 * Edit this file to configure your ESP32 for your network and server
 */

#ifndef CONFIG_H
#define CONFIG_H

// ==================== WIFI CONFIGURATION ====================
// Change these to match your WiFi network
const char* WIFI_SSID = "YourWiFiName";
const char* WIFI_PASSWORD = "YourWiFiPassword";

// ==================== SERVER CONFIGURATION ====================
// Change this to your PC's IP address running Docker
// Find it with: ipconfig (Windows) or ifconfig (Mac/Linux)
const char* SERVER_HOST = "100.88.240.42"; //testing with Fiona's local ip
// const char* SERVER_HOST = "175.159.122.140"; //testing with Fiona's public IP

// These ports match your docker-compose.yml
const int WEBSOCKET_PORT = 8000;  // Chatbot WebSocket port
const int YOLO_PORT = 5000;        // YOLO inference port

// ==================== DEVICE CONFIGURATION ====================
// Unique ID for this ESP32 device
const char* DEVICE_ID = "esp32_zoo_001";

// ==================== HARDWARE PIN CONFIGURATION ====================

// Servo Motor
#define SERVO_PIN 13

// Pressure Sensor (Analog)
#define PRESSURE_SENSOR_PIN 34
#define PRESSURE_THRESHOLD 500  // Adjust based on your sensor

// I2S Microphone (INMP441)
#define I2S_MIC_WS 25    // Word Select (LRCLK)
#define I2S_MIC_SD 26    // Serial Data (DOUT)
#define I2S_MIC_SCK 27   // Serial Clock (BCLK)

// I2S Speaker Amplifier (MAX98357A)
#define I2S_SPK_WS 32    // Word Select (LRCLK)
#define I2S_SPK_SD 33    // Serial Data (DIN)
#define I2S_SPK_SCK 14   // Serial Clock (BCLK)

// ==================== AUDIO CONFIGURATION ====================

// Audio recording settings
#define SAMPLE_RATE 16000         // 16kHz sample rate
#define CHANNELS 1                // Mono
#define BITS_PER_SAMPLE 16        // 16-bit audio
#define RECORDING_DURATION_MS 5000 // 5 seconds

// Audio buffer sizes
#define AUDIO_BUFFER_SIZE 4096
#define AUDIO_CHUNK_SIZE 1024

// ==================== CAMERA CONFIGURATION ====================

// Camera frame rate
#define CAMERA_FPS 10
#define CAMERA_INTERVAL_MS (1000 / CAMERA_FPS)

// Camera quality (lower = better quality, but larger files)
#define CAMERA_JPEG_QUALITY 12  // Range: 0-63 (10-12 recommended)

// Camera frame size
// Options: FRAMESIZE_QVGA (320x240), FRAMESIZE_VGA (640x480), FRAMESIZE_SVGA (800x600)
#define CAMERA_FRAME_SIZE FRAMESIZE_VGA

// ==================== SYSTEM CONFIGURATION ====================

// Enable/disable features
#define ENABLE_CAMERA_STREAMING true
#define ENABLE_AUDIO_RECORDING true
#define ENABLE_AUDIO_PLAYBACK true
#define ENABLE_SERVO_ANIMATION true

// Debug settings
#define DEBUG_SERIAL true
#define SERIAL_BAUD_RATE 115200

// Timeouts (milliseconds)
#define WIFI_CONNECT_TIMEOUT 20000
#define WEBSOCKET_CONNECT_TIMEOUT 10000
#define STT_PROCESSING_TIMEOUT 15000
#define AI_RESPONSE_TIMEOUT 30000
#define HTTP_REQUEST_TIMEOUT 5000

// ==================== WEBSOCKET PATHS ====================
#define AUDIO_WS_PATH "/ws/audio"
#define TTS_WS_PATH "/ws/tts"

// ==================== PERFORMANCE TUNING ====================

// FreeRTOS task priorities (higher = more priority)
#define AUDIO_RECORD_TASK_PRIORITY 2
#define AUDIO_PLAYBACK_TASK_PRIORITY 2
#define CAMERA_STREAM_TASK_PRIORITY 1
#define WEBSOCKET_TASK_PRIORITY 1

// Task stack sizes (bytes)
#define AUDIO_RECORD_TASK_STACK 8192
#define AUDIO_PLAYBACK_TASK_STACK 16384
#define CAMERA_STREAM_TASK_STACK 16384

// Memory allocation preferences
// Use SPIRAM if available for large buffers
#define USE_SPIRAM_FOR_AUDIO true

// ==================== SERVO ANIMATION ====================

// Servo positions
#define SERVO_CENTER_POS 90
#define SERVO_LEFT_POS 60
#define SERVO_RIGHT_POS 120

// Animation timing (milliseconds)
#define SERVO_ANIMATION_DELAY 300
#define SERVO_ANIMATION_CYCLES 3

// ==================== ADVANCED SETTINGS ====================

// Audio streaming
#define AUDIO_STREAM_CHUNK_SIZE 8192  // Bytes per WebSocket message
#define AUDIO_STREAM_DELAY_MS 50      // Delay between chunks

// WebSocket reconnect
#define WEBSOCKET_RECONNECT_INTERVAL 5000

// Camera retry settings
#define CAMERA_INIT_RETRIES 3
#define CAMERA_CAPTURE_TIMEOUT 5000

// Queue sizes
#define AUDIO_PLAYBACK_QUEUE_SIZE 20

// ==================== OPTIONAL FEATURES ====================

// Enable if you want servo to move on every detection
#define SERVO_ON_DETECTION false

// Enable verbose logging
#define VERBOSE_LOGGING false

// Enable memory debugging
#define DEBUG_MEMORY false

// ==================== DO NOT MODIFY BELOW THIS LINE ====================
// (Unless you know what you're doing)

// Camera model selection - AI Thinker ESP32-CAM
#define CAMERA_MODEL_AI_THINKER

// Camera pin definitions for AI Thinker ESP32-CAM
#ifdef CAMERA_MODEL_AI_THINKER
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
#endif

// Validate configuration
#if SAMPLE_RATE != 16000 && SAMPLE_RATE != 44100
  #warning "Sample rate should be 16000 or 44100 for best compatibility"
#endif

#if CAMERA_FPS > 30
  #warning "Camera FPS > 30 may cause performance issues"
#endif

#if RECORDING_DURATION_MS > 10000
  #warning "Recording duration > 10 seconds may cause memory issues"
#endif

// Helper macros
#define LOG_INFO(msg) if(DEBUG_SERIAL) { Serial.println(msg); }
#define LOG_DEBUG(msg) if(VERBOSE_LOGGING) { Serial.println(msg); }
#define LOG_ERROR(msg) Serial.println("❌ ERROR: " + String(msg))

#endif // CONFIG_H
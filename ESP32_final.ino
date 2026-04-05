#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <SD.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

// ================== PIN / HW CONFIG ==================

// I2C (OLED)
#define I2C_SDA      8
#define I2C_SCL      9
#define OLED_ADDR    0x3C

// GPS UART2
#define GPS_RX       16   // ESP32-S3 RX  <-- GPS TX
#define GPS_TX       17   // ESP32-S3 TX  --> GPS RX
#define GPS_BAUD     9600 // ถ้าเห็นตัวอักษรขยะ ลองเปลี่ยนเป็น 115200

// Buttons (active LOW: ปุ่มต่อ GND ตอนกด)
#define SW_LOG       6    // บันทึกจุดใหม่
#define SW_CLEAR     7    // เคลียร์ไฟล์ []
#define SW_UNDO      15   // ลบจุดล่าสุด

// LEDs สถานะ
#define LED_LOG      20   // ไฟเขียว
#define LED_CLEAR    21   // ไฟแดง
#define LED_UNDO     47   // ไฟเหลือง

// SD Card (SPI wiring)
#define SD_CS        10
#define SD_MOSI      11
#define SD_SCK       12
#define SD_MISO      13
const char *filename = "/noise_samples.json";

// ADC / RF detector
const int   PIN_ADC           = 1;      // ขา ADC ของ ESP32-S3
const float VREF              = 3.30;   // Vref ~3.3V
const int   N_SAMPLES         = 200;    // เที่ยวอ่านเฉลี่ยลด noise

// ค่าคาลิเบรตคร่าว ๆ แปลงแรงดัน -> dBm
const float SLOPE_mV_PER_dB   = -22.0f; // mV per dB (ประมาณ)
const float V_OFFSET_mV       = 0.0f;   // offset mV (จูนทีหลังได้)
const float P_INTERCEPT_dBm   = 14.0f;  // จุดตัดประมาณ (dBm)

// ================== GLOBAL OBJECTS ==================

HardwareSerial GPSserial(2); // UART2
TinyGPSPlus    gps;

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ================== STATE VARIABLES ==================

bool   lastLogState   = HIGH;
bool   lastClearState = HIGH;
bool   lastUndoState  = HIGH;

String lastActionMsg  = "IDLE";

float  lastVout       = 0.0f;    // โวลต์จาก detector
float  lastDbm        = 0.0f;    // dBm ล่าสุด
double lastLat        = 0.0;
double lastLng        = 0.0;
String lastTime       = "----";

// ================== RF / GPS HELPERS ==================

// อ่าน RF detector -> อัปเดต lastVout / lastDbm และคืน dBm
float readRFdBm() {
  uint32_t acc = 0;
  for (int i = 0; i < N_SAMPLES; i++) {
    acc += analogRead(PIN_ADC);
  }

  float adc_avg = acc / float(N_SAMPLES);   // ค่าเฉลี่ย ADC 0..4095
  lastVout = adc_avg * VREF / 4095.0f;      // โวลต์ที่อ่านได้

  float voutmV = lastVout * 1000.0f;        // mV
  lastDbm = P_INTERCEPT_dBm + (voutmV - V_OFFSET_mV) / SLOPE_mV_PER_dB;

  return lastDbm;
}

// เวลา UTC จาก GPS เป็นสตริง
String getGPSTimeString() {
  if (gps.date.isValid() && gps.time.isValid()) {
    char buf[25];
    sprintf(buf, "%04d-%02d-%02d %02d:%02d:%02d",
            gps.date.year(),
            gps.date.month(),
            gps.date.day(),
            gps.time.hour(),
            gps.time.minute(),
            gps.time.second());
    return String(buf);
  }
  return "0000-00-00 00:00:00";
}

// ================== OLED ==================

void updateOLED() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // หัวเรื่อง
  display.setCursor(45, 0);
  display.print("RF2.4G");

  // Vout
  display.setCursor(0, 10);
  display.print("Vout=");
  display.print(lastVout, 3);
  display.print(" V");

  // dBm
  display.setCursor(0, 20);
  display.print("Pin=");
  display.print(lastDbm, 1);
  display.print(" dBm");

  // Lat
  display.setCursor(0, 30);
  display.print("Lat=");
  display.print(lastLat, 6);

  // Lng
  display.setCursor(0, 40);
  display.print("Lng=");
  display.print(lastLng, 6);

  // Status line + Sats
  display.setCursor(0, 50);
  display.print("Status:");
  display.print(lastActionMsg);
  display.print("  Sat:");
  display.print(gps.satellites.value());


  display.display();
}

// ================== SD / JSON HELPERS ==================

// รวม array เดิม + จุดใหม่ -> ได้ array ใหม่
String appendJsonArray(const String &oldJson,
                       double lat,
                       double lng,
                       const String &timeStr,
                       float dbmVal) {

  // สร้าง entry ใหม่
  String newEntry = "{\"lat\":";
  newEntry += String(lat, 6);
  newEntry += ",\"lng\":";
  newEntry += String(lng, 6);
  newEntry += ",\"time\":\"";
  newEntry += timeStr;
  newEntry += "\",\"dbm\":";
  newEntry += String(dbmVal, 1);
  newEntry += "}";

  // ถ้าของเก่าไม่ใช่ array เลย / ว่าง
  if (!oldJson.startsWith("[")) {
    return "[" + newEntry + "]";
  }
  if (oldJson == "[]" || oldJson == "[ ]") {
    return "[" + newEntry + "]";
  }

  // หา ']' สุดท้าย แล้วแทรก ,entry ใหม่ก่อนปิด
  int lastBracket = oldJson.lastIndexOf(']');
  if (lastBracket == -1) {
    return "[" + newEntry + "]";
  }

  String before = oldJson.substring(0, lastBracket);
  String after  = oldJson.substring(lastBracket); // ปกติเป็น "]"
  return before + "," + newEntry + after;
}

// โหลดไฟล์ JSON ถ้าไม่มีให้คืน "[]"
String loadJsonFromSD() {
  if (!SD.exists(filename)) {
    Serial.println("ℹ SD: file not found -> []");
    return "[]";
  }

  File file = SD.open(filename, FILE_READ);
  if (!file) {
    Serial.println("❌ SD: open for read FAILED");
    return "[]";
  }

  String data = file.readString();
  file.close();

  Serial.print("ℹ SD: loaded old JSON len=");
  Serial.println(data.length());
  return data;
}

// เขียน JSON ใหม่ลงไฟล์ (ลบของเก่าแล้วเขียนใหม่)
bool saveJsonToSD(const String &data) {
  // ลบไฟล์เก่า (ถ้ามี)
  if (SD.exists(filename)) {
    if (!SD.remove(filename)) {
      Serial.println("❌ SD: remove old file FAILED (but continue)");
    }
  }

  File file = SD.open(filename, FILE_WRITE);
  if (!file) {
    Serial.println("❌ SD: open for write FAILED");
    return false;
  }

  size_t written = file.print(data);
  file.flush();
  file.close();

  Serial.print("💾 SD: wrote bytes=");
  Serial.println(written);

  if (written == 0) {
    Serial.println("❌ SD: write returned 0 bytes!");
    return false;
  }

  if (!SD.exists(filename)) {
    Serial.println("❌ SD: file missing after write??");
    return false;
  }

  Serial.println("✅ SD: File saved OK");
  return true;
}

// เคลียร์ไฟล์ -> เขียน [] ใหม่
bool clearFileOnSD() {
  if (SD.exists(filename)) {
    if (!SD.remove(filename)) {
      Serial.println("❌ SD: remove old file FAILED (clear)");
      // we'll still try rewrite
    }
  }

  File file = SD.open(filename, FILE_WRITE);
  if (!file) {
    Serial.println("❌ SD: open for write FAILED (clear)");
    return false;
  }

  size_t written = file.print("[]");
  file.flush();
  file.close();

  Serial.print("💾 SD: CLEAR wrote bytes=");
  Serial.println(written);

  if (written == 0) {
    Serial.println("❌ SD: CLEAR wrote 0 bytes?");
    return false;
  }

  Serial.println("🧹 SD: File cleared to []");
  return true;
}

// ลบ entry สุดท้ายออกจาก array
String removeLastEntry(const String &jsonIn) {
  String s = jsonIn;
  s.trim();
  if (!s.startsWith("[")) {
    return "[]";
  }

  int endBracket = s.lastIndexOf(']');
  if (endBracket == -1) {
    return "[]";
  }

  String inner = s.substring(1, endBracket); // ของใน []
  inner.trim();

  if (inner.length() == 0) {
    return "[]";
  }

  // หา comma สุดท้าย
  int lastComma = inner.lastIndexOf(',');
  if (lastComma == -1) {
    // มีจุดเดียว ก็เหลือ []
    return "[]";
  }

  String newInner = inner.substring(0, lastComma);
  newInner.trim();
  return "[" + newInner + "]";
}

bool undoLastPointOnSD() {
  String oldJson = loadJsonFromSD();
  Serial.println("↩ UNDO: old JSON:");
  Serial.println(oldJson);

  String newJson = removeLastEntry(oldJson);
  bool ok = saveJsonToSD(newJson);

  Serial.println("↩ UNDO: new JSON:");
  Serial.println(newJson);

  return ok;
}

// ================== BUTTON EDGE DETECT ==================

bool checkButtonPressed(uint8_t pin, bool &lastState) {
  bool current  = digitalRead(pin);
  bool pressed  = (lastState == HIGH && current == LOW);
  lastState     = current;
  return pressed;
}

// ================== SETUP ==================

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("=== ESP32-S3 RF LOGGER + GPS + SD + OLED ===");

  // I2C (OLED)
  Wire.begin(I2C_SDA, I2C_SCL);

  // SPI (SD)
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  // OLED init
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("❌ OLED not found!");
    lastActionMsg = "OLED ERR";
  } else {
    Serial.println("✅ OLED ready");
    display.clearDisplay();
    display.display();
  }

  // GPS UART2 init
  GPSserial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX, GPS_TX);
  Serial.print("GPS UART2 init @ ");
  Serial.print(GPS_BAUD);
  Serial.println(" baud");

  // BUTTONS with pull-up
  pinMode(SW_LOG,   INPUT_PULLUP);
  pinMode(SW_CLEAR, INPUT_PULLUP);
  pinMode(SW_UNDO,  INPUT_PULLUP);

  // LEDs
  pinMode(LED_LOG,   OUTPUT);
  pinMode(LED_CLEAR, OUTPUT);
  pinMode(LED_UNDO,  OUTPUT);
  digitalWrite(LED_LOG,   LOW);
  digitalWrite(LED_CLEAR, LOW);
  digitalWrite(LED_UNDO,  LOW);

  // SD CARD
  if (!SD.begin(SD_CS)) {
    Serial.println("❌ SD: mount failed. Check wiring CS/MOSI/MISO/SCK/3V3/GND");
    lastActionMsg = "SD ERR";
  } else {
    Serial.println("✅ SD: mounted OK");
    lastActionMsg = "READY";
  }

  // ADC config
  analogReadResolution(12);        // 0..4095
  analogSetAttenuation(ADC_11db);  // ช่วงประมาณ 0-3.3V

  Serial.print("Target file: ");
  Serial.println(filename);
  Serial.println("Ready. Walk + press LOG to save points.");
}

// ================== LOOP ==================

void loop() {
  // 1) อ่าน GPS UART แล้ว feed เข้า TinyGPSPlus
  while (GPSserial.available() > 0) {
    char c = GPSserial.read();
    gps.encode(c);
    // ถ้าอยากดู $GPGGA สด uncomment:
    // Serial.write(c);
  }

  // 2) อ่าน RF detector ตลอดเวลา
  readRFdBm();

  // 3) ถ้า GPS valid ให้เก็บค่าไว้ในตัวแปรโชว์/บันทึก
  if (gps.location.isValid()) {
    lastLat  = gps.location.lat();
    lastLng  = gps.location.lng();
    lastTime = getGPSTimeString();
  }

  // 4) Debug status ทุก 1 วิ
  static unsigned long lastStatus = 0;
  if (millis() - lastStatus > 1000) {
    lastStatus = millis();

    Serial.println("----------- STATUS -----------");
    if (gps.location.isValid()) {
      Serial.print("GPS OK  LAT=");
      Serial.print(lastLat, 6);
      Serial.print("  LNG=");
      Serial.print(lastLng, 6);
      Serial.print("  TIME=");
      Serial.println(lastTime);
    } else {
      Serial.println("GPS not fixed yet...");
    }

    Serial.print("Sats=");
    Serial.println(gps.satellites.value());

    Serial.print("RF dBm=");
    Serial.println(lastDbm, 1);
    Serial.println("------------------------------");
  }

  // 5) ปุ่ม LOG -> บันทึกจุดใหม่ลง SD เป็น JSON array
  if (checkButtonPressed(SW_LOG, lastLogState)) {
    Serial.println("🔘 LOG Button pressed!");

    if (!gps.location.isValid()) {
      Serial.println("⚠ Skip: GPS not fixed yet. No save.");
      lastActionMsg = "WAIT GPS";
      digitalWrite(LED_LOG, LOW);
    } else {
      // อ่าน RF อีกรอบตอนบันทึกจริง
      float rf_now = readRFdBm();

      double lat   = gps.location.lat();
      double lng   = gps.location.lng();
      String t     = getGPSTimeString();

      Serial.print("Will save point: lat=");
      Serial.print(lat, 6);
      Serial.print(" lng=");
      Serial.print(lng, 6);
      Serial.print(" rf=");
      Serial.print(rf_now, 1);
      Serial.print(" dBm time=");
      Serial.println(t);

      String oldJson = loadJsonFromSD();
      String newJson = appendJsonArray(oldJson, lat, lng, t, rf_now);
      bool ok        = saveJsonToSD(newJson);

      Serial.println("----- After Save, JSON is: -----");
      Serial.println(newJson);
      Serial.println("--------------------------------");

      if (!ok) {
        Serial.println("💥 ERROR: write failed (SD?)");
        lastActionMsg = "LOG ERR";
        digitalWrite(LED_LOG, LOW);
      } else {
        lastActionMsg = "LOG OK";
        digitalWrite(LED_LOG, HIGH);
        delay(200);
        digitalWrite(LED_LOG, LOW);
      }

      lastLat  = lat;
      lastLng  = lng;
      lastTime = t;
    }
  }

  // 6) ปุ่ม CLEAR -> เคลียร์ไฟล์ให้เหลือ []
  if (checkButtonPressed(SW_CLEAR, lastClearState)) {
    Serial.println("🧹 CLEAR Button pressed!");
    bool ok = clearFileOnSD();
    if (!ok) {
      Serial.println("💥 ERROR: CLEAR failed");
      lastActionMsg = "CLR ERR";
      digitalWrite(LED_CLEAR, LOW);
    } else {
      lastActionMsg = "CLEARED";
      digitalWrite(LED_CLEAR, HIGH);
      delay(200);
      digitalWrite(LED_CLEAR, LOW);
    }
  }

  // 7) ปุ่ม UNDO -> ลบ entry สุดท้าย
  if (checkButtonPressed(SW_UNDO, lastUndoState)) {
    Serial.println("↩ UNDO Button pressed!");
    bool ok = undoLastPointOnSD();
    if (!ok) {
      Serial.println("💥 ERROR: UNDO failed");
      lastActionMsg = "UNDO ERR";
      digitalWrite(LED_UNDO, LOW);
    } else {
      lastActionMsg = "UNDO OK";
      digitalWrite(LED_UNDO, HIGH);
      delay(200);
      digitalWrite(LED_UNDO, LOW);
    }
  }

  // 8) อัปเดตจอ
  updateOLED();

  delay(50);
}

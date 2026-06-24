#include <SCServo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// display 
constexpr uint8_t SCREEN_WIDTH  = 128;
constexpr uint8_t SCREEN_HEIGHT = 32;
constexpr int8_t  OLED_RESET    = -1;
constexpr uint8_t OLED_I2C_ADDR = 0x3C;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// servo bus 
constexpr uint32_t SERVO_BAUD    = 1000000;
constexpr int8_t   SERVO_RX_PIN  = 18;
constexpr int8_t   SERVO_TX_PIN  = 19;

// ST3215 register scaling (per datasheet)
constexpr float CURRENT_LSB_MA = 6.5f;   // Present Current  (reg 0x45) — 1 LSB = 6.5 mA
constexpr float VOLTAGE_LSB_V  = 0.1f;   // Present Voltage  (reg 0x3E) — 1 LSB = 0.1 V
constexpr int   POS_MIN        = 0;
constexpr int   POS_MAX        = 4095;

SMS_STS st;

// axes
struct AxisProfile {
  const char* name;
  uint16_t    speed;   // ~steps/s; useful range 0..~3500 (≈ 0.088 °/s per unit)
  uint8_t     accel;   // 0..254 (≈ 100 steps/s² per unit)
};

constexpr uint8_t NUM_AXES = 8;

// index == servo ID
const AxisProfile AXES[NUM_AXES] = {
  { "Base",            2200,   40 },   // 0  J1 yaw — whole-arm inertia

  // dual-drive shoulder pair 
  { "Shoulder L",      2048,   30 },   // 1  J2 pitch (paired with ID 2)
  { "Shoulder R",      2048,   30 },   // 2  J2 pitch (paired with ID 1)

  { "Elbow",           2000,   28 },   // 3  J3 pitch — single motor, longest lever
  { "Forearm Roll",    3500,  120 },   // 4  J4 roll  — paired pace with Wrist Roll
  { "Wrist Pitch",     2400,   60 },   // 5  J5 pitch — lifts gripper against gravity
  { "Wrist Roll",      3500,  120 },   // 6  J6 roll  — paired pace with Forearm Roll
  { "Gripper",         3500,  180 },   // 7  EE      — near-zero inertia, snappy
};

bool servo_active[NUM_AXES] = {false};

// helpers 
static inline bool valid_id(int id) {
  return id >= 0 && id < (int)NUM_AXES;
}

static inline bool in_pos_range(int pos) {
  return pos >= POS_MIN && pos <= POS_MAX;
}

void oled_show(const String& l1, const String& l2 = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(l1);
  if (l2.length()) {
    display.setCursor(0, 12);
    display.println(l2);
  }
  display.display();
}

bool write_axis(uint8_t id, int pos) {
  if (!valid_id(id) || !in_pos_range(pos)) return false;
  if (!servo_active[id])                   return false;
  const AxisProfile& a = AXES[id];
  st.WritePosEx(id, pos, a.speed, a.accel);
  return true;
}

void scan_hardware() {
  Serial.println(F("[SYS] hardware discovery"));
  for (uint8_t i = 0; i < NUM_AXES; i++) {
    int pos = st.ReadPos(i);
    servo_active[i] = (pos != -1);

    Serial.print(AXES[i].name);
    Serial.print(F(" (ID "));
    Serial.print(i);
    Serial.print(F("): "));
    Serial.println(servo_active[i] ? F("ACTIVE") : F("NOT FOUND"));
    delay(50);
  }
}

void print_stat() {
  Serial.println(F("[STAT] hardware telemetry"));
  for (uint8_t i = 0; i < NUM_AXES; i++) {
    if (!servo_active[i]) continue;

    int t_raw = st.ReadTemper(i);
    int v_raw = st.ReadVoltage(i);
    int c_raw = st.ReadCurrent(i);

    Serial.print(AXES[i].name);
    Serial.print(F(" (ID "));
    Serial.print(i);
    Serial.print(F(") -> "));

    if (t_raw == -1 || v_raw == -1 || c_raw == -1) {
      Serial.print(F("[ERR] read error ("));
      Serial.print(t_raw); Serial.print(F(","));
      Serial.print(v_raw); Serial.print(F(","));
      Serial.print(c_raw); Serial.println(F(")"));
      continue;
    }

    float volts = v_raw * VOLTAGE_LSB_V;
    float mA    = c_raw * CURRENT_LSB_MA;

    Serial.print(F("Temp: "));       Serial.print(t_raw);  Serial.print(F("C"));
    Serial.print(F(" | Volt: "));    Serial.print(volts, 1); Serial.print(F("V"));
    Serial.print(F(" | Current: ")); Serial.print(mA, 1);  Serial.println(F(" mA"));
  }
}

void handle_move(const String& data) {
  int comma = data.indexOf(',');
  if (comma <= 0) {
    Serial.println(F("[ERR] malformed command"));
    return;
  }

  int id  = data.substring(0, comma).toInt();
  int pos = data.substring(comma + 1).toInt();

  if (!valid_id(id)) {
    Serial.print(F("[ERR] invalid ID ")); Serial.println(id);
    return;
  }
  if (!in_pos_range(pos)) {
    Serial.print(F("[ERR] pos out of range: ")); Serial.println(pos);
    return;
  }
  if (!servo_active[id]) {
    Serial.print(F("[ERR] servo ")); Serial.print(id);
    Serial.println(F(" not active"));
    return;
  }
  if (!write_axis((uint8_t)id, pos)) {
    Serial.println(F("[ERR] write failed"));
  }
}

// arduino 
void setup() {
  Serial.begin(115200);
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, SERVO_RX_PIN, SERVO_TX_PIN);
  st.pSerial = &Serial1;

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    Serial.println(F("[ERR] SSD1306 init failed"));
  }
  oled_show("Waiting for IP...");

  delay(2000);
  scan_hardware();
  Serial.println(F("[SYS] esp32 bridge ready"));
}

void loop() {
  if (!Serial.available()) return;

  String data = Serial.readStringUntil('\n');
  data.trim();
  if (!data.length()) return;

  if (data.startsWith("ip,")) {
    oled_show("Robot IP Address:", data.substring(3));
    Serial.println(F("[SYS] OLED updated with IP"));
  }
  else if (data.equalsIgnoreCase("stat")) {
    print_stat();
  }
  else if (data.equalsIgnoreCase("reset")) {
    scan_hardware();
  }
  else {
    handle_move(data);
  }
}


 

 
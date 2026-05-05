#include <SCServo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

SMS_STS st;

bool servo_active[8];
String axis_names[8] = {
  "Base", "Shoulder L", "Shoulder R", "Upperarm", 
  "Elbow", "Forearm", "Wrist", "Gripper"
};

void scan_hardware() {
  Serial.println("[SYS] hardware discovery");
  
  for (int i = 0; i < 8; i++) {
    int check = st.ReadPos(i);
    Serial.print(axis_names[i]);
    Serial.print(" (ID "); 
    Serial.print(i); 
    Serial.print("): ");
    
    if (check != -1) {
      servo_active[i] = true;
      Serial.println("ACTIVE");
    } else {
      servo_active[i] = false;
      Serial.println("NOT FOUND");
    }
    delay(50); 
  }
}

void setup() {
  Serial.begin(115200); 
  Serial1.begin(1000000, SERIAL_8N1, 18, 19); 
  st.pSerial = &Serial1;

  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("SSD1306 allocation failed"));
  }
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Waiting for IP...");
  display.display();

  delay(2000);
  scan_hardware();
  Serial.println("[SYS] esp32 bridge ready");
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() == 0) return;

    if (data.startsWith("ip,")) {
      String ip_str = data.substring(3); 
      
      display.clearDisplay();
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.println("Robot IP Address:");
      display.setCursor(0, 12);
      display.println(ip_str);
      display.display();
      
      Serial.println("[SYS] OLED updated with IP");
    }
    else if (data.equalsIgnoreCase("stat")) {
      Serial.println("[STAT] hardware telemetry");
      for (int i = 0; i < 8; i++) {
        if (!servo_active[i]) continue;
        
        int temp = st.ReadTemper(i);
        int volt = st.ReadVoltage(i); 
        int curr = st.ReadCurrent(i); 
        
        Serial.print(axis_names[i]); 
        Serial.print(" (ID "); 
        Serial.print(i); 
        Serial.print(") -> ");
        
        if (temp != -1) {
          Serial.print("Temp: "); 
          Serial.print(temp); 
          Serial.print("C | Volt: "); 
          Serial.print(volt / 10.0, 1); 
          Serial.print("V | Current: "); 
          Serial.print(curr); 
          Serial.println("mA");
        } else {
          Serial.println("[ERR] read error");
        }
      }
    } 
    else if (data.equalsIgnoreCase("reset")) {
      scan_hardware();
    }
    else {
      int commaIdx = data.indexOf(',');
      if (commaIdx > 0) {
        int id = data.substring(0, commaIdx).toInt();
        int pos = data.substring(commaIdx + 1).toInt();
        
        if (pos >= 0 && pos <= 4095) {
          if (id == 0 || id == 1 || id == 2 || id == 3 || id == 5) {
            st.WritePosEx(id, pos, 2048, 32); 
          } else if (id == 4 || id == 6 || id == 7) {
            st.WritePosEx(id, pos, 3400, 64); 
          }
        }
      }
    }
  }
}
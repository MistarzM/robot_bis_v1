#include <SCServo.h>

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

  delay(2000);
  scan_hardware();
  Serial.println("[SYS] esp32 bridge ready");
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() == 0) return;

    if (data.equalsIgnoreCase("stat")) {
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
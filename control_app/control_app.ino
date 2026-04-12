#include <SCServo.h>

SMS_STS st; 

// hardware tracking array
bool servo_active[8]; 
String axis_names[8] = {
  "Base", "Shoulder L", "Shoulder R", "Upperarm", 
  "Elbow", "Forearm", "Wrist", "Gripper"
};

// hardware scan function
void scan_hardware() {
  Serial.println("\n==================================");
  Serial.println("  SYSTEM BOOT: HARDWARE SCAN");
  Serial.println("==================================");
  
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
  Serial.println("==================================\n");
}

void setup() {
  Serial.begin(115200); 
  Serial1.begin(1000000, SERIAL_8N1, 18, 19); 
  st.pSerial = &Serial1;

  delay(2000); 
  scan_hardware(); 
  Serial.println("ESP32 BRIDGE READY");
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim(); 

    if (data.length() == 0) return; 

    // command: stat 
    if (data.equalsIgnoreCase("stat") || data.equalsIgnoreCase("stats")) {
      Serial.println("=== HARDWARE STATS ===");
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
          Serial.println("READ ERROR!");
        }
      }
      Serial.println("==========================");
    }
    // command: servo movemnt - format: id, pos
    else {
      int comma_idx = data.indexOf(',');
      if (comma_idx > 0) {
        int id = data.substring(0, comma_idx).toInt();
        int pos = data.substring(comma_idx + 1).toInt();

        // safety limit check
        if (pos >= 0 && pos <= 4095) {
          st.WritePosEx(id, pos, 0, 0);
        }
      }
    }
  }
}

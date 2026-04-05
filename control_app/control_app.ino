#include <SCServo.h>

SMS_STS st; 

// VIRTUAL POSITIONS (Custom Home Positions)
int pos_base = 2147;
int pos_shoulder = 3547;
int pos_upperarm = 1747;
int pos_elbow = 2147;
int pos_forearm = 1547;
int pos_wrist = 2047;
int pos_gripper = 2847;

int step_size = 100;
int move_speed = 200;

// SOFT LIMITS 
int shoulder_max = 3847;
int shoulder_min = 1747;
int gripper_max = 3947;
int gripper_min = 2047;

// HARDWARE TRACKING ARRAY 
bool servo_active[8]; 
String axis_names[8] = {
  "Base", "Shoulder L", "Shoulder R", "Upperarm", 
  "Elbow", "Forearm", "Wrist", "Gripper"
};

// HARDWARE SCAN FUNCTION (Auto-Discovery) 
void scan_hardware() {
  Serial.println("\n==================================");
  Serial.println("  SYSTEM BOOT / RESET: HARDWARE SCAN");
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

// SMART HOMING FUNCTION 
void go_home() {
  // Reset all target variables to their custom safe home positions
  pos_base = 2147; 
  pos_shoulder = 3547; 
  pos_upperarm = 1747; 
  pos_elbow = 2147; 
  pos_forearm = 1547; 
  pos_wrist = 2047; 
  pos_gripper = 2847;
  
  Serial.println("=== EXECUTING SMART HOMING ===");
  
  if (servo_active[0]) {
    Serial.print("Moving Base (ID 0) to "); 
    Serial.println(pos_base);
    st.WritePosEx(0, pos_base, move_speed, 50); 
    delay(4000); 
  }
  
  if (servo_active[1] || servo_active[2]) {
    Serial.print("Moving Shoulder (ID 1 & 2) to "); 
    Serial.println(pos_shoulder);
    
    if (servo_active[1]) {
      st.WritePosEx(1, pos_shoulder, move_speed, 50);      
    }
    if (servo_active[2]) {
      st.WritePosEx(2, 4095 - pos_shoulder, move_speed, 50); 
    }
    delay(4000); 
  }

  if (servo_active[3]) {
    Serial.print("Moving Upperarm (ID 3) to "); 
    Serial.println(pos_upperarm);
    st.WritePosEx(3, pos_upperarm, move_speed, 50); 
    delay(4000); 
  }

  if (servo_active[4]) {
    Serial.print("Moving Elbow (ID 4) to "); 
    Serial.println(pos_elbow);
    st.WritePosEx(4, pos_elbow, move_speed, 50); 
    delay(4000); 
  }
  
  if (servo_active[5]) {
    Serial.print("Moving Forearm (ID 5) to "); 
    Serial.println(pos_forearm);
    st.WritePosEx(5, pos_forearm, move_speed, 50); 
    delay(4000); 
  }

  if (servo_active[6]) {
    Serial.print("Moving Wrist (ID 6) to "); 
    Serial.println(pos_wrist);
    st.WritePosEx(6, pos_wrist, move_speed, 50); 
    delay(4000); 
  }

  if (servo_active[7]) {
    Serial.print("Moving Gripper (ID 7) to "); 
    Serial.println(pos_gripper);
    st.WritePosEx(7, pos_gripper, move_speed, 50); 
    delay(4000); 
  }
  
  Serial.println("Homing complete. Ready for action!");
}

void setup() {
  Serial.begin(115200); 
  Serial1.begin(1000000, SERIAL_8N1, 18, 19); 
  st.pSerial = &Serial1;

  delay(2000); 
  
  scan_hardware(); 
  go_home();       

  Serial.println("AVAILABLE COMMANDS:");
  Serial.println("- 'q'/'a' (Base)   | 'w'/'s' (Shoulder)");
  Serial.println("- 'e'/'d' (Upper)  | 'r'/'f' (Elbow)");
  Serial.println("- 't'/'g' (Fore)   | 'y'/'h' (Wrist)");
  Serial.println("- 'u'/'j' (Gripper)");
  Serial.println("- 'default' | 'stat' | 'pos' | 'reset'");
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim(); 

    if (cmd.length() == 0) {
      return; 
    }

    // COMMAND: RESET (Hot-swap devices) 
    if (cmd.equalsIgnoreCase("reset")) {
      Serial.println("=== INITIATING SYSTEM RESET ===");
      scan_hardware();
      go_home();
    }
    // COMMAND: DEFAULT 
    else if (cmd.equalsIgnoreCase("default")) {
      go_home();
    }
    // COMMAND: STAT / TEMP 
    else if (cmd.equalsIgnoreCase("stat") || cmd.equalsIgnoreCase("temp")) {
      Serial.println("=== HARDWARE TELEMETRY ===");
      for (int i = 0; i < 8; i++) {
        if (!servo_active[i]) {
          continue; 
        }
        
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
    // COMMAND: POS 
    else if (cmd.equalsIgnoreCase("pos")) {
      Serial.println("=== ACTUAL PHYSICAL POSITIONS ===");
      for (int i = 0; i < 8; i++) {
        if (!servo_active[i]) {
          continue;
        }
        int p = st.ReadPos(i);
        Serial.print(axis_names[i]); 
        Serial.print(" (ID "); 
        Serial.print(i); 
        Serial.print("): ");
        
        if (p != -1) {
          Serial.println(p);
        } else {
          Serial.println("READ ERROR!");
        }
      }
      Serial.println("---------------------------------");
    }
    // MANUAL MOVEMENT 
    else if (cmd.length() == 1) {
      char key = cmd.charAt(0);
      switch(key) {
        
        // 1st DOF - BASE (ID 0) Q/A 
        case 'q': case 'Q': {
          if (!servo_active[0]) { 
            Serial.println("Base servo not active!"); 
            break; 
          }
          if (pos_base + step_size >= 4095) { 
            pos_base = 4095; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_base += step_size;
          }
          
          st.WritePosEx(0, pos_base, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(0); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Base pos: "); 
          Serial.print(pos_base); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'a': case 'A': {
          if (!servo_active[0]) { 
            Serial.println("Base servo not active!"); 
            break; 
          }
          if (pos_base - step_size <= 0) { 
            pos_base = 0; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_base -= step_size;
          }
          
          st.WritePosEx(0, pos_base, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(0); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Base pos: "); 
          Serial.print(pos_base); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        // 2nd DOF - SHOULDER (ID 1 & 2) W/S
        case 'w': case 'W': {
          if (!servo_active[1] && !servo_active[2]) { 
            Serial.println("Shoulder servos not active!"); 
            break; 
          }
          if (pos_shoulder + step_size >= shoulder_max) { 
            pos_shoulder = shoulder_max; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_shoulder += step_size;
          }
          
          if (servo_active[1]) {
            st.WritePosEx(1, pos_shoulder, move_speed, 50); 
          }
          if (servo_active[2]) {
            st.WritePosEx(2, 4095 - pos_shoulder, move_speed, 50); 
          }
          
          int m1 = 0, m2 = 0;
          for (int i = 0; i < 20; i++) { 
            if (servo_active[1]) { 
              int c1 = st.ReadCurrent(1); 
              if (c1 > m1) {
                m1 = c1; 
              }
            }
            if (servo_active[2]) { 
              int c2 = st.ReadCurrent(2); 
              if (c2 > m2) {
                m2 = c2; 
              }
            }
            delay(10); 
          }
          
          Serial.print("Shoulder pos: "); 
          Serial.print(pos_shoulder); 
          Serial.print(" | ID1 PEAK: "); 
          Serial.print(m1); 
          Serial.print("mA | ID2 PEAK: "); 
          Serial.print(m2); 
          Serial.println("mA");
          break;
        }
        case 's': case 'S': {
          if (!servo_active[1] && !servo_active[2]) { 
            Serial.println("Shoulder servos not active!"); 
            break; 
          }
          if (pos_shoulder - step_size <= shoulder_min) { 
            pos_shoulder = shoulder_min; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_shoulder -= step_size;
          }
          
          if (servo_active[1]) {
            st.WritePosEx(1, pos_shoulder, move_speed, 50); 
          }
          if (servo_active[2]) {
            st.WritePosEx(2, 4095 - pos_shoulder, move_speed, 50); 
          }
          
          int m1 = 0, m2 = 0;
          for (int i = 0; i < 20; i++) { 
            if (servo_active[1]) { 
              int c1 = st.ReadCurrent(1); 
              if (c1 > m1) {
                m1 = c1; 
              }
            }
            if (servo_active[2]) { 
              int c2 = st.ReadCurrent(2); 
              if (c2 > m2) {
                m2 = c2; 
              }
            }
            delay(10); 
          }
          
          Serial.print("Shoulder pos: "); 
          Serial.print(pos_shoulder); 
          Serial.print(" | ID1 PEAK: "); 
          Serial.print(m1); 
          Serial.print("mA | ID2 PEAK: "); 
          Serial.print(m2); 
          Serial.println("mA");
          break;
        }

        // 3rd DOF - UPPERARM (ID 3) E/D
        case 'e': case 'E': {
          if (!servo_active[3]) { 
            Serial.println("Upperarm servo not active!"); 
            break; 
          }
          if (pos_upperarm + step_size >= 4095) { 
            pos_upperarm = 4095; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_upperarm += step_size;
          }
          
          st.WritePosEx(3, pos_upperarm, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(3); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Upperarm pos: "); 
          Serial.print(pos_upperarm); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'd': case 'D': {
          if (!servo_active[3]) { 
            Serial.println("Upperarm servo not active!"); 
            break; 
          }
          if (pos_upperarm - step_size <= 0) { 
            pos_upperarm = 0; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_upperarm -= step_size;
          }
          
          st.WritePosEx(3, pos_upperarm, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(3); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Upperarm pos: "); 
          Serial.print(pos_upperarm); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        // 4th DOF - ELBOW (ID 4) R/F
        case 'r': case 'R': {
          if (!servo_active[4]) { 
            Serial.println("Elbow servo not active!"); 
            break; 
          }
          if (pos_elbow + step_size >= 4095) { 
            pos_elbow = 4095; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_elbow += step_size;
          }
          
          st.WritePosEx(4, pos_elbow, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(4); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Elbow pos: "); 
          Serial.print(pos_elbow); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'f': case 'F': {
          if (!servo_active[4]) { 
            Serial.println("Elbow servo not active!"); 
            break; 
          }
          if (pos_elbow - step_size <= 0) { 
            pos_elbow = 0; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_elbow -= step_size;
          }
          
          st.WritePosEx(4, pos_elbow, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(4); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Elbow pos: "); 
          Serial.print(pos_elbow); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        // 5th DOF - FOREARM (ID 5) T/G
        case 't': case 'T': {
          if (!servo_active[5]) { 
            Serial.println("Forearm servo not active!"); 
            break; 
          }
          if (pos_forearm + step_size >= 4095) { 
            pos_forearm = 4095; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_forearm += step_size;
          }
          
          st.WritePosEx(5, pos_forearm, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(5); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Forearm pos: "); 
          Serial.print(pos_forearm); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'g': case 'G': {
          if (!servo_active[5]) { 
            Serial.println("Forearm servo not active!"); 
            break; 
          }
          if (pos_forearm - step_size <= 0) { 
            pos_forearm = 0; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_forearm -= step_size;
          }
          
          st.WritePosEx(5, pos_forearm, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(5); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Forearm pos: "); 
          Serial.print(pos_forearm); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        // 6th DOF - WRIST (ID 6) Y/H
        case 'y': case 'Y': {
          if (!servo_active[6]) { 
            Serial.println("Wrist servo not active!"); 
            break; 
          }
          if (pos_wrist + step_size >= 4095) { 
            pos_wrist = 4095; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_wrist += step_size;
          }
          
          st.WritePosEx(6, pos_wrist, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(6); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Wrist pos: "); 
          Serial.print(pos_wrist); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'h': case 'H': {
          if (!servo_active[6]) { 
            Serial.println("Wrist servo not active!"); 
            break; 
          }
          if (pos_wrist - step_size <= 0) { 
            pos_wrist = 0; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_wrist -= step_size;
          }
          
          st.WritePosEx(6, pos_wrist, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(6); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Wrist pos: "); 
          Serial.print(pos_wrist); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        // GRIPPER (ID 7) U/J
        case 'u': case 'U': {
          if (!servo_active[7]) { 
            Serial.println("Gripper servo not active!"); 
            break; 
          }
          if (pos_gripper + step_size >= gripper_max) { 
            pos_gripper = gripper_max; 
            Serial.print("[ MAX LIMIT ] "); 
          } else {
            pos_gripper += step_size;
          }
          
          st.WritePosEx(7, pos_gripper, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(7); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Gripper pos: "); 
          Serial.print(pos_gripper); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }
        case 'j': case 'J': {
          if (!servo_active[7]) { 
            Serial.println("Gripper servo not active!"); 
            break; 
          }
          if (pos_gripper - step_size <= gripper_min) { 
            pos_gripper = gripper_min; 
            Serial.print("[ MIN LIMIT ] "); 
          } else {
            pos_gripper -= step_size;
          }
          
          st.WritePosEx(7, pos_gripper, move_speed, 50); 
          
          int max_i = 0; 
          for (int i = 0; i < 20; i++) { 
            int c = st.ReadCurrent(7); 
            if (c > max_i) {
              max_i = c; 
            }
            delay(10); 
          }
          
          Serial.print("Gripper pos: "); 
          Serial.print(pos_gripper); 
          Serial.print(" | PEAK I: "); 
          Serial.print(max_i); 
          Serial.println("mA");
          break;
        }

        default:
          Serial.println("Unknown key!");
          break;
      }
    } else {
      Serial.println("Unknown command! Type a key, 'default', 'stat', 'pos' or 'reset'.");
    }
  }
}

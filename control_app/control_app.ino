#include <SCServo.h>

SMS_STS st; 

// --- VIRTUAL POSITIONS (Custom Home Positions) ---
int posBase = 2147;    
int posShoulder = 3547; 
int posUpperarm = 1747; 
int posElbow = 2147;    
int posForearm = 1547;  
int posWrist = 2047;    
int posGripper = 2847;  

int stepSize = 100; 
int moveSpeed = 200; 

// --- SOFT LIMITS ---
int shoulderMax = 3847; 
int shoulderMin = 1747; 
int gripperMax = 3947; 
int gripperMin = 2047; 

// --- HARDWARE TRACKING ARRAY ---
bool servoActive[8]; 
String axisNames[8] = {
  "Base", "Shoulder L", "Shoulder R", "Upperarm", 
  "Elbow", "Forearm", "Wrist", "Gripper"
};

// --- HARDWARE SCAN FUNCTION (Auto-Discovery) ---
void scanHardware() {
  Serial.println("\n==================================");
  Serial.println("  SYSTEM BOOT / RESET: HARDWARE SCAN");
  Serial.println("==================================");
  
  for (int i = 0; i < 8; i++) {
    int check = st.ReadPos(i);
    Serial.print(axisNames[i]);
    Serial.print(" (ID "); Serial.print(i); Serial.print("): ");
    
    if (check != -1) {
      servoActive[i] = true;
      Serial.println("ACTIVE");
    } else {
      servoActive[i] = false;
      Serial.println("NOT FOUND");
    }
    delay(50); 
  }
  Serial.println("==================================\n");
}

// --- SMART HOMING FUNCTION ---
void goHome() {
  // Reset all target variables to their custom safe home positions
  posBase = 2147; 
  posShoulder = 3547; 
  posUpperarm = 1747; 
  posElbow = 2147; 
  posForearm = 1547; 
  posWrist = 2047; 
  posGripper = 2847;
  
  Serial.println("--- EXECUTING SMART HOMING ---");
  
  if (servoActive[0]) {
    Serial.println("Moving Base (ID 0) to 2147...");
    st.WritePosEx(0, posBase, moveSpeed, 50); 
    delay(4000); 
  }
  
  if (servoActive[1] || servoActive[2]) {
    Serial.println("Moving Shoulder (ID 1 & 2) to 3547...");
    if(servoActive[1]) st.WritePosEx(1, posShoulder, moveSpeed, 50);      
    if(servoActive[2]) st.WritePosEx(2, 4095 - posShoulder, moveSpeed, 50); 
    delay(4000); 
  }

  if (servoActive[3]) {
    Serial.println("Moving Upperarm (ID 3) to 1747...");
    st.WritePosEx(3, posUpperarm, moveSpeed, 50); 
    delay(4000); 
  }

  if (servoActive[4]) {
    Serial.println("Moving Elbow (ID 4) to 2147...");
    st.WritePosEx(4, posElbow, moveSpeed, 50); 
    delay(4000); 
  }
  
  if (servoActive[5]) {
    Serial.println("Moving Forearm (ID 5) to 1547...");
    st.WritePosEx(5, posForearm, moveSpeed, 50); 
    delay(4000); 
  }

  if (servoActive[6]) {
    Serial.println("Moving Wrist (ID 6) to 2047...");
    st.WritePosEx(6, posWrist, moveSpeed, 50); 
    delay(4000); 
  }

  if (servoActive[7]) {
    Serial.println("Moving Gripper (ID 7) to 2847...");
    st.WritePosEx(7, posGripper, moveSpeed, 50); 
    delay(4000); 
  }
  
  Serial.println("Homing complete. Ready for action!");
}

void setup() {
  Serial.begin(115200); 
  Serial1.begin(1000000, SERIAL_8N1, 18, 19); 
  st.pSerial = &Serial1;

  delay(2000); 
  
  scanHardware(); // Run initial discovery
  goHome();       // Run safe homing based on discovery

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

    if (cmd.length() == 0) return; 

    // --- COMMAND: RESET (Hot-swap devices) ---
    if (cmd.equalsIgnoreCase("reset")) {
      Serial.println("--- INITIATING SYSTEM RESET ---");
      scanHardware();
      goHome();
    }
    // --- COMMAND: DEFAULT ---
    else if (cmd.equalsIgnoreCase("default")) {
      goHome();
    }
    // --- COMMAND: STAT / TEMP ---
    else if (cmd.equalsIgnoreCase("stat") || cmd.equalsIgnoreCase("temp")) {
      Serial.println("--- HARDWARE TELEMETRY ---");
      for (int i = 0; i < 8; i++) {
        if (!servoActive[i]) continue; // Skip disconnected servos
        
        int temp = st.ReadTemper(i);
        int volt = st.ReadVoltage(i); 
        int curr = st.ReadCurrent(i); 
        
        Serial.print(axisNames[i]); Serial.print(" (ID "); Serial.print(i); Serial.print(") -> ");
        if (temp != -1) {
          Serial.print("Temp: "); Serial.print(temp); Serial.print("C | ");
          Serial.print("Volt: "); Serial.print(volt / 10.0, 1); Serial.print("V | ");
          Serial.print("Current: "); Serial.print(curr); Serial.println("mA");
        } else {
          Serial.println("READ ERROR!");
        }
      }
      Serial.println("--------------------------");
    }
    // --- COMMAND: POS ---
    else if (cmd.equalsIgnoreCase("pos")) {
      Serial.println("--- ACTUAL PHYSICAL POSITIONS ---");
      for (int i = 0; i < 8; i++) {
        if (!servoActive[i]) continue;
        int p = st.ReadPos(i);
        Serial.print(axisNames[i]); Serial.print(" (ID "); Serial.print(i); Serial.print("): ");
        if (p != -1) Serial.println(p);
        else Serial.println("READ ERROR!");
      }
      Serial.println("---------------------------------");
    }
    // --- MANUAL MOVEMENT ---
    else if (cmd.length() == 1) {
      char key = cmd.charAt(0);
      switch(key) {
        
        // --- BASE (ID 0) Q/A ---
        case 'q': case 'Q': {
          if (!servoActive[0]) { Serial.println("Base servo not active!"); break; }
          if (posBase + stepSize >= 4095) { posBase = 4095; Serial.print("[ MAX LIMIT ] "); } 
          else posBase += stepSize;
          
          st.WritePosEx(0, posBase, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(0); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Base pos: "); Serial.print(posBase); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'a': case 'A': {
          if (!servoActive[0]) { Serial.println("Base servo not active!"); break; }
          if (posBase - stepSize <= 0) { posBase = 0; Serial.print("[ MIN LIMIT ] "); } 
          else posBase -= stepSize;
          
          st.WritePosEx(0, posBase, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(0); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Base pos: "); Serial.print(posBase); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        // --- SHOULDER (ID 1 & 2) W/S ---
        case 'w': case 'W': {
          if (!servoActive[1] && !servoActive[2]) { Serial.println("Shoulder servos not active!"); break; }
          if (posShoulder + stepSize >= shoulderMax) { posShoulder = shoulderMax; Serial.print("[ MAX LIMIT ] "); } 
          else posShoulder += stepSize;
          
          if(servoActive[1]) st.WritePosEx(1, posShoulder, moveSpeed, 50); 
          if(servoActive[2]) st.WritePosEx(2, 4095 - posShoulder, moveSpeed, 50); 
          
          int m1=0, m2=0;
          for (int i=0; i<20; i++) { 
            if(servoActive[1]){ int c1=st.ReadCurrent(1); if(c1>m1) m1=c1; }
            if(servoActive[2]){ int c2=st.ReadCurrent(2); if(c2>m2) m2=c2; }
            delay(10); 
          }
          Serial.print("Shoulder pos: "); Serial.print(posShoulder); 
          Serial.print(" | ID1 PEAK: "); Serial.print(m1); Serial.print("mA | ID2 PEAK: "); Serial.print(m2); Serial.println("mA");
          break;
        }
        case 's': case 'S': {
          if (!servoActive[1] && !servoActive[2]) { Serial.println("Shoulder servos not active!"); break; }
          if (posShoulder - stepSize <= shoulderMin) { posShoulder = shoulderMin; Serial.print("[ MIN LIMIT ] "); } 
          else posShoulder -= stepSize;
          
          if(servoActive[1]) st.WritePosEx(1, posShoulder, moveSpeed, 50); 
          if(servoActive[2]) st.WritePosEx(2, 4095 - posShoulder, moveSpeed, 50); 
          
          int m1=0, m2=0;
          for (int i=0; i<20; i++) { 
            if(servoActive[1]){ int c1=st.ReadCurrent(1); if(c1>m1) m1=c1; }
            if(servoActive[2]){ int c2=st.ReadCurrent(2); if(c2>m2) m2=c2; }
            delay(10); 
          }
          Serial.print("Shoulder pos: "); Serial.print(posShoulder); 
          Serial.print(" | ID1 PEAK: "); Serial.print(m1); Serial.print("mA | ID2 PEAK: "); Serial.print(m2); Serial.println("mA");
          break;
        }

        // --- UPPERARM (ID 3) E/D ---
        case 'e': case 'E': {
          if (!servoActive[3]) { Serial.println("Upperarm servo not active!"); break; }
          if (posUpperarm + stepSize >= 4095) { posUpperarm = 4095; Serial.print("[ MAX LIMIT ] "); } 
          else posUpperarm += stepSize;
          
          st.WritePosEx(3, posUpperarm, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(3); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Upperarm pos: "); Serial.print(posUpperarm); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'd': case 'D': {
          if (!servoActive[3]) { Serial.println("Upperarm servo not active!"); break; }
          if (posUpperarm - stepSize <= 0) { posUpperarm = 0; Serial.print("[ MIN LIMIT ] "); } 
          else posUpperarm -= stepSize;
          
          st.WritePosEx(3, posUpperarm, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(3); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Upperarm pos: "); Serial.print(posUpperarm); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        // --- ELBOW (ID 4) R/F ---
        case 'r': case 'R': {
          if (!servoActive[4]) { Serial.println("Elbow servo not active!"); break; }
          if (posElbow + stepSize >= 4095) { posElbow = 4095; Serial.print("[ MAX LIMIT ] "); } 
          else posElbow += stepSize;
          
          st.WritePosEx(4, posElbow, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(4); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Elbow pos: "); Serial.print(posElbow); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'f': case 'F': {
          if (!servoActive[4]) { Serial.println("Elbow servo not active!"); break; }
          if (posElbow - stepSize <= 0) { posElbow = 0; Serial.print("[ MIN LIMIT ] "); } 
          else posElbow -= stepSize;
          
          st.WritePosEx(4, posElbow, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(4); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Elbow pos: "); Serial.print(posElbow); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        // --- FOREARM (ID 5) T/G ---
        case 't': case 'T': {
          if (!servoActive[5]) { Serial.println("Forearm servo not active!"); break; }
          if (posForearm + stepSize >= 4095) { posForearm = 4095; Serial.print("[ MAX LIMIT ] "); } 
          else posForearm += stepSize;
          
          st.WritePosEx(5, posForearm, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(5); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Forearm pos: "); Serial.print(posForearm); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'g': case 'G': {
          if (!servoActive[5]) { Serial.println("Forearm servo not active!"); break; }
          if (posForearm - stepSize <= 0) { posForearm = 0; Serial.print("[ MIN LIMIT ] "); } 
          else posForearm -= stepSize;
          
          st.WritePosEx(5, posForearm, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(5); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Forearm pos: "); Serial.print(posForearm); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        // --- WRIST (ID 6) Y/H ---
        case 'y': case 'Y': {
          if (!servoActive[6]) { Serial.println("Wrist servo not active!"); break; }
          if (posWrist + stepSize >= 4095) { posWrist = 4095; Serial.print("[ MAX LIMIT ] "); } 
          else posWrist += stepSize;
          
          st.WritePosEx(6, posWrist, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(6); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Wrist pos: "); Serial.print(posWrist); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'h': case 'H': {
          if (!servoActive[6]) { Serial.println("Wrist servo not active!"); break; }
          if (posWrist - stepSize <= 0) { posWrist = 0; Serial.print("[ MIN LIMIT ] "); } 
          else posWrist -= stepSize;
          
          st.WritePosEx(6, posWrist, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(6); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Wrist pos: "); Serial.print(posWrist); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        // --- GRIPPER (ID 7) U/J ---
        case 'u': case 'U': {
          if (!servoActive[7]) { Serial.println("Gripper servo not active!"); break; }
          if (posGripper + stepSize >= gripperMax) { posGripper = gripperMax; Serial.print("[ MAX LIMIT ] "); } 
          else posGripper += stepSize;
          
          st.WritePosEx(7, posGripper, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(7); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Gripper pos: "); Serial.print(posGripper); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }
        case 'j': case 'J': {
          if (!servoActive[7]) { Serial.println("Gripper servo not active!"); break; }
          if (posGripper - stepSize <= gripperMin) { posGripper = gripperMin; Serial.print("[ MIN LIMIT ] "); } 
          else posGripper -= stepSize;
          
          st.WritePosEx(7, posGripper, moveSpeed, 50); 
          int maxI = 0; for (int i=0; i<20; i++) { int c=st.ReadCurrent(7); if(c>maxI) maxI=c; delay(10); }
          Serial.print("Gripper pos: "); Serial.print(posGripper); Serial.print(" | PEAK I: "); Serial.print(maxI); Serial.println("mA");
          break;
        }

        default:
          Serial.println("Unknown key!");
          break;
      }
    }
    else {
      Serial.println("Unknown command! Type a key, 'default', 'stat', 'pos' or 'reset'.");
    }
  }
}
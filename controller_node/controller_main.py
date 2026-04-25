import subprocess
import sys
import time

def main():
    print("[SYSTEM] Booting UGV02 Controller Node...")
    
    python_bin = sys.executable

    # ZMIANA: Używamy flagi "-m" i notacji z kropką (services.nazwa)
    # To mówi Pythonowi: "Uruchom to, ale pamiętaj, że główny folder to UGV02_Workspace"
    print("[SYSTEM] Starting Arm Service...")
    arm_process = subprocess.Popen([python_bin, "-m", "services.arm_service"])
    
    print("[SYSTEM] Starting Camera Service...")
    cam_process = subprocess.Popen([python_bin, "-m", "services.camera_service"])
    
    print("[SYSTEM] All systems nominal. Press Ctrl+C to shutdown.")
    
    try:
        while True:
            time.sleep(1)
            
            if arm_process.poll() is not None or cam_process.poll() is not None:
                print("[CRITICAL] A subsystem crashed! Initiating emergency shutdown...")
                break
                
    except KeyboardInterrupt:
        print("\n[SYSTEM] Manual shutdown requested (Ctrl+C).")
    
    finally:
        print("[SYSTEM] Terminating services...")
        arm_process.terminate()
        cam_process.terminate()
        
        arm_process.wait()
        cam_process.wait()
        print("[SYSTEM] Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
import subprocess
import sys
import time

def main():
    print("[SYSTEM] Booting UGV02 Controller Node...")
    python_bin = sys.executable

    # Open log file to capture all subsystems outputs (stdout and stderr)
    log_file = open("robot.log", "w", encoding="utf-8")
    log_file.write(f"[SYSTEM] Controller Node boot sequence started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.flush()

    print("[SYSTEM] Starting Arm Service...")
    arm_process = subprocess.Popen([python_bin, "-m", "services.arm_service"], stdout=log_file, stderr=log_file)
    
    print("[SYSTEM] Starting Camera Service...")
    cam_process = subprocess.Popen([python_bin, "-m", "services.camera_service"], stdout=log_file, stderr=log_file)
    
    print("[SYSTEM] Starting Chassis Service...")
    chassis_process = subprocess.Popen([python_bin, "-m", "services.chassis_service"], stdout=log_file, stderr=log_file)
    
    print("[SYSTEM] All systems nominal. Press Ctrl+C to shutdown.")
    
    try:
        while True:
            time.sleep(1)
            # Monitor background processes
            if arm_process.poll() is not None or cam_process.poll() is not None or chassis_process.poll() is not None:
                print("[CRITICAL] A subsystem crashed! Initiating emergency shutdown...")
                break
                
    except KeyboardInterrupt:
        print("\n[SYSTEM] Manual shutdown requested (Ctrl+C).")
    
    finally:
        print("[SYSTEM] Terminating services...")
        arm_process.terminate()
        cam_process.terminate()
        chassis_process.terminate()
        
        arm_process.wait()
        cam_process.wait()
        chassis_process.wait()
        log_file.close()
        print("[SYSTEM] Shutdown complete.")

if __name__ == "__main__":
    main()
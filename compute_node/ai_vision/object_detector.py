from ultralytics import YOLO

class YoloDetector:
    def __init__(self):
        print("[AI] Loading YOLOv8 Nano model...")
        self.model = YOLO('yolov8n.pt') 
        print("[AI] YOLOv8 ready!")

    def process_frame(self, frame):
        results = self.model(frame, verbose=False)
        
        annotated_frame = results[0].plot()
        
        return annotated_frame, results[0]
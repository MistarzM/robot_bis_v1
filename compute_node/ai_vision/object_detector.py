from ultralytics import YOLO

class YoloDetector:
    def __init__(self):
        print("[AI] Loading YOLOv8 Nano model...")
        self.model = YOLO('yolov8n.pt') 
        print("[AI] YOLOv8 ready!")

    def process_frame(self, frame):
        # verbose=False ukrywa spam w konsoli dla każdej klatki
        results = self.model(frame, verbose=False)
        
        # Pobieramy klatkę z narysowanymi ramkami i etykietami (Bounding Boxes)
        annotated_frame = results[0].plot()
        
        # Zwracamy pokolorowaną klatkę oraz surowe dane, 
        # gdybyś chciał później kazać robotowi śledzić obiekt!
        return annotated_frame, results[0]
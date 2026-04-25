import cv2
import zmq
import time
from core import config  

def start_camera_stream():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.setsockopt(zmq.LINGER, 0)
    
    socket.bind(f"tcp://0.0.0.0:{config.VIDEO_PORT}")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print(f"[VIDEO] Camera streamer started on port {config.VIDEO_PORT}.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            socket.send(buffer.tobytes())
            time.sleep(0.03)
            
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        socket.close()
        context.term()

if __name__ == "__main__":
    start_camera_stream()
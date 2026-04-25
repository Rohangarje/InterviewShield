import cv2
import numpy as np
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  ultralytics not installed. Install with: pip install ultralytics")

class YOLODetector:
    def __init__(self):
        if not YOLO_AVAILABLE:
            print("⚠️  YOLODetector requires ultralytics. Phone detection disabled.")
            self.model = None
            return
        
        # Load nano model for speed (first load caches automatically)
        self.model = YOLO('yolov8n.pt')
        # Use CPU for web deployment
        self.model.to('cpu')
        # COCO class ID for cell phone
        self.phone_class_id = 67
    
    def detect_phone(self, frame):
        """
        Detect cell phones in frame.
        Returns dict with phone_detected, confidence, bbox
        """
        if not YOLO_AVAILABLE or self.model is None:
            return {
                'phone_detected': False,
                'confidence': 0.0,
                'bbox': None
            }
        
        # Resize for speed (320x320)
        input_frame = cv2.resize(frame, (320, 320))
        
        # Run inference
        results = self.model(input_frame, verbose=False, conf=0.5)
        
        phone_detected = False
        max_conf = 0
        bbox = None
        
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id == self.phone_class_id and conf > max_conf:
                        max_conf = conf
                        phone_detected = True
                        # Scale bbox back to original size
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        scale_x = frame.shape[1] / 320
                        scale_y = frame.shape[0] / 320
                        bbox = (int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y))
        
        return {
            'phone_detected': phone_detected,
            'confidence': max_conf,
            'bbox': bbox
        }

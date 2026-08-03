import cv2
import numpy as np
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

class ObjectDetector:
    def __init__(self, model_name='yolov8n.pt'):
        self.model = None
        if YOLO:
            try:
                self.model = YOLO(model_name)
                # Filter indices for COCO: car(2), motorcycle(3), bus(5), truck(7), person(0)
                self.target_classes = [0, 2, 3, 5, 7]
            except Exception as e:
                print(f"Error loading YOLO: {e}")
        
    def detect(self, image):
        if not self.model:
            return []
        
        results = self.model(image, verbose=False, conf=0.25)
        detections = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id in self.target_classes:
                    conf = float(box.conf[0])
                    xyxy = box.xyxy[0].cpu().numpy()
                    detections.append({
                        'box': xyxy,
                        'conf': conf,
                        'class': cls_id,
                        'label': self.model.names[cls_id]
                    })
        return detections

def draw_detections(image, detections):
    for det in detections:
        x1, y1, x2, y2 = det['box'].astype(int)
        label = f"{det['label']} {det['conf']:.2f}"
        
        # Color based on class - Green for cars, Red for people etc.
        color = (0, 255, 0)
        if det['class'] == 0: color = (0, 0, 255) # Person
        
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return image

def project_detections_to_bev(detections, homography, bev_size=(1000, 1000)):
    """
    Project detections from image floor points to BEV.
    Assumes objects are on the ground plane.
    """
    bev_points = []
    for det in detections:
        x1, y1, x2, y2 = det['box']
        # Use center-bottom of the box as the ground contact point
        ground_point = np.array([[(x1 + x2) / 2, y2]], dtype=np.float32).reshape(-1, 1, 2)
        
        # Transform point
        bev_point = cv2.perspectiveTransform(ground_point, homography)
        bx, by = bev_point[0, 0]
        
        if 0 <= bx < bev_size[0] and 0 <= by < bev_size[1]:
            bev_points.append({
                'pos': (int(bx), int(by)),
                'label': det['label'],
                'color': (0, 255, 0) if det['class'] != 0 else (0, 0, 255)
            })
    return bev_points

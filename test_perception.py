import cv2
import numpy as np
from modules.perception import ObjectDetector, draw_detections, project_detections_to_bev
import json

def test_inference():
    # Load a sample image
    img_path = 'data/front_sample.jpg'
    img = cv2.imread(img_path)
    if img is None:
        print("Sample image not found, using blank.")
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
    detector = ObjectDetector()
    detections = detector.detect(img)
    print(f"Detected {len(detections)} objects.")
    
    out = draw_detections(img.copy(), detections)
    cv2.imwrite('output/test_detection.jpg', out)
    print("Test detection saved to output/test_detection.jpg")

if __name__ == "__main__":
    test_inference()

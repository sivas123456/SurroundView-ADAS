import cv2
import json
import numpy as np
from modules.geometry import BEVTransformer, blend_bev, create_dashboard

def test_stitching():
    with open('data/calibration.json', 'r') as f:
        calib = json.load(f)
        
    transformer = BEVTransformer(calib)
    
    names = ['front', 'front_left', 'front_right', 'rear', 'rear_left', 'rear_right']
    projected = {}
    projected_masks = {}
    
    for name in names:
        img = cv2.imread(f'data/{name}_sample.jpg')
        if img is not None:
            warped, mask = transformer.process_frame(name, img)
            projected[name] = warped
            projected_masks[name] = mask
            cv2.imwrite(f'output/{name}_projected.jpg', warped)
            
    final_bev = blend_bev(projected, projected_masks, transformer.ego_car)
    
    # Use front sample as focal camera
    front_img = cv2.imread('data/front_sample.jpg')
    dashboard = create_dashboard(final_bev, front_img, info_text="WORLD-CLASS TEST MODE")
    
    cv2.imwrite('output/final_dashboard_sample.jpg', dashboard)
    print("World-Class Dashboard generated in output/final_dashboard_sample.jpg")

if __name__ == "__main__":
    test_stitching()

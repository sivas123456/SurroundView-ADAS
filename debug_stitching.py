import cv2
import numpy as np
import json
from modules.geometry import BEVTransformer

def debug_mappings():
    with open('data/calibration.json', 'r') as f:
        calib = json.load(f)
    
    transformer = BEVTransformer(calib)
    
    for name in calib.keys():
        sample_path = f'data/{name}_sample.jpg'
        img = cv2.imread(sample_path)
        if img is None:
            print(f"Skipping {name}, sample not found.")
            continue
            
        # 1. Undistort
        map1, map2 = transformer.undistort_maps[name]
        undistorted = cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR)
        
        # 2. Draw src points on undistorted
        # Note: self.homographies is computed from src to dst.
        # But wait, in _init_maps, I define src as points on the undistorted image?
        # Yes: undistorted = cv2.remap(image, map1, map2...)
        # warped = cv2.warpPerspective(undistorted, self.homographies[name]...)
        
        # Unfortunately I don't store src points in transformer.
        # I'll just hardcode them here to see where they land.
        
        src_points = {
            'front': [[200, 600], [1720, 600], [0, 1080], [1920, 1080]],
            'rear': [[200, 600], [1720, 600], [0, 1080], [1920, 1080]],
            'front_left': [[600, 600], [1800, 600], [0, 1080], [1920, 1080]],
            'front_right': [[120, 600], [1320, 600], [0, 1080], [1920, 1080]],
            'rear_left': [[600, 600], [1800, 600], [0, 1080], [1920, 1080]],
            'rear_right': [[120, 600], [1320, 600], [0, 1080], [1920, 1080]]
        }
        
        pts = np.array(src_points.get(name, []), dtype=np.int32)
        for pt in pts:
            cv2.circle(undistorted, tuple(pt), 10, (0, 0, 255), -1)
            
        cv2.imwrite(f'output/debug_src_{name}.jpg', undistorted)
        
        # 3. Check Warped
        warped, mask = transformer.process_frame(name, img)
        if warped is not None:
            cv2.imwrite(f'output/debug_warp_{name}.jpg', warped)
            cv2.imwrite(f'output/debug_mask_{name}.jpg', mask)

if __name__ == "__main__":
    import os
    if not os.path.exists('output'): os.makedirs('output')
    debug_mappings()

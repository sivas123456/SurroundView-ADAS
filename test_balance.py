import cv2
import numpy as np
import json

def test_undistort_balance():
    with open('data/calibration.json', 'r') as f:
        calib = json.load(f)
    
    name = 'front_left'
    data = calib[name]
    K = np.array(data['K']).reshape(3, 3)
    D = np.array(data['D'])
    W, H = data['width'], data['height']
    
    img = cv2.imread(f'data/{name}_sample.jpg')
    if img is None: return
    
    for b in [0.0, 0.5, 1.0]:
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(K, D, (W, H), np.eye(3), balance=b)
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), new_K, (W, H), cv2.CV_16SC2)
        undistorted = cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR)
        cv2.imwrite(f'output/test_undistort_{name}_bal_{b}.jpg', undistorted)
        print(f"Saved balance {b}, mean pixel: {np.mean(undistorted)}")

if __name__ == "__main__":
    test_undistort_balance()

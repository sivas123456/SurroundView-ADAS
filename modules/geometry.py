import cv2
import numpy as np
import os

class BEVTransformer:
    def __init__(self, calibration_data):
        self.calib = calibration_data
        self.undistort_maps = {}
        self.homographies = {}
        self.bev_size = (1200, 1200)  # Higher resolution for premium quality
        self.center = (600, 600)
        self.ego_car = self._create_car_vector()
        self.sector_masks = {}
        self._init_maps()

    def _create_car_vector(self):
        """Create a photorealistic car overlay from top view"""
        car = np.zeros((180, 90, 4), dtype=np.uint8)
        
        # Main body - sleek dark gray
        cv2.rectangle(car, (8, 8), (82, 172), (35, 35, 40, 255), -1)
        
        # Windshield (front) - lighter blue tint
        cv2.rectangle(car, (15, 8), (75, 35), (80, 90, 100, 200), -1)
        
        # Rear windshield
        cv2.rectangle(car, (15, 145), (75, 172), (60, 70, 80, 200), -1)
        
        # Side mirrors
        cv2.rectangle(car, (2, 45), (8, 60), (40, 40, 45, 255), -1)
        cv2.rectangle(car, (82, 45), (88, 60), (40, 40, 45, 255), -1)
        
        # Headlights - bright white/yellow
        cv2.ellipse(car, (22, 12), (8, 6), 0, 0, 360, (240, 255, 255, 255), -1)
        cv2.ellipse(car, (68, 12), (8, 6), 0, 0, 360, (240, 255, 255, 255), -1)
        
        # Taillights - red
        cv2.ellipse(car, (22, 168), (8, 5), 0, 0, 360, (30, 30, 200, 255), -1)
        cv2.ellipse(car, (68, 168), (8, 5), 0, 0, 360, (30, 30, 200, 255), -1)
        
        # Roof sensor/camera
        cv2.circle(car, (45, 90), 6, (0, 200, 255, 220), -1)
        cv2.circle(car, (45, 90), 8, (0, 150, 200, 180), 1)
        
        # Body outline - subtle highlight
        cv2.rectangle(car, (8, 8), (82, 172), (120, 120, 130, 255), 2)
        
        return car

    def _init_maps(self):
        """Initialize undistortion and homography maps for realistic top-down view"""
        
        # Camera physical layout (degrees from front)
        cam_angles = {
            'front': 0,
            'front_right': 60,
            'rear_right': 120,
            'rear': 180,
            'rear_left': 240,
            'front_left': 300
        }

        for name, data in self.calib.items():
            K = np.array(data['K']).reshape(3, 3)
            D = np.array(data['D'])
            W, H = data['width'], data['height']
            
            # Aggressive fisheye correction for flat perspective
            new_K = K.copy()
            new_K[0,0] *= 0.4  # More zoom for realistic ground view
            new_K[1,1] *= 0.4
            
            if data.get('dist_model') == 'equidistant':
                map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                    K, D, np.eye(3), new_K, (W, H), cv2.CV_16SC2
                )
            else:
                map1, map2 = cv2.initUndistortRectifyMap(
                    K, D, np.eye(3), new_K, (W, H), cv2.CV_16SC2
                )
            self.undistort_maps[name] = (map1, map2)
            
            # REALISTIC GROUND PLANE PROJECTION
            # Source: Lower portion of camera view (ground area)
            # Using more of the bottom for better ground coverage
            # Adjusted top crop to 0.53 to reduce horizon stretching while keeping windows
            src = np.float32([
                [W * 0.15, H * 0.53],  # Top-left
                [W * 0.85, H * 0.53],  # Top-right
                [W * 0.05, H * 0.95],  # Bottom-left
                [W * 0.95, H * 0.95]   # Bottom-right
            ])
            
            # Destination: Radial wedge in BEV (60° per camera)
            angle = cam_angles.get(name, 0)
            
            # Each camera covers 60° wedge with 10° overlap
            angle_start = angle - 35
            angle_end = angle + 35
            
            # Distance from car center (pixels)
            r_near = 100  # Close to car
            r_far = 580   # Far from car (realistic viewing distance)
            
            # Convert to radians (subtract 90 to align with image coordinates)
            a1 = np.radians(angle_start - 90)
            a2 = np.radians(angle_end - 90)
            
            # Calculate destination quadrilateral
            dst = np.float32([
                [600 + r_far * np.cos(a1), 600 + r_far * np.sin(a1)],   # Far-left
                [600 + r_far * np.cos(a2), 600 + r_far * np.sin(a2)],   # Far-right
                [600 + r_near * np.cos(a1), 600 + r_near * np.sin(a1)], # Near-left
                [600 + r_near * np.cos(a2), 600 + r_near * np.sin(a2)]  # Near-right
            ])
            
            self.homographies[name] = cv2.getPerspectiveTransform(src, dst)

        # Create seamless sector masks (60° wedges with soft edges)
        angle_bounds = [-30, 30, 90, 150, 210, 270, 330]
        cam_order = ['front', 'front_right', 'rear_right', 'rear', 'rear_left', 'front_left']
        
        for i, name in enumerate(cam_order):
            mask = np.zeros((1200, 1200), dtype=np.uint8)
            
            # Create wedge polygon
            poly_points = [[600, 600]]  # Center point
            for angle_deg in np.linspace(angle_bounds[i], angle_bounds[i+1], 50):
                angle_rad = np.radians(angle_deg - 90)
                x = int(600 + 1800 * np.cos(angle_rad))
                y = int(600 + 1800 * np.sin(angle_rad))
                poly_points.append([x, y])
            
            cv2.fillPoly(mask, [np.array(poly_points, dtype=np.int32)], 255)
            self.sector_masks[name] = mask

    def process_frame(self, name, image):
        """Process a single camera frame into BEV space"""
        if name not in self.undistort_maps:
            return None
            
        map1, map2 = self.undistort_maps[name]
        undistorted = cv2.remap(image, map1, map2, interpolation=cv2.INTER_LINEAR)
        
        # Apply homography to get top-down view
        warped = cv2.warpPerspective(
            undistorted, 
            self.homographies[name], 
            self.bev_size,
            flags=cv2.INTER_LINEAR
        )
        
        mask = self.sector_masks.get(name, np.zeros((1200, 1200), dtype=np.uint8))
        return warped, mask


def blend_bev(frames_dict, masks_dict, car_overlay=None):
    """Blend all camera views into a seamless photorealistic BEV"""
    canvas = np.zeros((1200, 1200, 3), dtype=np.float32)
    weight_canvas = np.zeros((1200, 1200), dtype=np.float32)
    
    # Blend all camera sectors with advanced feathering
    for name in masks_dict.keys():
        img = frames_dict.get(name)
        mask = masks_dict.get(name)
        if img is None or mask is None:
            continue
        
        # Normalize mask
        fmask = mask.astype(np.float32) / 255.0
        
        # Multi-stage blur for ultra-smooth blending
        fmask_blur = cv2.GaussianBlur(fmask, (121, 121), 0)
        
        # Accumulate weighted pixels
        canvas += img.astype(np.float32) * fmask_blur[:, :, np.newaxis]
        weight_canvas += fmask_blur
    
    # Normalize by total weight
    weight_canvas[weight_canvas < 0.001] = 1.0
    final_bev = (canvas / weight_canvas[:, :, np.newaxis]).astype(np.uint8)
    
    # Color correction for realistic outdoor look
    final_bev = cv2.convertScaleAbs(final_bev, alpha=1.1, beta=5)
    
    # Subtle sharpening for clarity
    kernel_sharpen = np.array([[-0.5, -0.5, -0.5],
                               [-0.5,  5.0, -0.5],
                               [-0.5, -0.5, -0.5]]) / 1.0
    final_bev = cv2.filter2D(final_bev, -1, kernel_sharpen)
    
    # Overlay the ego vehicle
    if car_overlay is not None:
        h, w = car_overlay.shape[:2]
        y1, y2 = 600 - h//2, 600 + h//2
        x1, x2 = 600 - w//2, 600 + w//2
        
        alpha = car_overlay[:, :, 3] / 255.0
        for c in range(3):
            final_bev[y1:y2, x1:x2, c] = (
                car_overlay[:, :, c] * alpha + 
                final_bev[y1:y2, x1:x2, c] * (1 - alpha)
            )
    
    # Premium radial vignette (Gradual falloff to hide stretching)
    # Replaces hard circle with smooth attenuation from r=350 to r=600
    Y, X = np.ogrid[:1200, :1200]
    radius = np.sqrt((X - 600)**2 + (Y - 600)**2)
    mask_soft = np.clip(1.0 - (radius - 350) / 250.0, 0, 1).astype(np.float32)
    final_bev = (final_bev * mask_soft[:, :, np.newaxis]).astype(np.uint8)
    
    # Distance reference rings (subtle, professional)
    for r, thickness in [(150, 1), (300, 1), (450, 2)]:
        cv2.circle(final_bev, (600, 600), r, (80, 85, 90), thickness)
    
    # Add distance labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(final_bev, "3m", (600-15, 600-150), font, 0.4, (100, 105, 110), 1)
    cv2.putText(final_bev, "6m", (600-15, 600-300), font, 0.4, (100, 105, 110), 1)
    cv2.putText(final_bev, "9m", (600-15, 600-450), font, 0.4, (100, 105, 110), 1)
    
    return final_bev


def create_dashboard(bev_img, focal_frame, info_text="", proximity=None):
    """Deprecated - UI now handled by index.html"""
    return bev_img

import cv2
import json
import numpy as np
import time
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from modules.geometry import BEVTransformer, blend_bev, create_dashboard
from modules.perception import ObjectDetector, draw_detections, project_detections_to_bev

def run_project(bag_path, save_video=False):
    with open('data/calibration.json', 'r') as f:
        calib = json.load(f)
    
    transformer = BEVTransformer(calib)
    detector = ObjectDetector()
    typestore = get_typestore(Stores.LATEST)
    
    cam_topics = {
        '/camera_f/image_raw': 'front',
        '/camera_fr/image_raw': 'front_right',
        '/camera_fl/image_raw': 'front_left',
        '/camera_r/image_raw': 'rear',
        '/camera_rr/image_raw': 'rear_right',
        '/camera_rl/image_raw': 'rear_left'
    }
    
    print(f"Starting BEV Pipeline for {bag_path}...")
    current_frames = {k: None for k in cam_topics.values()}
    current_masks = {k: None for k in cam_topics.values()}
    current_raw = {k: None for k in cam_topics.values()}
    
    writer = None
    if save_video:
        out_name = Path(bag_path).stem + "_surround_view.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        # Dashboard resolution is 1920x1080
        writer = cv2.VideoWriter(f'output/{out_name}', fourcc, 15.0, (1920, 1080))

    with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
        connections = [c for c in reader.connections if c.topic in cam_topics.keys()]
        
        last_sync_time = 0
        sync_threshold = 100_000_000 # 0.1s update rate
        
        frame_count = 0
        start_time = time.time()
        
        for connection, timestamp, rawdata in reader.messages(connections=connections):
            topic = connection.topic
            name = cam_topics[topic]
            
            msg = reader.deserialize(rawdata, connection.msgtype)
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
            if msg.encoding == 'rgb8':
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            current_raw[name] = img
            res = transformer.process_frame(name, img)
            if res:
                current_frames[name], current_masks[name] = res
            
            if timestamp - last_sync_time > sync_threshold:
                # 1. Generate BEV
                bev_output = blend_bev(current_frames, current_masks, transformer.ego_car)
                
                # 2. Get Focal Frame (Front camera - Undistorted)
                focal_raw = current_raw['front']
                detections = []
                if focal_raw is not None:
                    map1, map2 = transformer.undistort_maps['front']
                    focal_frame = cv2.remap(focal_raw, map1, map2, interpolation=cv2.INTER_LINEAR)
                    
                    # 2b. Run Object Detection on Front Camera
                    detections = detector.detect(focal_frame)
                    focal_frame = draw_detections(focal_frame, detections)
                else:
                    focal_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
                
                # 3. Project Detections to BEV
                bev_points = project_detections_to_bev(detections, transformer.homographies['front'])
                min_dist = None
                for p in bev_points:
                    cv2.circle(bev_output, p['pos'], 12, p['color'], -1)
                    cv2.circle(bev_output, p['pos'], 15, (255, 255, 255), 2) # Highlight
                    cv2.putText(bev_output, p['label'], (p['pos'][0]+20, p['pos'][1]), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # Proximity Calculation
                    dist_px = np.sqrt((p['pos'][0]-500)**2 + (p['pos'][1]-500)**2)
                    dist_m = dist_px * 0.025 # Scale factor
                    if min_dist is None or dist_m < min_dist:
                        min_dist = dist_m

                # 4. Create Dashboard
                info_msg = f"BAG: {Path(bag_path).name}"
                if detections:
                    info_msg += f" | OBJECTS: {len(detections)}"
                dash_output = create_dashboard(bev_output, focal_frame, info_text=info_msg, proximity=min_dist)
                
                # FPS Overlay on Dash
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                cv2.putText(dash_output, f"REFRESH: {fps:.1f} Hz", (1100, 800), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                if writer:
                    writer.write(dash_output)
                
                # Show at a smaller scale for screen fitting if needed, but 1080p is preferred
                cv2.imshow("Surround View System", cv2.resize(dash_output, (1280, 720)))
                
                last_sync_time = timestamp
                key = cv2.waitKey(1)
                if key == ord('q'):
                    break
                
                frame_count += 1
                if frame_count % 10 == 0:
                    print(f"Streaming Frame {frame_count}...", end='\r')

    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print("\nProcessing complete.")

if __name__ == "__main__":
    # Choose which dataset to run
    bag1 = 'rosbag2_2025_12_01-16_57_24_0-001.db3'
    bag2 = 'rosbag2_2025_12_01-16_59_00_0-001.db3'
    
    # Run the larger one by default for "Next" step
    run_project(bag2, save_video=True)

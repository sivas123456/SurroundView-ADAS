import os
import cv2
import numpy as np
import json
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

def init_project():
    folders = ['data', 'output', 'modules']
    for f in folders:
        os.makedirs(f, exist_ok=True)
    print("Project folders initialized.")

def extract_metadata(bag_path):
    typestore = get_typestore(Stores.LATEST)
    
    # Camera topics mapping
    cam_topics = {
        'front': '/camera_f/image_raw',
        'front_right': '/camera_fr/image_raw',
        'front_left': '/camera_fl/image_raw',
        'rear': '/camera_r/image_raw',
        'rear_right': '/camera_rr/image_raw',
        'rear_left': '/camera_rl/image_raw'
    }
    
    info_topics = {k: v.replace('image_raw', 'camera_info') for k, v in cam_topics.items()}
    
    calibration = {}
    samples = {}
    
    print(f"Opening bag: {bag_path}")
    with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
        # Extract Calibration
        connections = [c for c in reader.connections if c.topic in info_topics.values()]
        for connection, timestamp, rawdata in reader.messages(connections=connections):
            topic = connection.topic
            key = [k for k, v in info_topics.items() if v == topic][0]
            if key not in calibration:
                msg = reader.deserialize(rawdata, connection.msgtype)
                calibration[key] = {
                    'K': [float(x) for x in msg.k],
                    'D': [float(x) for x in msg.d],
                    'width': int(msg.width),
                    'height': int(msg.height),
                    'dist_model': str(msg.distortion_model)
                }
            if len(calibration) == len(info_topics):
                break
        
        # Extract one sample image for each
        img_connections = [c for c in reader.connections if c.topic in cam_topics.values()]
        for connection, timestamp, rawdata in reader.messages(connections=img_connections):
            topic = connection.topic
            key = [k for k, v in cam_topics.items() if v == topic][0]
            if key not in samples:
                msg = reader.deserialize(rawdata, connection.msgtype)
                img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
                if msg.encoding == 'rgb8':
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                samples[key] = img
                cv2.imwrite(f"data/{key}_sample.jpg", img)
                print(f"Saved sample for {key}")
            if len(samples) == len(cam_topics):
                break

    with open('data/calibration.json', 'w') as f:
        json.dump(calibration, f, indent=4)
    print("Calibration saved to data/calibration.json")

if __name__ == "__main__":
    init_project()
    extract_metadata('rosbag2_2025_12_01-16_57_24_0-001.db3')

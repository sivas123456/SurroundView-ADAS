from flask import Flask, render_template, Response, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import json
import time
import threading
import os
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from modules.geometry import BEVTransformer, blend_bev
from modules.perception import ObjectDetector, draw_detections, project_detections_to_bev

app = Flask(__name__, template_folder='ui')
CORS(app)

class BagStreamer:
    def __init__(self, bag_path):
        self.bag_path = bag_path
        with open('data/calibration.json', 'r') as f:
            calib = json.load(f)
        self.transformer = BEVTransformer(calib)
        self.detector = ObjectDetector()
        self.typestore = get_typestore(Stores.LATEST)
        
        self.cam_topics = {
            '/camera_f/image_raw': 'front',
            '/camera_fr/image_raw': 'front_right',
            '/camera_fl/image_raw': 'front_left',
            '/camera_r/image_raw': 'rear',
            '/camera_rr/image_raw': 'rear_right',
            '/camera_rl/image_raw': 'rear_left'
        }
        
        self.current_raw = {}
        self.frames = {}
        self.masks = {}
        
        print("Pre-loading sample images...")
        for name in self.cam_topics.values():
            sample_path = f'data/{name}_sample.jpg'
            if os.path.exists(sample_path):
                img = cv2.imread(sample_path)
                if img is not None:
                    print(f"  Loaded {name} sample")
                    self.current_raw[name] = img
                    res = self.transformer.process_frame(name, img)
                    if res:
                        self.frames[name], self.masks[name] = res
                else:
                    print(f"  FAILED to decode {name} sample")
                    self.current_raw[name] = None
            else:
                print(f"  MISSING sample: {sample_path}")
                self.current_raw[name] = None
        
        self.current_bev = blend_bev(self.frames, self.masks, self.transformer.ego_car)
        self.is_running = False
        self.lock = threading.Lock()
        
    def stream_loop(self):
        print(f"Starting stream loop for {self.bag_path}")
        while True:
            try:
                with AnyReader([Path(self.bag_path)], default_typestore=self.typestore) as reader:
                    connections = [c for c in reader.connections if c.topic in self.cam_topics.keys()]
                    print(f"Found {len(connections)} useful topics in bag")
                    
                    last_sync = 0
                    sync_thresh = 50_000_000 # 50ms sync
                    
                    for connection, timestamp, rawdata in reader.messages(connections=connections):
                        if not self.is_running: break
                        
                        topic_name = connection.topic
                        name = self.cam_topics[topic_name]
                        
                        try:
                            msg = reader.deserialize(rawdata, connection.msgtype)
                            img_raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
                            if msg.encoding == 'rgb8':
                                img = cv2.cvtColor(img_raw, cv2.COLOR_RGB2BGR)
                            else:
                                img = img_raw
                                
                            # Heavy processing
                            res = self.transformer.process_frame(name, img)
                            
                            with self.lock:
                                if name != 'front':
                                    self.current_raw[name] = img
                                else:
                                    # For front, we store a temporary raw frame for processing, 
                                    # but don't show it yet to avoid flickering.
                                    self._temp_front_raw = img
                                if res:
                                    self.frames[name], self.masks[name] = res
                            
                            if timestamp - last_sync > sync_thresh:
                                with self.lock:
                                    # Update BEV
                                    self.current_bev = blend_bev(self.frames, self.masks, self.transformer.ego_car)
                                    
                                    # Objects on Front
                                    f_raw = getattr(self, '_temp_front_raw', None)
                                    if f_raw is not None:
                                        map1, map2 = self.transformer.undistort_maps['front']
                                        f_undist = cv2.remap(f_raw, map1, map2, cv2.INTER_LINEAR)
                                        dets = self.detector.detect(f_undist)
                                        
                                        # Draw detections on BEV
                                        bev_pts = project_detections_to_bev(dets, self.transformer.homographies['front'])
                                        for p in bev_pts:
                                            cv2.circle(self.current_bev, p['pos'], 12, p['color'], -1)
                                            cv2.circle(self.current_bev, p['pos'], 15, (255, 255, 255), 2)
                                        
                                        # Overlay on thumbnail
                                        self.current_raw['front'] = draw_detections(f_undist, dets)

                                last_sync = timestamp
                                time.sleep(0.001)
                        except Exception as e:
                            # print(f"Msg error on {name}: {e}")
                            pass
                            
            except Exception as e:
                print(f"Bag Reader crashed: {e}")
                time.sleep(2)

streamer = BagStreamer('rosbag2_2025_12_01-16_59_00_0-001.db3')
streamer.is_running = True
threading.Thread(target=streamer.stream_loop, daemon=True).start()

def generate_mjpeg(cam_name):
    while True:
        with streamer.lock:
            if cam_name == 'bev':
                img = streamer.current_bev
            else:
                img = streamer.current_raw.get(cam_name)
        
        if img is not None:
            if cam_name != 'bev':
                img = cv2.resize(img, (400, 225))
            
            ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        time.sleep(0.04) # 25 FPS throttle for web

@app.route('/snapshot/<cam_name>')
def snapshot(cam_name):
    # Serve a single JPEG frame
    with streamer.lock:
        if cam_name == 'bev':
            img = streamer.current_bev
        else:
            img = streamer.current_raw.get(cam_name)
    
    if img is None:
        return "", 404
    
    if cam_name != 'bev':
        img = cv2.resize(img, (400, 225))
    
    ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video/<cam_name>')
def video_feed(cam_name):
    return Response(generate_mjpeg(cam_name),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

import webbrowser

@app.route('/status')
def get_status():
    return jsonify({"status": "CONNECTED", "bag": Path(streamer.bag_path).name})

if __name__ == '__main__':
    print("Opening browser...")
    webbrowser.open('http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, threaded=True)

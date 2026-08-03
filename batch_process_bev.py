"""
Advanced Batch BEV Processor
Processes entire ROS bag dataset to generate photorealistic Bird's Eye View outputs
"""

import cv2
import numpy as np
import json
import os
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from modules.geometry import BEVTransformer, blend_bev
from modules.perception import ObjectDetector, draw_detections, project_detections_to_bev
from tqdm import tqdm
import time

class BatchBEVProcessor:
    def __init__(self, output_dir='output_bev'):
        """Initialize the batch processor"""
        print("Initializing BEV Processor...")
        
        # Load calibration
        with open('data/calibration.json', 'r') as f:
            self.calib = json.load(f)
        
        self.transformer = BEVTransformer(self.calib)
        self.detector = ObjectDetector()
        self.typestore = get_typestore(Stores.LATEST)
        
        # Output configuration
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Video writers
        self.video_writers = {}
        self.frame_count = 0
        
        # Camera topics
        self.cam_topics = {
            '/camera_f/image_raw': 'front',
            '/camera_fr/image_raw': 'front_right',
            '/camera_fl/image_raw': 'front_left',
            '/camera_r/image_raw': 'rear',
            '/camera_rr/image_raw': 'rear_right',
            '/camera_rl/image_raw': 'rear_left'
        }
        
        print(f"Output directory: {self.output_dir.absolute()}")
        
    def init_video_writer(self, name, width, height, fps=30):
        """Initialize video writer for output"""
        output_path = self.output_dir / f"{name}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        return writer
    
    def process_bag(self, bag_path, max_frames=None, sample_rate=1):
        """
        Process a single ROS bag file
        
        Args:
            bag_path: Path to the ROS bag file
            max_frames: Maximum number of frames to process (None = all)
            sample_rate: Process every Nth frame (1 = all frames, 2 = every other frame)
        """
        bag_name = Path(bag_path).stem
        print(f"Processing: {bag_name}")
        print(f"   Sample Rate: 1/{sample_rate} frames")
        if max_frames:
            print(f"   Max Frames: {max_frames}")
        
        # Initialize video writer for this bag
        bev_writer = self.init_video_writer(f"{bag_name}_bev", 1200, 1200, fps=30//sample_rate)
        front_writer = self.init_video_writer(f"{bag_name}_front", 1920, 1080, fps=30//sample_rate)
        
        # Frame buffers
        current_frames = {}
        current_masks = {}
        current_raw = {}
        
        frame_idx = 0
        processed_count = 0
        last_sync = 0
        sync_threshold = 50_000_000  # 50ms
        
        try:
            with AnyReader([Path(bag_path)], default_typestore=self.typestore) as reader:
                connections = [c for c in reader.connections if c.topic in self.cam_topics.keys()]
                total_messages = sum(1 for _ in reader.messages(connections=connections))
                
                print(f"   Total messages: {total_messages}")
                
                # Reset reader
                reader = AnyReader([Path(bag_path)], default_typestore=self.typestore)
                reader.__enter__()
                connections = [c for c in reader.connections if c.topic in self.cam_topics.keys()]
                
                with tqdm(total=total_messages, desc="Processing frames", unit="msg") as pbar:
                    for connection, timestamp, rawdata in reader.messages(connections=connections):
                        topic_name = connection.topic
                        cam_name = self.cam_topics[topic_name]
                        
                        try:
                            # Deserialize message
                            msg = reader.deserialize(rawdata, connection.msgtype)
                            img_raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                                msg.height, msg.width, -1
                            )
                            
                            if msg.encoding == 'rgb8':
                                img = cv2.cvtColor(img_raw, cv2.COLOR_RGB2BGR)
                            else:
                                img = img_raw
                            
                            # Process frame
                            result = self.transformer.process_frame(cam_name, img)
                            if result:
                                current_frames[cam_name], current_masks[cam_name] = result
                            current_raw[cam_name] = img
                            
                            # Synchronization point - generate BEV when all cameras updated
                            if timestamp - last_sync > sync_threshold:
                                if frame_idx % sample_rate == 0:
                                    # Check if we have all 6 cameras
                                    if len(current_frames) == 6:
                                        # Generate BEV
                                        bev = blend_bev(
                                            current_frames, 
                                            current_masks, 
                                            self.transformer.ego_car
                                        )
                                        
                                        # Process front camera with detection
                                        front_img = current_raw.get('front')
                                        if front_img is not None:
                                            map1, map2 = self.transformer.undistort_maps['front']
                                            front_undist = cv2.remap(
                                                front_img, map1, map2, cv2.INTER_LINEAR
                                            )
                                            
                                            # Object detection
                                            detections = self.detector.detect(front_undist)
                                            front_with_det = draw_detections(front_undist, detections)
                                            
                                            # Project to BEV
                                            bev_pts = project_detections_to_bev(
                                                detections, 
                                                self.transformer.homographies['front']
                                            )
                                            for p in bev_pts:
                                                cv2.circle(bev, p['pos'], 12, p['color'], -1)
                                                cv2.circle(bev, p['pos'], 15, (255, 255, 255), 2)
                                                cv2.putText(
                                                    bev, p['label'], 
                                                    (p['pos'][0]+20, p['pos'][1]), 
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                                                    (255, 255, 255), 2
                                                )
                                            
                                            # Write frames
                                            bev_writer.write(bev)
                                            front_writer.write(front_with_det)
                                            
                                            processed_count += 1
                                            
                                            # Save sample images every 100 frames
                                            if processed_count % 100 == 0:
                                                cv2.imwrite(
                                                    str(self.output_dir / f"{bag_name}_bev_{processed_count:06d}.jpg"),
                                                    bev
                                                )
                                        
                                        # Check max frames limit
                                        if max_frames and processed_count >= max_frames:
                                            print(f"\nReached max frames limit: {max_frames}")
                                            break
                                
                                last_sync = timestamp
                                frame_idx += 1
                            
                            pbar.update(1)
                            
                        except Exception as e:
                            # Skip corrupted frames
                            pbar.update(1)
                            continue
                
                reader.__exit__(None, None, None)
                
        except Exception as e:
            print(f"Error processing bag: {e}")
        finally:
            bev_writer.release()
            front_writer.release()
            
        print(f"Processed {processed_count} frames from {bag_name}")
        return processed_count
    
    def process_all_bags(self, bag_dir='.', max_frames_per_bag=None, sample_rate=1):
        """
        Process all ROS bags in a directory
        
        Args:
            bag_dir: Directory containing ROS bags
            max_frames_per_bag: Max frames per bag (None = all)
            sample_rate: Process every Nth frame
        """
        bag_files = list(Path(bag_dir).glob('*.db3'))
        
        if not bag_files:
            print("No .db3 files found!")
            return
        
        print(f"\nFound {len(bag_files)} ROS bag files")
        print(f"Total size: {sum(f.stat().st_size for f in bag_files) / 1024**3:.2f} GB")
        
        total_processed = 0
        start_time = time.time()
        
        for bag_file in bag_files:
            count = self.process_bag(str(bag_file), max_frames_per_bag, sample_rate)
            total_processed += count
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"BATCH PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"   Total Frames Processed: {total_processed}")
        print(f"   Total Time: {elapsed/60:.2f} minutes")
        print(f"   Average FPS: {total_processed/elapsed:.2f}")
        print(f"   Output Directory: {self.output_dir.absolute()}")
        print(f"{'='*60}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch process ROS bags to generate BEV')
    parser.add_argument('--output', default='output_bev', help='Output directory')
    parser.add_argument('--max-frames', type=int, default=None, help='Max frames per bag (None=all)')
    parser.add_argument('--sample-rate', type=int, default=2, help='Process every Nth frame (1=all, 2=half, etc)')
    parser.add_argument('--bag-dir', default='.', help='Directory containing ROS bags')
    
    args = parser.parse_args()
    
    print("\nBatch BEV Processor started.")
    
    processor = BatchBEVProcessor(output_dir=args.output)
    processor.process_all_bags(
        bag_dir=args.bag_dir,
        max_frames_per_bag=args.max_frames,
        sample_rate=args.sample_rate
    )

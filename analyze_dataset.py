"""
ROS Bag Dataset Analyzer
Analyzes the contents and size breakdown of ROS bag files
"""

import json
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from collections import defaultdict
import numpy as np

def analyze_bag(bag_path):
    """Analyze a single ROS bag file"""
    print(f"\n{'='*70}")
    print(f"📦 Analyzing: {Path(bag_path).name}")
    print(f"{'='*70}")
    
    bag_size_mb = Path(bag_path).stat().st_size / (1024**2)
    print(f"📊 File Size: {bag_size_mb:.2f} MB ({bag_size_mb/1024:.2f} GB)")
    
    typestore = get_typestore(Stores.LATEST)
    
    # Statistics
    topic_stats = defaultdict(lambda: {'count': 0, 'total_bytes': 0, 'msg_type': ''})
    total_messages = 0
    start_time = None
    end_time = None
    
    print(f"\n🔍 Scanning messages...")
    
    with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
        # Get topic info
        for conn in reader.connections:
            topic_stats[conn.topic]['msg_type'] = conn.msgtype
        
        # Count messages and sizes
        for connection, timestamp, rawdata in reader.messages():
            topic = connection.topic
            topic_stats[topic]['count'] += 1
            topic_stats[topic]['total_bytes'] += len(rawdata)
            total_messages += 1
            
            if start_time is None:
                start_time = timestamp
            end_time = timestamp
    
    # Calculate duration
    duration_sec = (end_time - start_time) / 1e9 if start_time and end_time else 0
    duration_min = duration_sec / 60
    
    print(f"\n⏱️  RECORDING DETAILS")
    print(f"{'─'*70}")
    print(f"   Duration: {duration_min:.2f} minutes ({duration_sec:.1f} seconds)")
    print(f"   Total Messages: {total_messages:,}")
    print(f"   Average Rate: {total_messages/duration_sec:.1f} msg/sec" if duration_sec > 0 else "   Average Rate: N/A")
    
    # Group by camera
    camera_topics = defaultdict(lambda: {'count': 0, 'size_mb': 0, 'topics': []})
    other_topics = []
    
    for topic, stats in topic_stats.items():
        size_mb = stats['total_bytes'] / (1024**2)
        
        if '/camera_' in topic:
            # Extract camera name
            if '/camera_f/' in topic and 'fl' not in topic and 'fr' not in topic:
                cam = 'Front'
            elif '/camera_fl/' in topic:
                cam = 'Front-Left'
            elif '/camera_fr/' in topic:
                cam = 'Front-Right'
            elif '/camera_r/' in topic and 'rl' not in topic and 'rr' not in topic:
                cam = 'Rear'
            elif '/camera_rl/' in topic:
                cam = 'Rear-Left'
            elif '/camera_rr/' in topic:
                cam = 'Rear-Right'
            else:
                cam = 'Other'
            
            camera_topics[cam]['count'] += stats['count']
            camera_topics[cam]['size_mb'] += size_mb
            camera_topics[cam]['topics'].append({
                'name': topic,
                'count': stats['count'],
                'size_mb': size_mb,
                'type': stats['msg_type']
            })
        else:
            other_topics.append({
                'name': topic,
                'count': stats['count'],
                'size_mb': size_mb,
                'type': stats['msg_type']
            })
    
    # Print camera breakdown
    print(f"\n📹 CAMERA DATA BREAKDOWN")
    print(f"{'─'*70}")
    
    for cam_name in sorted(camera_topics.keys()):
        cam_data = camera_topics[cam_name]
        print(f"\n   🎥 {cam_name} Camera")
        print(f"      Total Size: {cam_data['size_mb']:.2f} MB ({cam_data['size_mb']/bag_size_mb*100:.1f}%)")
        print(f"      Messages: {cam_data['count']:,}")
        print(f"      Topics:")
        
        for topic_info in sorted(cam_data['topics'], key=lambda x: x['size_mb'], reverse=True):
            topic_name = topic_info['name'].split('/')[-1]
            print(f"         • {topic_name:<25} {topic_info['size_mb']:>8.2f} MB  ({topic_info['count']:>6,} msgs)")
    
    # Print other topics
    if other_topics:
        print(f"\n🔧 OTHER TOPICS")
        print(f"{'─'*70}")
        for topic_info in sorted(other_topics, key=lambda x: x['size_mb'], reverse=True):
            print(f"   • {topic_info['name']:<40} {topic_info['size_mb']:>8.2f} MB  ({topic_info['count']:>6,} msgs)")
    
    # Summary
    total_camera_size = sum(cam['size_mb'] for cam in camera_topics.values())
    total_other_size = sum(t['size_mb'] for t in other_topics)
    
    print(f"\n📊 SIZE SUMMARY")
    print(f"{'─'*70}")
    print(f"   Camera Data:  {total_camera_size:>10.2f} MB ({total_camera_size/bag_size_mb*100:.1f}%)")
    print(f"   Other Data:   {total_other_size:>10.2f} MB ({total_other_size/bag_size_mb*100:.1f}%)")
    print(f"   Total:        {bag_size_mb:>10.2f} MB")
    
    # Estimate frame counts
    print(f"\n🎬 ESTIMATED FRAME COUNTS")
    print(f"{'─'*70}")
    for cam_name in sorted(camera_topics.keys()):
        # Find image_raw topic
        raw_topic = next((t for t in camera_topics[cam_name]['topics'] if 'image_raw' in t['name'] and 'sync' not in t['name']), None)
        if raw_topic:
            frames = raw_topic['count']
            fps = frames / duration_sec if duration_sec > 0 else 0
            print(f"   {cam_name:<15} {frames:>6,} frames @ {fps:.1f} FPS")
    
    return {
        'bag_name': Path(bag_path).name,
        'size_mb': bag_size_mb,
        'duration_min': duration_min,
        'total_messages': total_messages,
        'camera_topics': camera_topics,
        'other_topics': other_topics
    }


def analyze_all_bags():
    """Analyze all ROS bags in current directory"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                  ROS BAG DATASET ANALYZER                         ║
║              Understanding Your 23.8 GB Dataset                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    bag_files = list(Path('.').glob('*.db3'))
    
    if not bag_files:
        print("❌ No .db3 files found in current directory!")
        return
    
    print(f"Found {len(bag_files)} ROS bag file(s)\n")
    
    all_results = []
    for bag_file in sorted(bag_files):
        result = analyze_bag(str(bag_file))
        all_results.append(result)
    
    # Overall summary
    print(f"\n{'='*70}")
    print(f"🎯 OVERALL DATASET SUMMARY")
    print(f"{'='*70}")
    
    total_size = sum(r['size_mb'] for r in all_results)
    total_duration = sum(r['duration_min'] for r in all_results)
    total_msgs = sum(r['total_messages'] for r in all_results)
    
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total Size: {total_size:.2f} MB ({total_size/1024:.2f} GB)")
    print(f"   Total Duration: {total_duration:.2f} minutes")
    print(f"   Total Messages: {total_msgs:,}")
    print(f"   Number of Bags: {len(bag_files)}")
    
    print(f"\n💾 What's Taking Up Space:")
    print(f"   • 6 Camera Feeds (1920x1080 each)")
    print(f"   • Multiple formats per camera:")
    print(f"      - image_raw (uncompressed RGB)")
    print(f"      - image_compressed (JPEG)")
    print(f"      - image_rect (rectified)")
    print(f"      - theora (video codec)")
    print(f"      - sync versions")
    print(f"   • Camera calibration info")
    print(f"   • TF transforms")
    print(f"   • System logs")
    
    print(f"\n🎥 Why So Large?")
    print(f"   • 6 cameras × 1920×1080 × 3 bytes (RGB) = ~18 MB per frame set")
    print(f"   • At 30 FPS: ~540 MB per second of recording")
    print(f"   • Multiple formats stored (raw + compressed + rectified)")
    print(f"   • {total_duration:.1f} minutes of recording")
    
    print(f"\n✅ What You're Using:")
    print(f"   • Only 'image_raw' topics (6 cameras)")
    print(f"   • Ignoring compressed/rectified/theora versions")
    print(f"   • This reduces processing load significantly")
    
    print(f"\n{'='*70}\n")


if __name__ == '__main__':
    analyze_all_bags()

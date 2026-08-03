"""
Monitor Batch Processing Progress
Real-time monitoring of BEV batch processing
"""

import os
import time
from pathlib import Path
import sys

def get_dir_size(path):
    """Get total size of directory in MB"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except:
        pass
    return total / (1024 * 1024)  # Convert to MB

def monitor_progress(output_dir='output_high_quality', refresh_interval=10):
    """Monitor the batch processing progress"""
    output_path = Path(output_dir)
    
    if not output_path.exists():
        print(f"Output directory '{output_dir}' not found!")
        print("   Make sure batch processing has started.")
        return
    
    print(f"Monitoring: {output_path.absolute()}")
    print("Press Ctrl+C to stop.\n")
    
    start_time = time.time()
    last_size = 0
    
    try:
        while True:
            # Get current stats
            current_size = get_dir_size(output_path)
            elapsed = time.time() - start_time
            
            # Count files
            video_files = list(output_path.glob('*.mp4'))
            image_files = list(output_path.glob('*.jpg'))
            
            # Calculate rate
            if elapsed > 0:
                mb_per_sec = current_size / elapsed
                size_increase = current_size - last_size
            else:
                mb_per_sec = 0
                size_increase = 0
            
            # Clear screen (Windows)
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print(f"--- BEV Processing Status ---")
            print(f"Elapsed Time:      {int(elapsed // 60)}m {int(elapsed % 60)}s")
            print(f"Output Size:       {current_size:.2f} MB")
            print(f"Processing Rate:   {mb_per_sec:.2f} MB/sec")
            print(f"Video Files:       {len(video_files)}")
            print(f"Sample Images:     {len(image_files)}")
            print("-" * 30)
            
            # Show video files
            for vf in sorted(video_files):
                size = vf.stat().st_size / (1024 * 1024)
                print(f"   {vf.name:<45} {size:>8.2f} MB")
            
            if not video_files:
                print("   (No video files yet)")
            
            print(f"\nRefreshing in {refresh_interval}s...")
            
            last_size = current_size
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        print(f"Final Output: {current_size:.2f} MB")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor BEV batch processing')
    parser.add_argument('--output', default='output_high_quality', help='Output directory to monitor')
    parser.add_argument('--interval', type=int, default=10, help='Refresh interval in seconds')
    
    args = parser.parse_args()
    
    monitor_progress(args.output, args.interval)

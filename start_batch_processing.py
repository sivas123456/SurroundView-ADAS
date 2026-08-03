"""
Batch Processing Launcher
"""

import subprocess
import sys

def print_menu():
    print("\nBatch Processing Options:")
    print("1. Full Processing (All frames)")
    print("2. High Quality (Every 2nd frame)")
    print("3. Preview (Every 5th frame)")
    print("4. Quick Test (First 500 frames)")
    print("5. Custom Configuration")
    print("-" * 30)

print_menu()
choice = input("Select option (1-5): ").strip()

cmd = []

if choice == '1':
    cmd = ['python', 'batch_process_bev.py', '--sample-rate', '1', '--output', 'output_full']
    
elif choice == '2':
    cmd = ['python', 'batch_process_bev.py', '--sample-rate', '2', '--output', 'output_high']
    
elif choice == '3':
    cmd = ['python', 'batch_process_bev.py', '--sample-rate', '5', '--output', 'output_preview']
    
elif choice == '4':
    cmd = ['python', 'batch_process_bev.py', '--sample-rate', '10', '--max-frames', '500', '--output', 'output_test']
    
elif choice == '5':
    sample_rate = input("Sample rate (int): ").strip()
    max_frames = input("Max frames per bag (optional, press Enter to skip): ").strip()
    output = input("Output directory: ").strip() or 'output_custom'
    
    cmd = ['python', 'batch_process_bev.py', '--sample-rate', sample_rate, '--output', output]
    if max_frames:
        cmd.extend(['--max-frames', max_frames])
else:
    print("Invalid selection.")
    sys.exit(1)

print(f"\nExecuting: {' '.join(cmd)}\n")
subprocess.run(cmd)

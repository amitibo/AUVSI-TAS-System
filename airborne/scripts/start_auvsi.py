from __future__ import division
from AUVSIairborne import start_server
import AUVSIairborne.global_settings as gs
import argparse


def main(args):
    
    start_server(
        camera_type=args.camera,
        simulate_pixhawk=args.simulate_pixhawk,
        simulate_targets=args.simulate_targets,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the airborne server.')
    parser.add_argument('--camera', type=str, default='canon', help='Camera type. Options: [canon (default), simlulation].')
    parser.add_argument('--simulate_pixhawk', action='store_true', help='Simulate PixHawk data.')
    parser.add_argument('--simulate_targets', action='store_true', help='Paste simulated targets on the camera images.')
    args = parser.parse_args()
    
    main(args)
    

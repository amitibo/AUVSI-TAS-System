import pkg_resources
import json
import pickle
import os


def main():
    base_path = pkg_resources.resource_filename('AUVSIcv', '../DATA')
    rgb_path = os.path.join(base_path, 'rgb.txt')
    
    colors = {}
    with open(rgb_path, 'rb') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.split()
            name = ' '.join(parts[:-1])
            hex_rgb = parts[-1][1:]

            r = int(hex_rgb[:2], 16)
            g = int(hex_rgb[2:4], 16)
            b = int(hex_rgb[4:6], 16)
            
            colors[name] = (r, g, b)

    with open(os.path.join(base_path, 'colors.pkl'), 'wb') as f:
        pickle.dump(colors, f)

    with open(os.path.join(base_path, 'colors.json'), 'wb') as f:
        json.dump(colors, f)


if __name__ == '__main__':
    main()
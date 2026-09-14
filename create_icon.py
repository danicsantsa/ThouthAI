#!/usr/bin/env python3
"""
Create icon for Workspace Tracking
Generates a professional app icon
"""

from PIL import Image, ImageDraw
import os

def create_icon():
    """Create app icon with A + signal waves"""
    
    # Create icon image
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Security palette: deep graphite with a signal-green accent.
    bg_color = (11, 17, 16, 255)
    draw.ellipse([0, 0, size-1, size-1], fill=bg_color)
    
    # Restrained green rings remain readable at small sizes.
    ring_color = (57, 217, 138, 190)
    ring_width = 8
    
    # Draw concentric rings
    for i in range(3):
        offset = 20 + (i * 25)
        draw.arc([offset, offset, size-offset, size-offset], 
                0, 360, fill=ring_color, width=ring_width)
    
    # Draw "A" in white
    a_color = (232, 243, 237, 255)
    center_x = size // 2
    center_y = size // 2
    
    # Simple "A" shape
    # Left line
    draw.line([(center_x-40, center_y+30), (center_x-5, center_y-40)], 
             fill=a_color, width=12)
    # Right line
    draw.line([(center_x+40, center_y+30), (center_x+5, center_y-40)], 
             fill=a_color, width=12)
    # Horizontal bar
    draw.line([(center_x-30, center_y), (center_x+30, center_y)], 
             fill=a_color, width=10)
    
    # Draw wave at bottom (green)
    wave_color = (57, 217, 138, 255)
    wave_y = center_y + 45
    
    # Wave line
    points = []
    for x in range(center_x-35, center_x+36, 5):
        y = wave_y + int(8 * (1 if (x-center_x) % 20 < 10 else -1))
        points.append((x, y))
    
    if len(points) > 1:
        draw.line(points, fill=wave_color, width=4)
    
    return img

def main():
    print("Creating Workspace Tracking icon...")
    
    icon = create_icon()
    
    # Save as PNG
    icon_path = '/home/danicsantsa/Computervision/workspace-tracking-icon.png'
    icon.save(icon_path, 'PNG')
    print(f"✓ Icon saved: {icon_path}")
    
    # Also save as smaller sizes for different uses
    for size in [128, 64, 32]:
        resized = icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(icon_path.replace('.png', f'-{size}.png'), 'PNG')
        print(f"✓ Icon {size}x{size} saved")
    
    print("\n✓ All icons created successfully!")

if __name__ == '__main__':
    main()

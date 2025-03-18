from PIL import Image
import mss

# Capture full screen
with mss.mss() as sct:
    # Get information on the primary monitor
    monitor = sct.monitors[1]  # [1] refers to the first monitor (full screen)
    
    # Capture the screen
    screenshot = sct.grab(monitor)
    
    # Convert to PIL Image
    img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
    
    # Save or display the image
    img.save("screenshot.png")
    #img.show()

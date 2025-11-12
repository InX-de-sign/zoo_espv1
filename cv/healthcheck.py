"""
Health check for CV service
"""
import cv2
import numpy as np

def check_opencv():
    """Verify OpenCV is working"""
    try:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return {"opencv": "operational", "version": cv2.__version__}
    except Exception as e:
        return {"opencv": "failed", "error": str(e)}
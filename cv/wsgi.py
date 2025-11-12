"""
WSGI entry point for CV service
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

app = FastAPI(title="Museum CV Service")

# Import your existing CV modules here
# from your_cv_module import process_image, detect_paintings

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    """Analyze uploaded image"""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Call your existing CV functions here
        # results = process_image(img)
        
        return JSONResponse(content={
            "status": "success",
            "detected_objects": [],  # Add your detection results
            "paintings": [],  # Add painting detection results
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "cv"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
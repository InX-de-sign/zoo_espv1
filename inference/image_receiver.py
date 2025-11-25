import asyncio
import base64
import logging
from collections import deque
from datetime import datetime
from io import BytesIO
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect
from PIL import Image
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageWebSocketReceiver:
    """Handles WebSocket connections from ESP32 camera clients"""
    
    def __init__(self, inference_callback=None):
        self.clients: Dict[str, WebSocket] = {}
        self.image_queues: Dict[str, deque] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.client_settings: Dict[str, dict] = {}
        self.inference_callback = inference_callback
        
    async def handle_client_with_id(self, websocket: WebSocket, client_id: str, first_message: dict):
        """Handle image stream from ESP32 camera client"""
        logger.info(f"📷 Camera client connected: {client_id}")
        
        # Initialize queue and processing task
        self.image_queues[client_id] = deque(maxlen=10)  # Keep last 10 images
        self.processing_tasks[client_id] = asyncio.create_task(
            self._process_image_queue(client_id, websocket)
        )
        
        # Buffer for reassembling chunked images
        image_reassembly = {}
        
        # Process registration
        if first_message.get("type") == "register":
            self.client_settings[client_id] = first_message.get("camera_settings", {})
            logger.info(f"✅ Camera registered: {client_id}")
            logger.info(f"   Settings: {self.client_settings[client_id]}")
            
            await websocket.send_json({
                "type": "registered",
                "message": "Camera registered successfully",
                "client_id": client_id
            })
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "image_chunk":
                    image_base64 = data.get("image")
                    
                    if not image_base64:
                        logger.warning(f"⚠️ Missing image data in chunk")
                        continue
                    
                    try:
                        image_bytes = base64.b64decode(image_base64)
                        chunk_id = data.get("chunk_id", 0)
                        
                        # Reassemble chunks
                        if chunk_id == 0:
                            # First chunk - reset buffer
                            image_reassembly[client_id] = []
                            total_size = data.get("total_size", 0)
                            if total_size:
                                logger.info(f"📦 Starting image reassembly: {total_size} bytes")
                        
                        image_reassembly.setdefault(client_id, []).append(image_bytes)
                        
                        if chunk_id % 3 == 0:
                            logger.debug(f"📥 Chunk {chunk_id}: {len(image_bytes)} bytes")
                    
                    except Exception as e:
                        logger.error(f"❌ Failed to decode image chunk: {e}")
                        continue
                
                elif data.get("type") == "image_complete":
                    total_chunks = data.get('total_chunks', 0)
                    logger.info(f"📷 Image complete: {total_chunks} chunks")
                    
                    # Combine all chunks and add to queue
                    if client_id in image_reassembly and image_reassembly[client_id]:
                        combined_image = b''.join(image_reassembly[client_id])
                        logger.info(f"✅ Reassembled {len(combined_image)} bytes from {len(image_reassembly[client_id])} chunks")
                        
                        # Convert to PIL Image
                        try:
                            pil_image = Image.open(BytesIO(combined_image))
                            logger.info(f"📸 Image decoded: {pil_image.size[0]}x{pil_image.size[1]} {pil_image.mode}")
                            
                            if client_id in self.image_queues:
                                self.image_queues[client_id].append({
                                    "image": pil_image,
                                    "timestamp": datetime.now(),
                                    "metadata": data.get("metadata", {})
                                })
                                
                        except Exception as e:
                            logger.error(f"❌ Failed to decode image: {e}")
                        
                        # Clear reassembly buffer
                        del image_reassembly[client_id]
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                    
        except WebSocketDisconnect:
            logger.info(f"📴 Camera client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"❌ Client error: {e}")
        finally:
            await self._cleanup_client(client_id)
    
    async def _process_image_queue(self, client_id: str, websocket: WebSocket):
        """Process images from the queue and run inference"""
        logger.info(f"🔄 Image processor started for client: {client_id}")
        
        try:
            while client_id in self.image_queues:
                if self.image_queues[client_id]:
                    image_data = self.image_queues[client_id].popleft()
                    
                    # Run inference if callback is provided
                    if self.inference_callback:
                        try:
                            detections = await self.inference_callback(
                                image_data["image"], 
                                client_id
                            )
                            
                            # Send results back to ESP32
                            await websocket.send_json({
                                "type": "inference_result",
                                "detections": detections,
                                "timestamp": datetime.now().isoformat(),
                                "client_id": client_id
                            })
                            
                            logger.info(f"✅ Sent {len(detections)} detections to {client_id}")
                            
                        except Exception as e:
                            logger.error(f"❌ Inference error: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": str(e),
                                "timestamp": datetime.now().isoformat()
                            })
                
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for {client_id}")
        except Exception as e:
            logger.error(f"Error in image processor: {e}")
    
    async def _cleanup_client(self, client_id: str):
        """Clean up client resources"""
        if client_id in self.processing_tasks:
            self.processing_tasks[client_id].cancel()
            del self.processing_tasks[client_id]
        
        if client_id in self.image_queues:
            del self.image_queues[client_id]
        
        if client_id in self.clients:
            del self.clients[client_id]
        
        if client_id in self.client_settings:
            del self.client_settings[client_id]
        
        logger.info(f"🔌 Disconnected: {client_id}")
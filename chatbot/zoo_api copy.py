# zoo_api.py - FastAPI for Zoo chatbot (PORT 8000)
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ocean Park Zoo Chatbot API")

# Import zoo components
from zoo_main import HybridZooAI
from config import load_azure_openai_config

openai_config = load_azure_openai_config()
assistant = HybridZooAI(openai_api_key=openai_config.api_key, db_path="zoo.db")

# Mount static files if they exist
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Serve the chatbot interface"""
    html_path = os.path.join("static", "zoo_index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <html>
            <head><title>Ocean Park Zoo Chatbot</title></head>
            <body>
                <h1>🐼 Ocean Park Zoo Chatbot</h1>
                <p>WebSocket endpoint: ws://localhost:8000/ws</p>
                <p>Create a file at static/zoo_index.html for the full interface</p>
            </body>
        </html>
        """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time chat"""
    await websocket.accept()
    
    client_id = f"user_{hash(str(websocket.client))}_{int(asyncio.get_event_loop().time())}"[-10:]
    logger.info(f"🐼 Zoo client connected: {client_id}")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "message": "Welcome to Ocean Park! I'm your zoo guide! Ask me about anything that interests you!"
        })
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            logger.info(f"Zoo query from {client_id}: {message}")
            
            # Send thinking indicator
            await websocket.send_json({
                "type": "thinking",
                "message": "Let me check our animal database..."
            })
            
            try:
                # Process with zoo AI
                response = await assistant.process_message(message, client_id)
                
                # Send response
                await websocket.send_json({
                    "type": "response",
                    "message": response
                })
                
                logger.info(f"Zoo response sent to {client_id}")
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Sorry, I had trouble with that question. Can you try asking differently?"
                })
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info(f"🐼 Zoo client disconnected: {client_id}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Ocean Park Zoo Chatbot",
        "port": 8000,
        "openai_available": True,
        "database": assistant.db_path if hasattr(assistant, 'db_path') else "unknown"
    }

@app.get("/test-database")
async def test_database():
    """Test if zoo database is working"""
    try:
        import sqlite3
        
        if not assistant.db_path or not os.path.exists(assistant.db_path):
            return {"error": "Database not found", "path": assistant.db_path}
        
        conn = sqlite3.connect(assistant.db_path)
        cursor = conn.cursor()
        
        # Get animal count
        cursor.execute("SELECT COUNT(*) FROM animals")
        count = cursor.fetchone()[0]
        
        # Get sample animals
        cursor.execute("SELECT common_name, scientific_name, location_at_park FROM animals LIMIT 5")
        samples = cursor.fetchall()
        
        conn.close()
        
        return {
            "status": "success",
            "database_path": assistant.db_path,
            "total_animals": count,
            "sample_animals": [
                {"name": name, "scientific": sci, "location": loc}
                for name, sci, loc in samples
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/animals")
async def list_animals():
    """List all animals in database"""
    try:
        import sqlite3
        
        if not assistant.db_path or not os.path.exists(assistant.db_path):
            return {"error": "Database not found"}
        
        conn = sqlite3.connect(assistant.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT common_name, scientific_name, habitat, location_at_park
            FROM animals
            ORDER BY common_name
        ''')
        
        animals = cursor.fetchall()
        conn.close()
        
        return {
            "total": len(animals),
            "animals": [
                {
                    "name": name,
                    "scientific_name": sci,
                    "habitat": habitat,
                    "location": location
                }
                for name, sci, habitat, location in animals
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/animal/{animal_name}")
async def get_animal_info(animal_name: str):
    """Get detailed information about a specific animal"""
    try:
        import sqlite3
        
        if not assistant.db_path or not os.path.exists(assistant.db_path):
            return {"error": "Database not found"}
        
        conn = sqlite3.connect(assistant.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT *
            FROM animals
            WHERE LOWER(common_name) LIKE ?
        ''', (f'%{animal_name.lower()}%',))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {"error": "Animal not found", "searched_for": animal_name}
        
        # Map to column names
        columns = ['id', 'common_name', 'scientific_name', 'distribution_range', 'habitat',
                  'phylum', 'class', 'order_name', 'family', 'genus',
                  'characteristics', 'body_measurements', 'diet', 'behavior',
                  'location_at_park', 'stories', 'conservation_status', 'threats', 'conservation_actions']
        
        animal_data = dict(zip(columns, result))
        return animal_data
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("🐼 Starting Ocean Park Zoo Chatbot API")
    logger.info("=" * 60)
    logger.info("Port: 9001 (different from museum's 8000)")
    logger.info("WebSocket: ws://localhost:9001/ws")
    logger.info("Web UI: http://localhost:9001")
    logger.info("Health: http://localhost:9001/health")
    logger.info("Database Test: http://localhost:9001/test-database")
    logger.info("=" * 60)
    
    # Create database if it doesn't exist
    if not os.path.exists("zoo.db"):
        logger.info("Creating zoo database...")
        from create_zoo_database import create_zoo_database
        create_zoo_database()
    
    uvicorn.run(app, host="0.0.0.0", port=9001)
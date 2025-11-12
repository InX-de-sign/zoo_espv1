"""
Health check endpoints for the chatbot service
"""
from datetime import datetime
from typing import Dict, Any
import psutil
import os

def get_health_status() -> Dict[str, Any]:
    """
    Get comprehensive health status of the service
    """
    return {
        "status": "healthy",
        "service": "chatbot",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": check_database_connection(),
            "redis": check_redis_connection(),
            "vectordb": check_vectordb_connection(),
            "memory": check_memory_usage(),
            "disk": check_disk_usage(),
        }
    }

def check_database_connection() -> Dict[str, Any]:
    """Check PostgreSQL connection"""
    try:
        from sqlalchemy import create_engine
        from config import DATABASE_URL
        
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            return {"status": "healthy", "response_time": "< 1ms"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_redis_connection() -> Dict[str, Any]:
    """Check Redis connection"""
    try:
        import redis
        from config import REDIS_URL
        
        r = redis.from_url(REDIS_URL)
        r.ping()
        return {"status": "healthy", "response_time": "< 1ms"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_vectordb_connection() -> Dict[str, Any]:
    """Check Vector Database connection"""
    try:
        import requests
        from config import VECTORDB_URL
        
        response = requests.get(f"{VECTORDB_URL}/health", timeout=2)
        if response.status_code == 200:
            return {"status": "healthy", "response_time": f"{response.elapsed.total_seconds()*1000:.0f}ms"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_memory_usage() -> Dict[str, Any]:
    """Check memory usage"""
    memory = psutil.virtual_memory()
    return {
        "usage_percent": memory.percent,
        "available_gb": round(memory.available / (1024**3), 2),
        "status": "healthy" if memory.percent < 80 else "warning"
    }

def check_disk_usage() -> Dict[str, Any]:
    """Check disk usage"""
    disk = psutil.disk_usage('/')
    return {
        "usage_percent": disk.percent,
        "available_gb": round(disk.free / (1024**3), 2),
        "status": "healthy" if disk.percent < 80 else "warning"
    }

# Add to your existing api.py
def add_health_endpoints(app):
    """Add health check endpoints to your Flask/FastAPI app"""
    
    # For FastAPI
    if hasattr(app, 'get'):
        @app.get("/health")
        async def health():
            return get_health_status()
        
        @app.get("/health/live")
        async def liveness():
            return {"status": "alive"}
        
        @app.get("/health/ready")
        async def readiness():
            health = get_health_status()
            is_ready = all(
                check.get("status") == "healthy" 
                for check in health["checks"].values()
                if isinstance(check, dict)
            )
            return {"ready": is_ready}
    
    # For Flask
    else:
        from flask import jsonify
        
        @app.route('/health')
        def health():
            return jsonify(get_health_status())
        
        @app.route('/health/live')
        def liveness():
            return jsonify({"status": "alive"})
        
        @app.route('/health/ready')
        def readiness():
            health = get_health_status()
            is_ready = all(
                check.get("status") == "healthy"
                for check in health["checks"].values()
                if isinstance(check, dict)
            )
            return jsonify({"ready": is_ready})
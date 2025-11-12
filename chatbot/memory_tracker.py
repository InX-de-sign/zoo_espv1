# memory_tracker.py - Zoo version
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import sqlite3

class HybridMemoryTracker:
    """
    Hybrid memory system for zoo chatbot:
    - Custom tracker for conversation history and context
    - Persistent storage for long-term memory
    """
    
    def __init__(self, memory_db_path="memory.db", max_history=20):
        self.memory_db_path = memory_db_path
        self.max_history = max_history
        
        # In-memory conversation tracking
        self.conversations = {}  # user_id -> conversation data
        
        # Initialize database
        self.init_memory_db()
        
        print("Hybrid Memory Tracker initialized for zoo")
    
    def init_memory_db(self):
        """Initialize memory database"""
        try:
            conn = sqlite3.connect(self.memory_db_path)
            cursor = conn.cursor()
            
            # Conversation history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    intent TEXT,
                    entities TEXT,
                    source TEXT DEFAULT 'unknown'
                )
            ''')
            
            # User preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    favorite_animals TEXT,
                    interest_level TEXT,
                    preferred_topics TEXT,
                    last_visit REAL,
                    visit_count INTEGER DEFAULT 1,
                    data TEXT
                )
            ''')
            
            # Current session state table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_state (
                    user_id TEXT PRIMARY KEY,
                    slots TEXT,
                    current_topic TEXT,
                    conversation_stage TEXT,
                    last_updated REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            print("Memory database initialized")
            
        except Exception as e:
            print(f"Memory database initialization failed: {e}")
    
    def track_interaction(self, user_id: str, message: str, response: str, 
                         intent: Optional[str] = None, entities: List[Dict] = None,
                         source: str = "unknown"):
        """Track a conversation interaction"""
        
        # Update in-memory tracking
        if user_id not in self.conversations:
            self.conversations[user_id] = {
                "history": [],
                "current_topic": None,
                "interests": set(),
                "mentioned_animals": set(),
                "session_start": time.time()
            }
        
        conversation = self.conversations[user_id]
        
        # Add to conversation history (keep only recent)
        conversation["history"].append({
            "timestamp": time.time(),
            "message": message,
            "response": response,
            "intent": intent,
            "entities": entities or [],
            "source": source
        })
        
        # Keep only recent history in memory
        if len(conversation["history"]) > self.max_history:
            conversation["history"] = conversation["history"][-self.max_history:]
        
        # Extract and update interests
        self.update_user_interests(user_id, message, entities)
        
        # Store in database
        self.store_interaction(user_id, message, response, intent, entities, source)
        
        return conversation
    
    def update_user_interests(self, user_id: str, message: str, entities: List[Dict] = None):
        """Update user interests based on message"""
        conversation = self.conversations.get(user_id)
        if not conversation:
            return
        
        message_lower = message.lower()
        
        # Track mentioned animals
        animals = ["panda", "capybara", "sloth", "penguin", "seal", "sea lion", "fox", "red panda", "arctic fox"]
        for animal in animals:
            if animal in message_lower:
                conversation["mentioned_animals"].add(animal)
        
        # Track topics of interest
        zoo_topics = {
            "conservation": ["conservation", "protect", "endangered", "save", "threats"],
            "diet": ["diet", "eat", "food", "feed", "feeding"],
            "behavior": ["behavior", "behaviour", "act", "play", "sleep", "swim"],
            "habitat": ["habitat", "home", "live", "environment", "where"],
            "characteristics": ["look", "appearance", "size", "color", "fur", "features"]
        }
        
        for topic, keywords in zoo_topics.items():
            if any(keyword in message_lower for keyword in keywords):
                conversation["interests"].add(topic)
        
        # Update current topic based on recent context
        if entities:
            for entity in entities:
                if entity.get("entity") == "animal":
                    conversation["current_topic"] = entity.get("value")
    
    def store_interaction(self, user_id: str, message: str, response: str,
                         intent: Optional[str], entities: List[Dict], source: str):
        """Store interaction in database"""
        try:
            conn = sqlite3.connect(self.memory_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO conversation_history 
                (user_id, timestamp, message, response, intent, entities, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, time.time(), message, response, intent, 
                  json.dumps(entities) if entities else None, source))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Failed to store interaction: {e}")
    
    def get_conversation_context(self, user_id: str, last_n: int = 3) -> Dict[str, Any]:
        """Get recent conversation context for better responses"""
        conversation = self.conversations.get(user_id)
        if not conversation:
            return {}
        
        recent_history = conversation["history"][-last_n:] if conversation["history"] else []
        
        context = {
            "recent_messages": [h["message"] for h in recent_history],
            "recent_responses": [h["response"] for h in recent_history],
            "current_topic": conversation.get("current_topic"),
            "interests": list(conversation.get("interests", [])),
            "mentioned_animals": list(conversation.get("mentioned_animals", [])),
            "conversation_length": len(conversation["history"]),
            "session_duration": time.time() - conversation.get("session_start", time.time())
        }
        
        return context
    
    def get_personalized_context(self, user_id: str) -> str:
        """Generate personalized context string for RAG"""
        context = self.get_conversation_context(user_id)
        
        if not context:
            return "This is a new visitor to the zoo."
        
        context_parts = []
        
        # Add conversation context
        if context.get("mentioned_animals"):
            animals = ", ".join(context["mentioned_animals"])
            context_parts.append(f"User has shown interest in: {animals}")
        
        if context.get("current_topic"):
            context_parts.append(f"Currently discussing: {context['current_topic']}")
        
        if context.get("interests"):
            interests = ", ".join(context["interests"])
            context_parts.append(f"Interested in: {interests}")
        
        # Add conversation flow context
        if context.get("conversation_length", 0) > 5:
            context_parts.append("User is engaged in extended conversation")
        
        return " | ".join(context_parts) if context_parts else "New conversation starting"
    
    def update_slots(self, user_id: str, slots: Dict[str, Any]):
        """Update session slots and store as backup"""
        try:
            conn = sqlite3.connect(self.memory_db_path)
            cursor = conn.cursor()
            
            # Get conversation context for additional info
            context = self.get_conversation_context(user_id)
            
            # Merge slots with context
            enhanced_slots = slots.copy()
            enhanced_slots.update({
                "mentioned_animals": context.get("mentioned_animals", []),
                "interests": context.get("interests", []),
                "current_topic": context.get("current_topic")
            })
            
            cursor.execute('''
                INSERT OR REPLACE INTO session_state 
                (user_id, slots, current_topic, conversation_stage, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, json.dumps(enhanced_slots), 
                  context.get("current_topic"), "active", time.time()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Failed to update slots: {e}")
    
    def get_memory_summary(self, user_id: str) -> Dict[str, Any]:
        """Get complete memory summary for user"""
        try:
            conn = sqlite3.connect(self.memory_db_path)
            cursor = conn.cursor()
            
            # Get conversation stats
            cursor.execute('''
                SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                FROM conversation_history 
                WHERE user_id = ?
            ''', (user_id,))
            
            stats = cursor.fetchone()
            total_messages, first_visit, last_visit = stats if stats else (0, None, None)
            
            # Get recent topics
            cursor.execute('''
                SELECT intent, COUNT(*) as count
                FROM conversation_history 
                WHERE user_id = ? AND intent IS NOT NULL
                GROUP BY intent 
                ORDER BY count DESC 
                LIMIT 5
            ''', (user_id,))
            
            popular_intents = cursor.fetchall()
            
            conn.close()
            
            # Combine with current session data
            current_context = self.get_conversation_context(user_id)
            
            return {
                "total_interactions": total_messages,
                "first_visit": first_visit,
                "last_visit": last_visit,
                "popular_intents": popular_intents,
                "current_session": current_context,
                "memory_available": user_id in self.conversations
            }
            
        except Exception as e:
            print(f"Memory summary failed: {e}")
            return {}
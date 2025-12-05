# zoo_main.py - Adapted for Ocean Park Zoo chatbot
from enhanced_rag_openai import EnhancedRAGWithOpenAI  
from memory_tracker import HybridMemoryTracker
import asyncio
import os
import logging
import json
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridZooAI:
    """
    HYBRID: Local database + OpenAI Enhanced RAG for ZOO
    - local database: customized for zoo animals
    - OpenAI: Advanced queries with local context
    """
    
    def __init__(self, openai_api_key=None, db_path=None):
        logger.info("Initializing Hybrid Zoo AI (Local + OpenAI)...")
        
        # Initialize memory system
        self.memory = HybridMemoryTracker()
        logger.info("Memory system initialized")
        
        # Initialize Enhanced RAG with OpenAI
        try:
            self.enhanced_rag = EnhancedRAGWithOpenAI(db_path=db_path)
            logger.info("Enhanced RAG + OpenAI initialized")
        except Exception as e:
            logger.error(f"Enhanced RAG failed: {e}")
            raise Exception("Enhanced RAG system required")
        
        # Database path
        self.db_path = db_path or self._find_database()
                
        logger.info("Hybrid Zoo AI ready!")
    
    def _normalize_animal_name(self, animal_name: str) -> str:
        """
        Normalize animal names from CV detection to match database format
        CV sends: "red-panda", "arctic-fox", "harbor-seal"
        Database has: "red panda", "arctic fox", "harbor seal"
        """
        if not animal_name:
            return None
        
        # Replace hyphens with spaces
        normalized = animal_name.replace('-', ' ')
        
        # Handle common variations
        name_mappings = {
            'red panda': 'red panda',
            'arctic fox': 'arctic fox',
            'harbor seal': 'seal',  # Database might have "harbour seal" or just "seal"
            'harbour seal': 'seal',
            'sea lion': 'sea lion',
            'giant panda': 'panda'
        }
        
        return name_mappings.get(normalized.lower(), normalized)


    async def process_message(self, message_text, user_id="default_user", cv_detected_animal=None):
        try:
            logger.info(f"Processing: '{message_text[:50]}...' for user: {user_id}")
            
            if user_id not in self.memory.conversations:
                logger.info(f"🔄 Restoring previous session for {user_id}")
                self._restore_session(user_id)

            # 🎯 NORMALIZE CV detection
            normalized_cv_animal = None
            if cv_detected_animal:
                normalized_cv_animal = self._normalize_animal_name(cv_detected_animal)
                logger.info(f"🎯 CV DETECTED: {normalized_cv_animal} (from {cv_detected_animal})")
                
                # Update current topic (but don't clear history)
                if user_id in self.memory.conversations:
                    self.memory.conversations[user_id]["current_topic"] = normalized_cv_animal
                    # Add to mentioned animals set
                    if "mentioned_animals" not in self.memory.conversations[user_id]:
                        self.memory.conversations[user_id]["mentioned_animals"] = set()
                    self.memory.conversations[user_id]["mentioned_animals"].add(normalized_cv_animal)

            message_lower = message_text.lower()

            # Use CV detection first, fallback to text detection
            detected_animal = normalized_cv_animal or self._detect_animal(message_text)

            conversation_context = self.memory.get_conversation_context(user_id)
            personalized_context = self.memory.get_personalized_context(user_id)
            
            query_type = self._determine_query_type(message_text, conversation_context)

            # 🎯 BUILD CONTEXT WITH CV PRIORITY
            full_context = {
                'local_database': self._get_relevant_local_context(message_text, detected_animal),  
                'user_context': personalized_context,
                'detected_animal': detected_animal,
                'cv_detected_animal': normalized_cv_animal,  # 🆕 ADD THIS
                'query_type': query_type,
                'conversation_history': conversation_context.get('recent_messages', [])
            }

            # 🎯 ADD STRONG CV CONTEXT INSTRUCTION
            if normalized_cv_animal:
                full_context['cv_instruction'] = f"""
    IMPORTANT: The user is currently viewing a {normalized_cv_animal} through their camera.
    Unless they explicitly ask about a different animal, assume all questions refer to the {normalized_cv_animal}.
    Give priority to information about the {normalized_cv_animal} in your response.
    """

            response = await self.enhanced_rag.process_query_with_openai(
                query=message_text,
                context=full_context,
                user_id=user_id
            )

            self.memory.track_interaction(
                user_id=user_id,
                message=message_text,
                response=response,
                intent=self._extract_intent(message_text),
                entities=self._extract_entities(message_text, detected_animal),
                source="zoo_rag_openai"
            )

            logger.info(f"Response generated: '{response[:50]}...'")             
            return response
                        
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return "I'm having some technical difficulties, but I'm still here to help with your animal questions!"


    # 3. Update stream_message - SAME LOGIC
    async def stream_message(self, message_text, user_id="default_user", cv_detected_animal=None):
        """
        Stream OpenAI response word-by-word for real-time TTS
        """
        try:
            logger.info(f"Streaming: '{message_text[:50]}...' for user: {user_id}")
            
            if user_id not in self.memory.conversations:
                self._restore_session(user_id)

            # 🎯 NORMALIZE CV detection
            normalized_cv_animal = None
            if cv_detected_animal:
                normalized_cv_animal = self._normalize_animal_name(cv_detected_animal)
                logger.info(f"🎯 CV DETECTED FOR STREAMING: {normalized_cv_animal}")
                
                if user_id in self.memory.conversations:
                    self.memory.conversations[user_id]["current_topic"] = normalized_cv_animal
                    if "mentioned_animals" not in self.memory.conversations[user_id]:
                        self.memory.conversations[user_id]["mentioned_animals"] = set()
                    self.memory.conversations[user_id]["mentioned_animals"].add(normalized_cv_animal)

            detected_animal = normalized_cv_animal or self._detect_animal(message_text)
            conversation_context = self.memory.get_conversation_context(user_id)
            personalized_context = self.memory.get_personalized_context(user_id)
            query_type = self._determine_query_type(message_text, conversation_context)

            # 🎯 BUILD CONTEXT WITH CV PRIORITY
            full_context = {
                'local_database': self._get_relevant_local_context(message_text, detected_animal),  
                'user_context': personalized_context,
                'detected_animal': detected_animal,
                'cv_detected_animal': normalized_cv_animal,  # 🆕 ADD THIS
                'query_type': query_type,
                'conversation_history': conversation_context.get('recent_messages', [])
            }
            
            # 🎯 ADD STRONG CV CONTEXT INSTRUCTION
            if normalized_cv_animal:
                full_context['cv_instruction'] = f"""
    IMPORTANT: The user is currently viewing a {normalized_cv_animal} through their camera.
    Unless they explicitly ask about a different animal, assume all questions refer to the {normalized_cv_animal}.
    Give priority to information about the {normalized_cv_animal} in your response.
    """

            # Stream from OpenAI
            full_response = ""
            async for chunk in self.enhanced_rag.stream_query_with_openai(
                query=message_text,
                context=full_context,
                user_id=user_id
            ):
                full_response += chunk
                yield chunk

            # Track after streaming complete
            self.memory.track_interaction(
                user_id=user_id,
                message=message_text,
                response=full_response,
                intent=self._extract_intent(message_text),
                entities=self._extract_entities(message_text, detected_animal),
                source="zoo_rag_openai_stream"
            )
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "I'm having some technical difficulties, but I'm still here to help!"


    # 4. Update _extract_entities to include detected animal
    def _extract_entities(self, message_text, detected_animal=None):
        """Simple entity extraction for memory tracking"""
        entities = []
        
        # 🎯 PRIORITIZE CV DETECTED ANIMAL
        if detected_animal:
            entities.append({"entity": "animal", "value": detected_animal, "source": "cv_detection"})
        else:
            # Fallback to text detection
            animal = self._detect_animal(message_text)
            if animal:
                entities.append({"entity": "animal", "value": animal, "source": "text_detection"})
        
        return entities


    # 5. Update _get_relevant_local_context to use normalized name
    def _get_relevant_local_context(self, message_text, detected_animal=None):
        """Get relevant content from zoo database"""
        if not self.db_path or not os.path.exists(self.db_path):
            return "No local database available."
        
        try:
            import sqlite3
            
            # 🎯 NORMALIZE the animal name
            animal_name = self._normalize_animal_name(detected_animal) if detected_animal else self._detect_animal(message_text)
            
            if animal_name:
                logger.info(f"🔍 Searching database for: {animal_name}")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Search by common name with flexible matching
                cursor.execute('''
                    SELECT common_name, scientific_name, distribution_range, habitat,
                        characteristics, body_measurements, diet, behavior,
                        location_at_park, stories, conservation_status, threats, conservation_actions
                    FROM animals
                    WHERE LOWER(common_name) LIKE ? OR LOWER(common_name) LIKE ?
                ''', (f'%{animal_name}%', f'%{animal_name.replace(" ", "%")}%'))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    logger.info(f"✅ Found database entry for: {animal_name}")
                    common_name, sci_name, distribution, habitat, chars, measurements, diet, behavior, location, stories, status, threats, actions = result
                    
                    return f"""OCEAN PARK ANIMAL INFORMATION:
    Common Name: {common_name or 'Unknown'}
    Scientific Name: {sci_name or 'Unknown'}
    Distribution: {distribution or 'Unknown'}
    Habitat: {habitat or 'Unknown'}
    Physical Characteristics: {chars or 'No information available'}
    Body Measurements: {measurements or 'Not specified'}
    Diet: {diet or 'Not specified'}
    Behavior: {behavior or 'Not specified'}
    Location at Park: {location or 'Check park map'}
    Conservation Status: {status or 'Not specified'}
    Threats: {threats or 'Not specified'}
    Conservation Actions: {actions or 'Not specified'}
    Stories: {stories or 'No stories available'}"""
                else:
                    logger.warning(f"⚠️ No database entry found for: {animal_name}")
            
            # Fallback: general collection info
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT common_name, scientific_name, location_at_park FROM animals LIMIT 3")
            all_animals = cursor.fetchall()
            conn.close()
            
            if all_animals:
                context_parts = ["OCEAN PARK ANIMAL COLLECTION:"]
                for name, sci_name, location in all_animals:
                    context_parts.append(f"- {name} ({sci_name}) at {location}")
                
                return "\n".join(context_parts)
            
            return "Animal collection information unavailable."
                
        except Exception as e:
            logger.error(f"Database context error: {e}")
            return "Local database context unavailable due to error."             

    def _restore_session(self, user_id: str):
        """Restore previous conversation session from database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.memory.memory_db_path)
            cursor = conn.cursor()
            
            # Get last 5 interactions
            cursor.execute('''
                SELECT message, response, intent, entities, timestamp
                FROM conversation_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                # Initialize conversation in memory
                self.memory.conversations[user_id] = {
                    "history": [],
                    "current_topic": None,
                    "interests": set(),
                    "mentioned_animals": set(),
                    "session_start": time.time()
                }
                
                # Restore history (reverse order - oldest first)
                for message, response, intent, entities_json, timestamp in reversed(rows):
                    entities = json.loads(entities_json) if entities_json else []
                    self.memory.conversations[user_id]["history"].append({
                        "timestamp": timestamp,
                        "message": message,
                        "response": response,
                        "intent": intent,
                        "entities": entities,
                        "source": "restored"
                    })
                    
                    # Restore interests
                    self.memory.update_user_interests(user_id, message, entities)
                
                logger.info(f"✅ Restored {len(rows)} previous interactions for {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to restore session: {e}")

    def _determine_query_type(self, message_text, context):
        """Determine query type for zoo context"""
        message_lower = message_text.lower()
        
        # Advanced analysis
        advanced_indicators = [
            "analyze", "compare", "explain", "meaning", "behavior", "adaptation",
            "evolution", "why", "how does", "conservation"
        ]
        
        if any(indicator in message_lower for indicator in advanced_indicators):
            return 'advanced_animal_query'
        
        # Basic animal queries
        animal_keywords = ["panda", "capybara", "sloth", "penguin", "seal", "sea lion", "fox", "red panda"]
        basic_indicators = ["what is", "tell me about", "describe", "where is", "how big"]
        
        has_animal = any(keyword in message_lower for keyword in animal_keywords)
        has_basic = any(indicator in message_lower for indicator in basic_indicators)
        
        if has_animal and has_basic:
            return 'basic_animal_info'
        elif has_animal:
            return 'basic_animal_info'
        
        # Park info queries
        park_keywords = ["hours", "tickets", "price", "open", "restroom", "cafe", "location"]
        if any(keyword in message_lower for keyword in park_keywords):
            return 'park_info'
        
        return 'general_animal_knowledge'

    def _detect_animal(self, message_text):
        """Detect which animal the user is asking about"""
        message_lower = message_text.lower()
        
        animal_mappings = {
            'capybara': ['capybara'],
            'red panda': ['red panda'],
            'panda': ['panda', 'giant panda'],
            'sloth': ['sloth'],
            'arctic fox': ['arctic fox', 'fox'],
            'sea lion': ['sea lion', 'california sea lion'],
            'penguin': ['penguin', 'king penguin'],
            'seal': ['seal', 'harbour seal', 'harbor seal']
        }
        
        for canonical_name, variations in animal_mappings.items():
            if any(var in message_lower for var in variations):
                return canonical_name
        
        return None


    def _extract_intent(self, message_text):
        """Simple intent extraction for memory tracking"""
        message_lower = message_text.lower()
        
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "greet"
        elif any(word in message_lower for word in ["hours", "open", "time"]):
            return "ask_hours"
        elif any(word in message_lower for word in ["price", "ticket", "cost"]):
            return "ask_pricing"
        elif any(word in message_lower for word in ["where", "location", "find"]):
            return "locate_animal"
        elif any(word in message_lower for word in ["conservation", "protect", "endangered"]):
            return "conservation_query"
        elif any(word in message_lower for word in ["panda", "capybara", "sloth", "penguin"]):
            return "animal_info"
        else:
            return "general_query"


    def get_user_insights(self, user_id):
        """Get insights about user for personalization"""
        return self.memory.get_memory_summary(user_id)
    
    def _find_database(self):
        """Find zoo database"""
        possible_paths = [
            'zoo.db',
            os.path.join(os.path.dirname(__file__), 'zoo.db'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Database found: {path}")
                return path
        logger.warning("No database found")
        return None

# For backward compatibility
ZooAIAssistant = HybridZooAI

# Test the zoo system
async def test_zoo_system():
    """Test the zoo AI system"""
    print("Testing Zoo AI System")
    print("=" * 50)
    
    # Create database first
    import sys
    sys.path.append(os.path.dirname(__file__))
    from create_zoo_database import create_zoo_database
    db_path = create_zoo_database()
    
    assistant = HybridZooAI(db_path=db_path)
    user_id = "test_user"
    
    test_queries = [
        "Hello!",
        "Tell me about capybaras",
        "Where can I find the pandas?",
        "What do red pandas eat?",
        "What conservation efforts are being done for arctic foxes?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{query}'")
        try:
            response = await assistant.process_message(query, user_id)
            print(f"   Response: {response[:150]}...")
                  
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\nZoo system test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_zoo_system())
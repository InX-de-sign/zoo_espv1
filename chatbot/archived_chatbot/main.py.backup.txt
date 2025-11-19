# main.py - FIXED VERSION WITHOUT SYNTAX ERRORS
from enhanced_rag_openai import EnhancedRAGWithOpenAI  
from memory_tracker import HybridMemoryTracker
import asyncio
import os
import logging
import requests  # ADDED: Missing import
from typing import Dict, Any  # ADDED: Missing import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridMuseumAI:
    """
    HYBRID: Local database + OpenAI Enhanced RAG
    - local database: customized for museum artifacts
    - OpenAI: Low-confidence or advanced queries with local context
    - Direct path: User Query -> Memory Context -> Enhanced RAG -> Response
    """
    
    def __init__(self, openai_api_key=None, rasa_model_path=None, db_path=None):
        logger.info("Initializing Hybrid Museum AI (Local + OpenAI)...")
        
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
                
        logger.info("Hybrid Museum AI ready!")
    
    async def detect_current_painting(self):
        """Call CV service to detect what painting user is looking at"""
        try:
            response = requests.get(
                "http://museum_cv:8001/detect-current",
                timeout=10
            )
            
            if response.status_code == 200:
                cv_result = response.json()
                if cv_result["status"] == "found":
                    painting_label = cv_result["detection"]["label"]
                    confidence = cv_result["detection"]["confidence"]
                    
                    logger.info(f"CV detected: {painting_label} (confidence: {confidence})")
                    return painting_label
            
            return None
            
        except Exception as e:
            logger.error(f"CV service error: {e}")
            return None
    
    async def process_message(self, message_text, user_id="default_user", cv_detected_artifact=None):
        try:
            logger.info(f"Processing: '{message_text[:50]}...' for user: {user_id}")
            
            message_lower = message_text.lower()

            # Check if user is explicitly asking about what they're looking at
            is_asking_about_current_view = any(phrase in message_lower for phrase in [
                "what am i looking at", "what's this", "what is this", "identify this",
                "tell me about this", "what painting is this", "what artwork",
                "this painting", "this artwork", "colors in this", "in this painting",
                "the painting", "the artwork", "what artifact was i looking at"
            ])

            if is_asking_about_current_view and not cv_detected_artifact:
                cv_detected_artifact = await self.detect_current_painting()
                if cv_detected_artifact:
                    logger.info(f"CV service returned: {cv_detected_artifact}")
            
            # If CV detected an artifact, prioritize that context
            if cv_detected_artifact:
                logger.info(f"CV detection active: {cv_detected_artifact}")
                detected_artifact = cv_detected_artifact
            else:
                detected_artifact = self._detect_artifact(message_text)

            conversation_context = self.memory.get_conversation_context(user_id)
            personalized_context = self.memory.get_personalized_context(user_id)
            
            # Adjust query type based on CV detection and user intent
            if is_asking_about_current_view and cv_detected_artifact:
                query_type = 'cv_identified_artifact'  # Special type for "what am I looking at"
            else:
                query_type = self._determine_query_type(message_text, conversation_context)

            full_context = {
                'local_database': self._get_relevant_local_context(message_text, detected_artifact),  
                'user_context': personalized_context,
                'detected_artifact': detected_artifact,
                'cv_detected': cv_detected_artifact is not None,
                'asking_about_current_view': is_asking_about_current_view,
                'query_type': query_type,
                'conversation_history': conversation_context.get('recent_messages', [])
            }

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
                entities=self._extract_entities(message_text),
                source="simplified_rag_openai"
            )

            logger.info(f"Response generated: '{response[:50]}...'")             
            return response
                
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return "I'm having some technical difficulties, but I'm still here to help with your art questions!"

    def _determine_query_type(self, message_text, context):
        """Simplified query type determination"""
        message_lower = message_text.lower()
        
        # Check for advanced analysis keywords
        advanced_indicators = [
            "analyze", "compare", "explain", "meaning", "symbolism", "technique",
            "influence", "style", "interpretation", "significance", "theory", "why", "how does"
        ]
        
        if any(indicator in message_lower for indicator in advanced_indicators):
            return 'advanced_local_artifact'
        
        # Check for basic artwork queries
        artwork_keywords = ["van gogh", "lady jane", "jane grey", "traquair", "victory", "cafe terrace", "openfish", "robot fish", "fish"]
        basic_indicators = ["what is", "tell me about", "describe", "where is", "who painted"]
        
        has_artwork = any(keyword in message_lower for keyword in artwork_keywords)
        has_basic = any(indicator in message_lower for indicator in basic_indicators)
        
        if has_artwork and has_basic:
            return 'basic_local_artifact'
        elif has_artwork:
            return 'basic_local_artifact'
        
        # Museum info queries
        museum_keywords = ["hours", "tickets", "price", "open", "restroom", "cafe", "activities"]
        if any(keyword in message_lower for keyword in museum_keywords):
            return 'basic_museum_info'
        
        # Default to general art knowledge
        return 'general_art_knowledge'

    def _detect_artifact(self, message_text):
        """Detect which artwork the user is asking about"""
        # Use the enhanced RAG's extraction method
        return self.enhanced_rag.extract_artwork_from_message(message_text)

    def _get_relevant_local_context(self, message_text, detected_artifact=None):
        """Get relevant content from local database"""
        if not self.db_path or not os.path.exists(self.db_path):
            return "No local database available."
        
        try:
            import sqlite3
            
            # Try to find relevant artifact using enhanced search
            artwork_entity = detected_artifact or self._detect_artifact(message_text)
            
            if artwork_entity:
                logger.info(f"Searching database for: {artwork_entity}")

            result = self.enhanced_rag.enhanced_artwork_search(message_text, artwork_entity)
            
            if result:
                title, artist, date_painted, description, curator_words, location, media, size = result
                
                return f"""MUSEUM ARTIFACT INFORMATION:
                    Title: {title or 'Unknown Title'}
                    Artist: {artist or 'Unknown Artist'}
                    Date: {date_painted or 'Unknown Date'}
                    Location in Museum: {location or 'Unknown Location'}
                    Media: {media or 'Unknown Media'}
                    Size: {size or 'Unknown Size'}
                    Description: {description or 'No description available'}
                    Curator's Notes: {curator_words or 'No curator notes available'}"""
            
            # Fallback: general collection info
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT title, artist, description FROM artifacts LIMIT 3")
            all_artifacts = cursor.fetchall()
            conn.close()
            
            if all_artifacts:
                context_parts = ["MUSEUM COLLECTION OVERVIEW:"]
                for title, artist, description in all_artifacts:
                    title = title or "Unknown Title"
                    artist = artist or "Unknown Artist" 
                    description = (description or "No description available")[:100]
                    context_parts.append(f"- {title} by {artist}: {description}...")
                
                return "\n".join(context_parts)
            
            return "Museum collection information unavailable."
                
        except Exception as e:
            logger.error(f"Database context error: {e}")
            return "Local database context unavailable due to error."

    def _build_enhanced_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build comprehensive prompt with all available context"""
        prompt_parts = []
        
        # Add museum collection context
        try:
            local_db = context.get('local_database') if context else None
            if local_db and isinstance(local_db, str) and local_db.strip():
                prompt_parts.append("MUSEUM COLLECTION CONTEXT:")
                prompt_parts.append(local_db)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Local database context error: {e}")
        
        # Add CV detection as BACKGROUND context (not forcing focus)
        try:
            if context.get('cv_detected') and context.get('detected_artifact'):
                detected_artwork = context.get('detected_artifact')
                prompt_parts.append("VISUAL CONTEXT:")
                prompt_parts.append(f"The user is currently viewing: {detected_artwork}")
                prompt_parts.append("(Use this information naturally if relevant to their question)")
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"CV context error: {e}")
        
        # Add user preferences
        try:
            user_context = context.get('user_context') if context else None
            if user_context and isinstance(user_context, str) and user_context.strip():
                prompt_parts.append("USER PREFERENCES:")
                prompt_parts.append(user_context)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"User context error: {e}")
        
        # Add the actual user query
        if query and isinstance(query, str):
            prompt_parts.append("USER QUESTION:")
            prompt_parts.append(query)
            prompt_parts.append("")
        
        return "\n".join(prompt_parts) if prompt_parts else f"USER QUESTION: {query}"

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
            return "locate_artwork"
        elif any(word in message_lower for word in ["analyze", "compare", "meaning"]):
            return "advanced_analysis"
        elif any(word in message_lower for word in ["van gogh", "lady jane", "traquair"]):
            return "artifact_info"
        else:
            return "general_query"

    def _extract_entities(self, message_text):
        """Simple entity extraction for memory tracking"""
        entities = []
        message_lower = message_text.lower()
        
        # Detect artists
        artists = {
            "van gogh": "Van Gogh",
            "delaroche": "Delaroche", 
            "traquair": "Traquair",
            "van den berg": "van den Berg",  
            "scharff": "Scharff",            
            "rusák": "Rusák" 
        }
        
        for key, name in artists.items():
            if key in message_lower:
                entities.append({"entity": "artist", "value": name})
        
        # Detect artworks
        artwork = self._detect_artifact(message_text)
        if artwork:
            entities.append({"entity": "artwork", "value": artwork})
        
        return entities

    def get_user_insights(self, user_id):
        """Get insights about user for personalization"""
        return self.memory.get_memory_summary(user_id)
    
    def _find_database(self):
        """Find museum database"""
        possible_paths = [
            'museum.db',
            os.path.join(os.path.dirname(__file__), 'muznc1', 'museum.db'),
            os.path.join(os.path.dirname(__file__), 'museum.db'),
            'muznc1/museum.db',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Database found: {path}")
                return path
        logger.warning("No database found")
        return None

# For backward compatibility (if other files import MuseumAIAssistant)
MuseumAIAssistant = HybridMuseumAI

# Test the simplified system
async def test_simplified_system():
    """Test the simplified museum AI system"""
    print("Testing Simplified Museum AI System")
    print("=" * 50)
    
    assistant = HybridMuseumAI()
    user_id = "test_user"
    
    test_queries = [
        "Hello!",
        "What are your hours?",
        "Tell me about Van Gogh",
        "Where is Lady Jane Grey?",
        "Analyze the symbolism in the Victory painting",
        "Compare Van Gogh's technique to other artists"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{query}'")
        try:
            response = await assistant.process_message(query, user_id)
            print(f"   Response: {response[:100]}...")
            
            # Check memory
            context = assistant.memory.get_conversation_context(user_id)
            print(f"   Memory: {len(context.get('recent_messages', []))} messages, "
                  f"Interests: {context.get('interests', [])}")
                  
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\nSimplified system test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_simplified_system())
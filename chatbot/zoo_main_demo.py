# zoo_main.py - Adapted for Ocean Park Zoo chatbot WITH HARDCODED RESPONSES
from enhanced_rag_openai import EnhancedRAGWithOpenAI  
from memory_tracker import HybridMemoryTracker
import asyncio
import os
import logging
from typing import Dict, Any, Optional
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridZooAI:
    """
    HYBRID: Local database + OpenAI Enhanced RAG for ZOO
    - local database: customized for zoo animals
    - OpenAI: Advanced queries with local context
    - HARDCODED RESPONSES: Fixed answers for specific questions
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
        
        # ============================================================
        # HARDCODED RESPONSES - Add your fixed Q&A pairs here
        # ============================================================
        self.hardcoded_responses = self._initialize_hardcoded_responses()
        
        logger.info("Hybrid Zoo AI ready with hardcoded responses!")
    
    def _initialize_hardcoded_responses(self):
        """
        Initialize hardcoded question-answer pairs.
        Each entry has:
        - 'patterns': list of regex patterns or keywords to match
        - 'response': exact response to return
        - 'match_type': 'all' (all patterns must match) or 'any' (any pattern matches)
        """
        return [
            {
                'name': 'red_pandas_look_like_cats',
                'patterns': [
                    r'red panda.*look.*cat',
                    r'red panda.*why.*cat',
                    r'red panda.*like cat',
                    r'what animal.*red panda',
                    r'why.*red panda.*cat'
                ],
                'match_type': 'any',
                'response': "They might look a bit like cats because of their furry faces, big eyes, and fluffy tails, but they're actually in their own special family called Ailuridae—not related to cats at all! Instead, they're more like cousins to raccoons and weasels."
            },
            {
                'name': 'where_to_find_pandas',
                'patterns': [
                    r'where.*find.*panda',
                    r'where.*panda.*ocean park',
                    r'panda.*location',
                    r'find.*panda.*here',
                    r'remind.*panda.*where'
                ],
                'match_type': 'any',
                'response': "yes! red pandas are cute creatures like regular pandas! You can find them at the Amazing Asian Animals 1 Waterfront section of Ocean Park. Look for four adorable pandas named Jia Jia, An An, Ying Ying, and Le Le—they're our suuperstars! Don't forget to take a photo with them!"
            }
            # Add more hardcoded responses here:
            # {
            #     'name': 'example_question',
            #     'patterns': [r'keyword1', r'keyword2'],
            #     'match_type': 'any',
            #     'response': "Your exact response here"
            # }
        ]
    
    def _check_hardcoded_responses(self, message_text: str) -> Optional[str]:
        """
        Check if the message matches any hardcoded response patterns.
        Returns the hardcoded response if matched, None otherwise.
        """
        message_lower = message_text.lower().strip()
        
        for response_config in self.hardcoded_responses:
            patterns = response_config['patterns']
            match_type = response_config.get('match_type', 'any')
            
            matches = []
            for pattern in patterns:
                # Try regex match
                if re.search(pattern, message_lower):
                    matches.append(True)
                else:
                    matches.append(False)
            
            # Check if conditions are met
            if match_type == 'all' and all(matches):
                logger.info(f"Hardcoded response matched: {response_config['name']}")
                return response_config['response']
            elif match_type == 'any' and any(matches):
                logger.info(f"Hardcoded response matched: {response_config['name']}")
                return response_config['response']
        
        return None
    
    async def process_message(self, message_text, user_id="default_user", cv_detected_animal=None):
        try:
            logger.info(f"Processing: '{message_text[:50]}...' for user: {user_id}")
            
            # ============================================================
            # CHECK HARDCODED RESPONSES FIRST
            # ============================================================
            hardcoded_response = self._check_hardcoded_responses(message_text)
            if hardcoded_response:
                logger.info("Returning hardcoded response")
                
                # Still track the interaction for memory
                self.memory.track_interaction(
                    user_id=user_id,
                    message=message_text,
                    response=hardcoded_response,
                    intent=self._extract_intent(message_text),
                    entities=self._extract_entities(message_text),
                    source="hardcoded"
                )
                
                return hardcoded_response
            
            # ============================================================
            # CONTINUE WITH NORMAL RAG PROCESSING
            # ============================================================
            message_lower = message_text.lower()

            # Detect animal being asked about
            if cv_detected_animal:
                logger.info(f"CV detection active: {cv_detected_animal}")
                detected_animal = cv_detected_animal
            else:
                detected_animal = self._detect_animal(message_text)

            conversation_context = self.memory.get_conversation_context(user_id)
            personalized_context = self.memory.get_personalized_context(user_id)
            
            query_type = self._determine_query_type(message_text, conversation_context)

            full_context = {
                'local_database': self._get_relevant_local_context(message_text, detected_animal),  
                'user_context': personalized_context,
                'detected_animal': detected_animal,
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
                source="zoo_rag_openai"
            )

            logger.info(f"Response generated: '{response[:50]}...'")             
            return response
                
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return "I'm having some technical difficulties, but I'm still here to help with your animal questions!"

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

    def _get_relevant_local_context(self, message_text, detected_animal=None):
        """Get relevant content from zoo database"""
        if not self.db_path or not os.path.exists(self.db_path):
            return "No local database available."
        
        try:
            import sqlite3
            
            animal_name = detected_animal or self._detect_animal(message_text)
            
            if animal_name:
                logger.info(f"Searching database for: {animal_name}")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Search by common name
                cursor.execute('''
                    SELECT common_name, scientific_name, distribution_range, habitat,
                           characteristics, body_measurements, diet, behavior,
                           location_at_park, stories, conservation_status, threats, conservation_actions
                    FROM animals
                    WHERE LOWER(common_name) LIKE ?
                ''', (f'%{animal_name}%',))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
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

    def _extract_entities(self, message_text):
        """Simple entity extraction for memory tracking"""
        entities = []
        
        # Detect animals
        animal = self._detect_animal(message_text)
        if animal:
            entities.append({"entity": "animal", "value": animal})
        
        return entities

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
    
    # ============================================================
    # UTILITY METHODS FOR MANAGING HARDCODED RESPONSES
    # ============================================================
    
    def add_hardcoded_response(self, name: str, patterns: list, response: str, match_type: str = 'any'):
        """
        Dynamically add a new hardcoded response.
        
        Args:
            name: Identifier for this response
            patterns: List of regex patterns to match
            response: Exact response to return
            match_type: 'any' or 'all' - how patterns should match
        """
        self.hardcoded_responses.append({
            'name': name,
            'patterns': patterns,
            'match_type': match_type,
            'response': response
        })
        logger.info(f"Added hardcoded response: {name}")
    
    def list_hardcoded_responses(self):
        """List all hardcoded responses"""
        return [
            {
                'name': r['name'],
                'patterns': r['patterns'],
                'response_preview': r['response'][:100] + '...' if len(r['response']) > 100 else r['response']
            }
            for r in self.hardcoded_responses
        ]

# For backward compatibility
ZooAIAssistant = HybridZooAI

# Test the zoo system
async def test_zoo_system():
    """Test the zoo AI system with hardcoded responses"""
    print("Testing Zoo AI System with Hardcoded Responses")
    print("=" * 70)
    
    # Create database first
    import sys
    sys.path.append(os.path.dirname(__file__))
    from create_zoo_database import create_zoo_database
    db_path = create_zoo_database()
    
    assistant = HybridZooAI(db_path=db_path)
    user_id = "test_user"
    
    # List hardcoded responses
    print("\nConfigured Hardcoded Responses:")
    for i, response in enumerate(assistant.list_hardcoded_responses(), 1):
        print(f"{i}. {response['name']}")
        print(f"   Patterns: {response['patterns'][:2]}...")
        print(f"   Response: {response['response_preview']}")
    
    print("\n" + "=" * 70)
    print("Testing Queries:")
    print("=" * 70)
    
    test_queries = [
        # Test hardcoded responses
        "What animals are those red pandas, why do they look like cats?",
        "they remind me of pandas! Where can i find some pandas here in the Ocean Park",
        
        # Test normal queries
        "Hello!",
        "Tell me about capybaras",
        "What do red pandas eat?",
        "How are penguins affected by climate change?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        try:
            response = await assistant.process_message(query, user_id)
            print(f"   Response: {response}")
            print(f"   Length: {len(response)} chars")
                  
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "=" * 70)
    print("Zoo system test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_zoo_system())
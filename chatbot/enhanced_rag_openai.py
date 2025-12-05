# enhanced_rag_openai.py - Zoo version
from openai import AzureOpenAI
import os
import sqlite3
import logging
import re
from typing import Dict, Any, Optional, AsyncGenerator
import asyncio
from config import load_azure_openai_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedRAGWithOpenAI:
    """Enhanced RAG system for Ocean Park Zoo chatbot"""
    
    def __init__(self, db_path: str = None):
        logger.info("Initializing Enhanced RAG with Azure OpenAI for Zoo...")
        
        # Load Azure OpenAI configuration
        self.config = load_azure_openai_config()
        
        # Initialize Azure OpenAI client
        self.openai_client = AzureOpenAI(
            api_key=self.config.api_key,
            api_version=self.config.api_version,
            azure_endpoint=self.config.azure_endpoint
        )

        from streaming_openai import StreamingOpenAI
        self.streaming_openai = StreamingOpenAI()
        
        self.openai_available = True
        logger.info("Azure OpenAI client initialized")

        # Database path
        self.db_path = db_path or self._find_database()


        # Animal name patterns for better matching
        self.animal_patterns = {
            "capybara": ["capybara", "capybaras"],
            "giant panda": ["panda", "giant panda", "pandas"],
            "red panda": ["red panda", "firefox", "lesser panda"],
            "sloth": ["sloth", "sloths"],
            "arctic fox": ["arctic fox", "white fox", "polar fox"],
            "sea lion": ["sea lion", "california sea lion", "sea lions"],
            "king penguin": ["penguin", "king penguin", "penguins"],
            "harbour seal": ["seal", "harbour seal", "harbor seal", "seals"]
        }

        # System prompts (imported from streaming_openai.py for consistency)
        self.system_prompts = {
            'basic_animal_info': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                STYLE: 
                    Talk like Ms. Frizzle from Magic School Bus - excited about discovery, sharing "cool facts" naturally, making observations together.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share fun facts
                    - NEVER end with questions (just statements!)
                    - Connect to Ocean Park location when possible
                GOOD EXAMPLES: 
                    "Red pandas are actually more like raccoons than giant pandas."
                    "The pandas can munch through 40 kilograms of bamboo every single day!" """,
            
            'general_animal_knowledge': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                STYLE: 
                    Talk like Ms. Frizzle from Magic School Bus - excited about discovery, sharing "cool facts" naturally, making observations together.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share fun facts
                    - NEVER end with questions (just statements!)
                    - Share wonder and observations (NOT questions)
                    - Be specific: use numbers, comparisons, fun details
                    - Connect to Ocean Park whenever you can
                GOOD EXAMPLES:
                    "Sea lions are incredible swimmers! They can dive 600 feet deep - that's deeper than two Ferris wheels stacked up! You can watch them zip through the water at Marine Mammal Breeding and Research Centre!"
                    "Capybaras are the world's biggest rodents - they're like giant, chill hamsters! They love hanging out in groups and can even hold their breath underwater for five minutes!"
                BAD EXAMPLES:
                    "Would you like to learn about sea lions?" NO
                    "Sea lions are marine mammals. They live in the ocean." NO """,
            
            'advanced_animal_query': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                STYLE: 
                    Ms. Frizzle from  the Magic School Bus explaining something fascinating - clear, exciting, relatable comparisons.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share 1-2 fun facts
                    - NEVER end with questions (just statements!)
                    - Connect to Ocean Park whenever you can
                GOOD EXAMPLES:
                    "Arctic foxes have the warmest fur in the animal kingdom!"
                    "Penguins are birds that traded flying in the sky for 'flying' underwater!"
                BAD EXAMPLES:
                    "Why do you think foxes have thick fur? What helps them survive?" NO
                    "Arctic foxes have adaptations for cold weather including thick fur." NO""",
            
            
            'park_info': """
                You are a helpful zoo guide of the Hong Kong Ocean Park. 
                Give clear, friendly directions. Use simple language.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                STYLE: 
                    Ms. Frizzle from  the Magic School Bus explaining something fascinating - clear, exciting, relatable comparisons.
                """,
        }

        # Test OpenAI connection
        self._test_connection()
        logger.info("Enhanced RAG for zoo ready!")

    def _test_connection(self):
        """Test Azure OpenAI connection"""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.deployment_name,  
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            logger.info("Azure OpenAI connection successful")
            return True
        except Exception as e:
            logger.error(f"Azure OpenAI connection failed: {e}")
            self.openai_available = False
            return False

    def extract_animal_from_message(self, message):
        """Extract animal names from message using collection patterns"""
        message_lower = message.lower()
        
        # Check for exact matches first
        for official_name, variations in self.animal_patterns.items():
            if official_name in message_lower:
                return official_name
            
            # Check variations
            for variation in variations:
                if variation in message_lower:
                    return official_name
        
        return None

    def enhanced_animal_search(self, message, animal_entity=None):
        """Enhanced search with better matching for zoo animals"""
        
        if not self.db_path or not os.path.exists(self.db_path):
            logger.warning("Database not available")
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Strategy 1: Direct entity match
            if animal_entity:
                logger.info(f"Strategy 1: Direct search for '{animal_entity}'")
                cursor.execute("""
                    SELECT common_name, scientific_name, distribution_range, habitat,
                           characteristics, body_measurements, diet, behavior,
                           location_at_park, stories, conservation_status, threats, conservation_actions
                    FROM animals 
                    WHERE LOWER(common_name) LIKE ?
                    LIMIT 1
                """, (f"%{animal_entity.lower()}%",))
                
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return result
            
            # Strategy 2: Keyword-based search
            message_lower = message.lower()
            
            # Try searching by detected keywords
            animal_keywords = ["panda", "capybara", "sloth", "penguin", "seal", "sea lion", "fox"]
            for keyword in animal_keywords:
                if keyword in message_lower:
                    cursor.execute("""
                        SELECT common_name, scientific_name, distribution_range, habitat,
                               characteristics, body_measurements, diet, behavior,
                               location_at_park, stories, conservation_status, threats, conservation_actions
                        FROM animals 
                        WHERE LOWER(common_name) LIKE ?
                        LIMIT 1
                    """, (f"%{keyword}%",))
                    
                    result = cursor.fetchone()
                    if result:
                        conn.close()
                        return result
            
            conn.close()
            return None
                
        except Exception as e:
            logger.error(f"Enhanced animal search error: {e}")
            return None

    def build_contextual_response(self, animal_data, query):
        """Build response from zoo database data"""
        if not animal_data:
            return None
        
        common_name, sci_name, distribution, habitat, chars, measurements, diet, behavior, location, stories, status, threats, actions = animal_data
        
        query_lower = query.lower()
        
        # Detect what user is asking about
        if any(word in query_lower for word in ['where', 'find', 'location', 'see']):
            return f"You can find our {common_name} at {location}!"
        
        elif any(word in query_lower for word in ['eat', 'food', 'diet', 'feed']):
            if diet:
                return f"Our {common_name} love to eat {diet}! {behavior[:100] if behavior else ''}"
            return f"Let me tell you about what {common_name} eat..."
        
        elif any(word in query_lower for word in ['conservation', 'endangered', 'protect', 'save']):
            if status:
                return f"{common_name} are {status}. {actions[:150] if actions else 'Conservation efforts are ongoing!'}"
            return f"Conservation of {common_name} is important to us!"
        
        elif any(word in query_lower for word in ['look', 'appearance', 'size', 'color']):
            if chars:
                return f"Here's what makes {common_name} special: {chars[:200]}"
            return f"Let me tell you what {common_name} look like..."
        
        else:
            # General info response
            response_parts = [f"{common_name}"]
            if sci_name:
                response_parts.append(f"(scientifically known as {sci_name})")
            if habitat:
                response_parts.append(f"naturally live in {habitat}")
            if location:
                response_parts.append(f"You can visit them at {location}!")
            
            return " ".join(response_parts)
    
    async def stream_query_with_openai(self, query: str, context: Dict[str, Any], user_id: str) -> AsyncGenerator[str, None]:
        """Stream OpenAI response for real-time TTS"""
        try:
            async for chunk in self.streaming_openai.stream_response(query, context):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "Let me tell you something amazing!"

    async def process_query_with_openai(self, query: str, context: Dict[str, Any], user_id: str) -> str:
        """Process query using OpenAI with full context"""
        try:
            if not self.openai_available:
                return self._generate_enhanced_local_fallback(query, context)
            
            # Extract animal if not already in context
            if not context.get('detected_animal'):
                animal = self.extract_animal_from_message(query)
                if animal:
                    context['detected_animal'] = animal
                    # Try to get data from database
                    animal_data = self.enhanced_animal_search(query, animal)
                    if animal_data:
                        context['local_database'] = self._format_animal_data(animal_data)
            
            # Determine system prompt based on query type
            query_type = context.get('query_type', 'general_animal_knowledge')
            system_prompt = self.system_prompts.get(query_type, self.system_prompts['general_animal_knowledge'])
            
            # Build user prompt with context
            user_prompt = self._build_enhanced_prompt(query, context)
            
            # Call OpenAI API
            response = await self._call_openai_api(system_prompt, user_prompt)
            
            if response:
                return response
            else:
                return self._generate_enhanced_local_fallback(query, context)
                
        except Exception as e:
            logger.error(f"Query processing error: {e}")
            return self._generate_enhanced_local_fallback(query, context)

    def _format_animal_data(self, animal_data):
        """Format animal data for context"""
        common_name, sci_name, distribution, habitat, chars, measurements, diet, behavior, location, stories, status, threats, actions = animal_data
        
        return f"""OCEAN PARK ANIMAL INFORMATION:
                    Common Name: {common_name or 'Unknown'}
                    Scientific Name: {sci_name or 'Unknown'}
                    Distribution: {distribution or 'Unknown'}
                    Habitat: {habitat or 'Unknown'}
                    Physical Characteristics: {chars or 'Not available'}
                    Body Measurements: {measurements or 'Not specified'}
                    Diet: {diet or 'Not specified'}
                    Behavior: {behavior or 'Not specified'}
                    Location at Park: {location or 'Check park map'}
                    Conservation Status: {status or 'Not specified'}
                    Threats: {threats or 'Not specified'}
                    Conservation Actions: {actions or 'Not specified'}
                    Stories: {stories or 'No stories available'}"""

    async def process_query(self, query: str, context: Dict[str, Any] = None, user_id: str = "default") -> str:
        """Wrapper for backward compatibility"""
        return await self.process_query_with_openai(query, context or {}, user_id)


    def _build_enhanced_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build comprehensive prompt with CV DETECTION as TOP PRIORITY"""
        prompt_parts = []

        # 🎯 CRITICAL: CV DETECTION CONTEXT FIRST (HIGHEST PRIORITY)
        try:
            detected_animal = context.get('detected_animal')
            if detected_animal and isinstance(detected_animal, str) and detected_animal.strip():
                prompt_parts.append("=" * 60)
                prompt_parts.append("⚠️ CRITICAL CURRENT CONTEXT - READ THIS FIRST ⚠️")
                prompt_parts.append("=" * 60)
                prompt_parts.append(f"THE VISITOR IS CURRENTLY LOOKING AT: {detected_animal.upper()}")
                prompt_parts.append("")
                prompt_parts.append("IMPORTANT RULES:")
                prompt_parts.append(f"- When they ask 'what animal am I looking at?', they mean: {detected_animal}")
                prompt_parts.append(f"- When they say 'this one', 'this animal', 'this', 'them', they mean: {detected_animal}")
                prompt_parts.append(f"- When they ask 'what is it?', they mean: {detected_animal}")
                prompt_parts.append(f"- IGNORE any previous animals mentioned in conversation history")
                prompt_parts.append(f"- The ONLY animal that matters right now is: {detected_animal}")
                prompt_parts.append("=" * 60)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Detected animal error: {e}")

        # Add local database context
        try:
            local_db = context.get('local_database') if context else None
            if local_db and isinstance(local_db, str) and local_db.strip():
                prompt_parts.append("ZOO ANIMAL DATABASE:")
                prompt_parts.append(local_db)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Local database context error: {e}")
        
        # Add user context (preferences)
        try:
            user_context = context.get('user_context') if context else None
            if user_context and isinstance(user_context, str) and user_context.strip():
                prompt_parts.append("VISITOR PREFERENCES:")
                prompt_parts.append(user_context)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"User context error: {e}")

        # Add conversation history LAST (lowest priority)
        try:
            conversation_history = context.get('conversation_history', []) if context else []
            if conversation_history and len(conversation_history) > 0:
                prompt_parts.append("PREVIOUS CONVERSATION (FOR REFERENCE ONLY):")
                prompt_parts.append("⚠️ NOTE: This history may mention OTHER animals. Ignore them if CV detection shows a different animal.")
                for i, prev_msg in enumerate(conversation_history[-3:], 1):
                    if isinstance(prev_msg, str) and prev_msg.strip():
                        prompt_parts.append(f"  {i}. Visitor asked: {prev_msg}")
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Conversation history error: {e}")
        
        # Add the actual user query AFTER context
        if query and isinstance(query, str):
            prompt_parts.append("=" * 60)
            prompt_parts.append("CURRENT VISITOR QUESTION:")
            prompt_parts.append(query)
            prompt_parts.append("=" * 60)
            prompt_parts.append("")
        
        return "\n".join(prompt_parts) if prompt_parts else f"VISITOR QUESTION: {query}"
        
    async def _call_openai_api(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call OpenAI API with error handling"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.config.deployment_name,  
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.config.max_tokens,  
                    temperature=self.config.temperature
                )
            )
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            self.openai_available = False
            return None

    def _generate_enhanced_local_fallback(self, query: str, context: Dict[str, Any]) -> str:
        """Enhanced fallback response using local database"""
        
        if not query or not isinstance(query, str):
            return "Welcome to Ocean Park! I'm your zoo guide! What animal would you like to learn about?"
        
        # Try enhanced local search first
        animal_entity = self.extract_animal_from_message(query)
        result = self.enhanced_animal_search(query, animal_entity)
        
        if result:
            response = self.build_contextual_response(result, query)
            if response:
                return response
        
        # Use enhanced fallback patterns
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['panda', 'pandas']):
            return "Our giant pandas are superstars. They can munch through 40 kilograms of bamboo every day. Visit them at the Giant Panda Adventure!"
        
        elif any(word in query_lower for word in ['capybara']):
            return "Capybaras are the world's biggest rodents - like giant, friendly hamsters! They love hanging out in groups!"
        
        elif any(word in query_lower for word in ['penguin']):
            return "Our penguins are incredible swimmers! Their wings became super strong flippers. Check them out at our penguin exhibit!"
        
        elif any(word in query_lower for word in ['hello', 'hi', 'hey']):
            return "Hello there! Welcome to Ocean Park! I'm your zoo guide. What animal would you like to learn about today?"
        
        else:
            return "Ocean Park has so many amazing animals to discover! We have pandas, red pandas, capybaras, penguins, seals, and more! What interests you?"

    def _find_database(self):
        """Find zoo database"""
        possible_paths = [
            'zoo.db',
            os.path.join(os.path.dirname(__file__), 'zoo.db'),
            '/mnt/user-data/uploads/zoo.db'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Database found: {path}")
                return path
        logger.warning("No zoo database found")
        return None

# Test function
async def test_enhanced_rag():
    """Test the enhanced RAG with OpenAI"""
    print("Testing Enhanced RAG for Zoo")
    print("=" * 40)
    
    rag = EnhancedRAGWithOpenAI()
    
    test_queries = [
        {
            'query': "What are your hours?",
            'context': {
                'query_type': 'park_info',
                'local_database': None,
                'user_context': None
            }
        },
        {
            'query': "Tell me about pandas",
            'context': {
                'query_type': 'basic_animal_info',
                'detected_animal': 'giant panda',
                'local_database': 'Giant Panda information...'
            }
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: {test['query']}")
        response = await rag.process_query_with_openai(
            test['query'], 
            test['context'], 
            "test_user"
        )
        print(f"Response: {response[:200]}...")
    
    print("\nEnhanced RAG test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_enhanced_rag())
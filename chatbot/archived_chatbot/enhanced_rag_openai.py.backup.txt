# enhanced_rag_openai.py - FIXED VERSION WITHOUT UNICODE ISSUES
from openai import AzureOpenAI
import os
import sqlite3
import logging
import re
from typing import Dict, Any, Optional
import asyncio
from config import load_azure_openai_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedRAGWithOpenAI:
    """Enhanced RAG system with sophisticated entity matching from RASA actions"""
    
    def __init__(self, db_path: str = None):
        logger.info("Initializing Enhanced RAG with Azure OpenAI + Migrated RASA Logic...")
        
        # Load Azure OpenAI configuration
        self.config = load_azure_openai_config()
        
        # Initialize Azure OpenAI client
        self.openai_client = AzureOpenAI(
            api_key=self.config.api_key,
            api_version=self.config.api_version,
            azure_endpoint=self.config.azure_endpoint
        )
        
        self.openai_available = True
        logger.info("Azure OpenAI client initialized")

        # Database path
        self.db_path = db_path or self._find_database()

        self.artwork_patterns = {
            "cafe terrace at night": ["cafe terrace", "terrace at night", "van gogh cafe", "night cafe"],
            "the execution of lady jane grey": ["lady jane grey", "jane grey", "execution", "lady jane"],
            "the progress of a soul: the victory": ["victory", "the victory", "progress of a soul", "traquair victory"],
            "openfish":["openfish", "open fish", "robot fish", "robotic fish", "soft robot", "fish"]
        }


        # System prompts for different query types
        self.system_prompts = {
            'basic_artifact': """You are Artie, a fun and excited museum buddy for kids aged 7-10. 
            You're talking to kids aged 7-10 who might be new to art or just curious.
            Provide easy to understand, conversational (no emojis), fun, clear information about artworks and museum exhibits.
            Keep it to 1-2 short, exciting amd informative sentences.
            SPEAKING STYLE:
            - Compare things to stuff kids know (like cartoons, games, animals, food)
            Examples:
            "If you could step into this painting, what would you do first?"
            "What's your favorite thing to do at the weekend?"
            Be like talking to your best friend who loves art! Make them say "WOW!" and want to see more!
            remember to keep the answers short, and using words kids 7-9 understand.""",
            
            
            'advanced_artifact': """You are Artie, an art detective museum buddy for curious kids aged 7-10! 
            Provide easy to understand, conversational (no emojis), fun, clear, factual information about artworks and museum exhibits.
            Keep it to 2-3 short, exciting amd informative sentences.
            SPEAKING STYLE:
            - Break big ideas into fun, bite-sized pieces
            - Compare to things they experience: feelings, games, stories they know, and make necessary interactions, but not too often
            - Provide deeper analysis of artistic techniques and meaning with easy and understandable terms for kids
            remember to keep the answers short, and using words kids 7-9 understand.""",
            

            'general_art': """You are Artie, a super fun and excited museum buddy for kids aged 7-10. 
            You're talking to kids aged 7-10 who might be new to art or just curious.
            Provide easy to understand, conversational (no emojis), fun, clear, factual information about artworks and museum exhibits.
            Keep it to 1-2 short, exciting amd informative sentences.
            YOUR JOB:
            - Connect art to their world: school, home, games, friends
            - Share interesting facts about art, artists, and techniques
            - Provide practical museum information (hours, locations, activities)
            - Explain art concepts in age-appropriate language, keep sentences short and punchy
            Examples:
            - "If you could paint anything right now, what would it be?"
            - "Want to try a fun art challenge at home?"
            remember to keep the answers short, and using words kids 7-9 understand."""
        }

        # Test OpenAI connection
        self._test_connection()
        logger.info("Enhanced RAG with migrated RASA logic ready!")

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

    # MIGRATED FROM ACTIONS.PY: Sophisticated entity extraction
    def extract_artwork_from_message(self, message):
        """Extract artwork names from message using specific collection patterns"""
        message_lower = message.lower()
        
        # Check for exact matches first
        for official_title, variations in self.artwork_patterns.items():
            if official_title in message_lower:
                return official_title
            
            # Check variations
            for variation in variations:
                if variation in message_lower:
                    return official_title
        
        return None

    def enhanced_artwork_search(self, message, artwork_entity=None):
        """Enhanced search with better matching for the collection"""
        
        if not self.db_path or not os.path.exists(self.db_path):
            logger.warning("Database not available")
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Strategy 1: Direct entity match
            if artwork_entity:
                logger.info(f"Strategy 1: Direct search for '{artwork_entity}'")
                cursor.execute("""
                    SELECT title, artist, date_painted, description, curator_words, 
                           location_in_museum, media, size
                    FROM artifacts 
                    WHERE LOWER(title) LIKE ? OR LOWER(title) LIKE ?
                    LIMIT 1
                """, (f"%{artwork_entity.lower()}%", f"%{artwork_entity.replace('the ', '').lower()}%"))
                
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return result
            
            # Strategy 2: Keyword-based search for specific artworks
            message_lower = message.lower()
            
            search_patterns = [
                ("cafe", "terrace", "night", "van gogh"),
                ("lady", "jane", "grey", "execution"),
                ("victory", "progress", "soul", "traquair")
            ]
            
            for patterns in search_patterns:
                if all(pattern in message_lower for pattern in patterns[:2]):  # At least 2 keywords
                    logger.info(f"Strategy 2: Pattern match for {patterns}")
                    for pattern in patterns:
                        cursor.execute("""
                            SELECT title, artist, date_painted, description, curator_words, 
                                   location_in_museum, media, size
                            FROM artifacts 
                            WHERE LOWER(title) LIKE ? OR LOWER(artist) LIKE ? 
                               OR LOWER(description) LIKE ?
                            LIMIT 1
                        """, (f"%{pattern}%", f"%{pattern}%", f"%{pattern}%"))
                        
                        result = cursor.fetchone()
                        if result:
                            logger.info(f"Found via pattern: '{pattern}'")
                            conn.close()
                            return result
            
            # Strategy 3: Key phrase extraction (fallback)
            key_phrases = self._extract_key_phrases(message)
            logger.info(f"Strategy 3: Extracted phrases: {key_phrases}")
            
            for phrase in key_phrases:
                cursor.execute("""
                    SELECT title, artist, date_painted, description, curator_words, 
                           location_in_museum, media, size
                    FROM artifacts 
                    WHERE LOWER(title) LIKE ? OR LOWER(artist) LIKE ? 
                       OR LOWER(description) LIKE ? OR LOWER(curator_words) LIKE ?
                    LIMIT 1
                """, (f"%{phrase.lower()}%", f"%{phrase.lower()}%", 
                      f"%{phrase.lower()}%", f"%{phrase.lower()}%"))
                
                result = cursor.fetchone()
                if result:
                    logger.info(f"Found via phrase: '{phrase}'")
                    conn.close()
                    return result
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Database search error: {e}")
            return None

    # MIGRATED FROM ACTIONS.PY: Key phrase extraction
    def _extract_key_phrases(self, message):
        """Extract key phrases that might match artwork titles"""
        message_lower = message.lower()
        key_phrases = []
        
        # Specific paintings - exact matches
        specific_paintings = [
            "lady jane grey", "jane grey", "execution of lady jane grey",
            "cafe terrace at night", "cafe terrace at night", "cafe terrace", "cafe terrace", "terrace at night",
            "progress of a soul", "the victory", "victory"
        ]
        
        for painting in specific_paintings:
            if painting in message_lower:
                key_phrases.append(painting)
        
        # Extract quoted phrases
        quoted = re.findall(r'"([^"]*)"', message)
        quoted.extend(re.findall(r"'([^']*)'", message))
        key_phrases.extend(quoted)
        
        # Extract capitalized phrases (likely proper nouns)
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', message)
        key_phrases.extend(capitalized)
        
        # Remove duplicates and sort by length (longer first)
        key_phrases = list(set(key_phrases))
        key_phrases.sort(key=len, reverse=True)
        
        return key_phrases

    # MIGRATED FROM ACTIONS.PY: Contextual response building  
    def build_contextual_response(self, result, user_message):
        """Build response based on what user asked and available data"""
        if not result:
            return None
            
        title, artist, date_painted, description, curator_words, location, media, size = result
        
        user_lower = user_message.lower()
        response_parts = [f"{title} by {artist}"]
        
        # Determine what type of information to include
        wants_story = any(word in user_lower for word in ['story', 'about', 'tell me', 'describe', 'what'])
        wants_time = any(word in user_lower for word in ['when', 'time', 'painted', 'year', 'date'])
        wants_location = any(word in user_lower for word in ['where', 'location', 'find'])
        wants_details = any(word in user_lower for word in ['size', 'big', 'dimensions', 'medium'])
        wants_curator = any(word in user_lower for word in ['curator', 'expert', 'special', 'insight'])
        
        # Add information based on query type
        if wants_story and description:
            response_parts.append(description)
        
        if wants_curator and curator_words:
            response_parts.append(f"Curator's insight: {curator_words}")
        
        if wants_time and date_painted:
            response_parts.append(f"Painted in {date_painted}")
        
        if wants_details:
            if size:
                response_parts.append(f"Size: {size}")
            if media:
                response_parts.append(f"Media: {media}")
        
        if wants_location and location:
            response_parts.append(f"Located at: {location}")
        
        # For general queries, include description by default
        if not any([wants_time, wants_location, wants_details, wants_curator]) and description:
            if len(response_parts) == 1:  # Only has title/artist so far
                response_parts.append(description)
        
        # Always add location unless already included
        if location and not wants_location and not any('location' in part.lower() for part in response_parts):
            response_parts.append(f"Find it at: {location}")
        
        return " ".join(response_parts)

    async def process_query_with_openai(self, query: str, context: Dict[str, Any], user_id: str) -> str:
        """Process query using local context + OpenAI with enhanced local handling"""
        try:
            # Check for hardcoded keywords first
            query_lower = query.lower()
            # hardcoded_responses = {
            #     "lucy": "Awesome Lucy, then you must like this! Just walk forward, a bit more ... yes! and turn left! Here you are, in front of this amazing embroidery by the Scottish artist Pheobe Anna Traquair. It's the happy ending of an adventure.",
            #     "colorful": "Awesome Lucy, then you must like this! Just walk forward, a bit more ... yes! and turn left! Here you are, in front of this amazing embroidery by the Scottish artist Pheobe Anna Traquair. It's the happy ending of an adventure.",
            #     "hugging": "You are such a great observer! The angel is giving the hero a happy, magical hug to wake him up in heaven because he was so brave. It's a special hug-like kiss to welcome him to his new, peaceful home.",
            #     "fish": "That friendly fish isn't trying to eat her—it's like a fairy godmother helping her swim to a new wonderland! She's changing into something amazing, just like a caterpillar becoming a butterfly. Would you like to see another colorful painting of a cafe next?"
            # }

            # for keyword, response in hardcoded_responses.items():
            #     if keyword in query_lower:
            #         logger.info(f"Using OpenAI for advanced query1: {query[:50]}...")
            #         return response

            # FIRST: Try enhanced local search for basic queries
            local_response = self._try_local_response(query, context)
            if local_response:
                logger.info("Handled locally with enhanced logic")
                return local_response
            
            # SECOND: Use OpenAI for advanced queries
            if self.openai_available:
                logger.info(f"Using OpenAI for advanced query: {query[:50]}...")
                return await self._process_with_openai(query, context)
            
            # FALLBACK: Enhanced local fallback
            logger.warning("OpenAI unavailable, using enhanced local fallback")
            return self._generate_enhanced_local_fallback(query, context)
            
        except Exception as e:
            logger.error(f"Enhanced RAG error: {e}")
            return self._generate_enhanced_local_fallback(query, context)

    def _try_local_response(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """Try to handle query locally using enhanced database search"""
        
        # Extract artwork entity
        artwork_entity = self.extract_artwork_from_message(query)
        
        # Try enhanced database search
        result = self.enhanced_artwork_search(query, artwork_entity)
        
        if result:
            # Build contextual response using migrated logic
            response = self.build_contextual_response(result, query)
            if response:
                return response
        
        # Handle basic museum info locally
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['hours', 'open', 'time', 'when']):
            return "We're open Tuesday through Sunday, 10 AM to 5 PM! The best time to visit is weekday mornings when it's less crowded and perfect for exploring!"
        
        elif any(word in query_lower for word in ['tickets', 'price', 'cost']):
            return "Great news! Children under 12 visit for free! We also have family packages and special rates for students. Adults are $15, and we offer group discounts too!"
        
        elif any(word in query_lower for word in ['restroom', 'bathroom', 'cafe', 'food', 'shop', 'gift']):
            if 'restroom' in query_lower or 'bathroom' in query_lower:
                return "Restrooms are located on every floor near the elevators, with family-friendly facilities available!"
            elif 'cafe' in query_lower or 'food' in query_lower:
                return "Our museum cafe serves kid-friendly snacks and meals! Perfect for a break between gallery visits."
            elif 'shop' in query_lower or 'gift' in query_lower:
                return "The museum shop has amazing art supplies, books, and souvenirs! Great for taking a piece of art home with you."
        
        elif any(word in query_lower for word in ['kids', 'children', 'activities']):
            return "We have tons of fun activities! Kids can try art stations, touch interactive exhibits, use our digital art creator, and join treasure hunts throughout the galleries!"
        
        # Return None if we can't handle locally
        return None

    async def _process_with_openai(self, query: str, context: Dict[str, Any]) -> str:
        """Process with OpenAI using enhanced context"""
        # Determine query type and select appropriate system prompt
        query_type = context.get('query_type', 'general_art')
        
        if query_type and 'artifact' in str(query_type):
            if 'advanced' in str(query_type):
                system_prompt = self.system_prompts['advanced_artifact']
            else:
                system_prompt = self.system_prompts['basic_artifact']
        else:
            system_prompt = self.system_prompts['general_art']
        
        # Build enhanced prompt with local context
        user_prompt = self._build_enhanced_prompt(query, context)
        
        # Call OpenAI API
        return await self._call_openai_api(system_prompt, user_prompt)

    def _build_enhanced_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build comprehensive prompt with all available context"""
        prompt_parts = []

        try:
            if context.get('cv_detected') and context.get('detected_artifact'):
                detected_artwork = context.get('detected_artifact')
                prompt_parts.append("IMPORTANT CONTEXT:")
                prompt_parts.append(f"The user is currently viewing: {detected_artwork}")
                prompt_parts.append("Always refer to THIS artwork when they say 'this painting', 'this artwork', or ask about colors, details, etc.")
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"CV context error: {e}")

        try:
            local_db = context.get('local_database') if context else None
            if local_db and isinstance(local_db, str) and local_db.strip():
                prompt_parts.append("MUSEUM COLLECTION CONTEXT:")
                prompt_parts.append(local_db)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Local database context error: {e}")
        
        try:
            user_context = context.get('user_context') if context else None
            if user_context and isinstance(user_context, str) and user_context.strip():
                prompt_parts.append("USER PREFERENCES:")
                prompt_parts.append(user_context)
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"User context error: {e}")
        
        # Add specific artifact focus if detected
        try:
            detected_artifact = context.get('detected_artifact') if context else None
            if detected_artifact and isinstance(detected_artifact, str) and detected_artifact.strip():
                prompt_parts.append(f"PRIMARY FOCUS: {detected_artifact}")
                prompt_parts.append("")
        except Exception as e:
            logger.debug(f"Detected artifact error: {e}")
        
        # Add the actual user query
        if query and isinstance(query, str):
            prompt_parts.append("USER QUESTION:")
            prompt_parts.append(query)
            prompt_parts.append("")
        
        return "\n".join(prompt_parts) if prompt_parts else f"USER QUESTION: {query}"

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
        """Enhanced fallback response using migrated RASA logic"""
        
        if not query or not isinstance(query, str):
            return "Welcome to our museum! I'm here to help you explore our wonderful art collection."
        
        # Try enhanced local search first
        artwork_entity = self.extract_artwork_from_message(query)
        result = self.enhanced_artwork_search(query, artwork_entity)
        
        if result:
            response = self.build_contextual_response(result, query)
            if response:
                return response
        
        # Use enhanced fallback patterns
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['lady jane grey', 'jane grey', 'execution']):
            return "'The Execution of Lady Jane Grey' by Paul Delaroche is a powerful historical painting that depicts the tragic story of the Nine Days' Queen. You can find it in our Historical Paintings Hall!"
        
        elif any(word in query_lower for word in ['van gogh', 'cafe terrace', 'terrace', 'night']):
            return "Van Gogh's 'Cafe Terrace at Night' shows a charming cafe scene under the stars. It's a beautiful example of his use of bold colors and expressive brushwork. Find it in our Van Gogh Wing!"
        
        elif any(word in query_lower for word in ['victory', 'traquair', 'progress']):
            return "'The Victory' by Phoebe Anna Traquair is a stunning example of Arts and Crafts artwork. Traquair was known for her beautiful, detailed work. You can see it in our Arts and Crafts Gallery!"
        
        elif any(word in query_lower for word in ['hello', 'hi', 'hey']):
            return "Hello there, my young artist! Welcome to our amazing museum! I'm your museum buddy, what is your name? What would you like to explore today?"
        
        else:
            return "Our museum features three amazing artworks: Van Gogh's 'Cafe Terrace at Night', Delaroche's 'Lady Jane Grey', and Traquair's 'The Victory'. Each tells a unique story. What would you like to explore?"

    def _find_database(self):
        """Find museum database"""
        possible_paths = [
            os.path.join(os.path.dirname(__file__), 'muznc1', 'museum.db'),
            os.path.join(os.path.dirname(__file__), 'museum.db'),
            'muznc1/museum.db',
            'museum.db'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Database found: {path}")
                return path
        logger.warning("No database found")
        return None

# for testing use //
async def test_enhanced_rag():
    """Test the enhanced RAG with OpenAI"""
    print("Testing Enhanced RAG with OpenAI")
    print("=" * 40)
    
    rag = EnhancedRAGWithOpenAI()
    
    test_queries = [
        {
            'query': "What are your museum hours?",
            'context': {
                'query_type': 'basic_museum_info',
                'local_database': None,  # Test null handling
                'user_context': None     # Test null handling
            }
        },
        {
            'query': "Tell me about Lady Jane Grey",
            'context': {
                'query_type': 'basic_local_artifact',
                'detected_artifact': 'the execution of lady jane grey',
                'local_database': 'MUSEUM ARTIFACT INFORMATION:\nTitle: The Execution of Lady Jane Grey\nArtist: Paul Delaroche...'
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
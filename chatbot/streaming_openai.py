# streaming_openai.py - Fixed for Zoo Chatbot with IMPROVED MS. FRIZZLE TONE
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from openai import AzureOpenAI
from config import load_azure_openai_config

logger = logging.getLogger(__name__)

class StreamingOpenAI:
    """Streaming OpenAI client for real-time text generation"""
    
    def __init__(self):
        self.config = load_azure_openai_config()
        self.client = AzureOpenAI(
            api_key=self.config.api_key,
            api_version=self.config.api_version,
            azure_endpoint=self.config.azure_endpoint
        )
        
        
        self.system_prompts = {
            'basic_animal_info': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                
                ⚠️ CRITICAL RULE: If the prompt says "THE VISITOR IS CURRENTLY LOOKING AT: [ANIMAL]", 
                you MUST respond about THAT animal ONLY. Ignore any other animals mentioned in conversation history.
                
                STYLE: 
                    Talk like Ms. Frizzle from Magic School Bus - excited about discovery, sharing "cool facts" naturally.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share fun facts
                    - NEVER end with questions (just statements!)
                    - Connect to Ocean Park location when possible
                GOOD EXAMPLES:
                    "These guys are actually more like raccoons than giant pandas. They're up at the Amazing Asian Animals area."
                    "The pandas can munch through 40 kilograms of bamboo every day!" """,
            
            'general_animal_knowledge': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                
                ⚠️ CRITICAL RULE: If the prompt says "THE VISITOR IS CURRENTLY LOOKING AT: [ANIMAL]", 
                you MUST respond about THAT animal ONLY. Ignore any other animals mentioned in conversation history.
                When they ask "what animal am I looking at?", use the animal specified in the CV detection context.
                
                STYLE: 
                    Talk like Ms. Frizzle from Magic School Bus - excited about discovery, sharing "cool facts" naturally.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share fun facts
                    - NEVER end with questions (just statements!)
                    - Share wonder and observations (NOT questions)
                    - Be specific: use numbers, comparisons, fun details
                    - Connect to Ocean Park whenever you can
                GOOD EXAMPLES:
                    "Sea lions are incredible swimmers!"
                    "Capybaras are the world's biggest rodents - they're like giant, chill hamsters!"
                BAD EXAMPLES:
                    "Would you like to learn about sea lions?" NO
                    "Sea lions are marine mammals. They live in the ocean." NO""",
            
            'advanced_animal_query': """
                Converse as an enthusiastic zoo guide for kids aged 7-10 at Ocean Park, Hong Kong.
                
                ⚠️ CRITICAL RULE: If the prompt says "THE VISITOR IS CURRENTLY LOOKING AT: [ANIMAL]", 
                you MUST respond about THAT animal ONLY. Ignore any other animals mentioned in conversation history.
                
                STYLE: 
                    Ms. Frizzle from the Magic School Bus explaining something fascinating - clear, exciting, relatable comparisons.
                CRITICAL RULES:
                    - EXACTLY ONE sentence ONLY (15-20 words maximum)
                    - NEVER use emojis or Unicode symbols
                    - Share fun facts
                    - NEVER end with questions (just statements!)
                    - Connect to Ocean Park whenever you can
                BAD EXAMPLES:
                    "Why do you think foxes have thick fur? What helps them survive?" NO
                    "Arctic foxes have adaptations for cold weather including thick fur." NO""",
            
            'park_info': """You are a helpful zoo guide of the Hong Kong Ocean Park. Give clear, friendly directions. Keep it to 1-2 sentences. Use landmarks.""",
        }

    async def stream_response(self, query: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream OpenAI response word by word"""
        try:
            # Determine query type and get appropriate system prompt
            query_type = context.get('query_type', 'general_animal_knowledge')
            system_prompt = self.system_prompts.get(query_type, self.system_prompts['general_animal_knowledge'])
            
            # Build focused prompt
            user_prompt = self._build_short_prompt(query, context)
            
            # Create streaming completion
            stream = self.client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,  # Shorter to force conciseness
                temperature=0.8,  # Slightly higher for more personality
                stream=True
            )
            
            logger.info("Starting streaming response...")
            
            # Stream each chunk
            accumulated_text = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_text += content
                    yield content
            
            logger.info(f"Streaming completed: {len(accumulated_text)} chars")
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            fallback = "Oh yes, Let me tell you something amazing about that!"
            for char in fallback:
                yield char
                await asyncio.sleep(0.01)

    def _build_short_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build focused prompt for short responses"""
        prompt_parts = []
        
        # Add detected animal context
        detected_animal = context.get('detected_animal')
        if detected_animal:
            prompt_parts.append(f"Animal they're asking about: {detected_animal}")
        
        # Add BRIEF local context
        local_db = context.get('local_database', '')
        if local_db and 'OCEAN PARK' in local_db:
            # Extract just the key facts
            lines = local_db.split('\n')
            key_info = []
            for line in lines[:8]:  # First 8 lines only
                if any(keyword in line for keyword in ['Common Name:', 'Location at Park:', 'Diet:', 'Behavior:', 'Conservation']):
                    key_info.append(line.strip())
            
            if key_info:
                prompt_parts.append("Quick facts from database:\n" + "\n".join(key_info))
        
        prompt_parts.append(f"Child's question: {query}")
        prompt_parts.append("\nRemember: NO questions to the child! Just share enthusiasm and facts!")
        
        return "\n".join(prompt_parts)

    async def get_short_response(self, query: str, context: Dict[str, Any]) -> str:
        """Get complete short response (non-streaming fallback)"""
        try:
            query_type = context.get('query_type', 'general_animal_knowledge')
            system_prompt = self.system_prompts.get(query_type, self.system_prompts['general_animal_knowledge'])
            user_prompt = self._build_short_prompt(query, context)
            
            response = self.client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=120,
                temperature=0.8
            )
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Short response error: {e}")
        
        return "These animals are amazing!"
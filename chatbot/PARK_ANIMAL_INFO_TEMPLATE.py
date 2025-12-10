# TEMPLATE: Paste your scraped Ocean Park data here
# Then copy this content into park_knowledge.py PARK_ANIMAL_INFO section

PARK_ANIMAL_INFO = {
    
    # ===== EXAMPLE: Arctic Fox Den =====
    # Copy data from Ocean Park website following this format:
    
    'arctic_fox_den': {
        'name': 'Arctic Fox Den',
        'location': 'Polar Adventure | Summit',
        'zone': 'Summit',
        'description': '''Learn the secrets of this elusive tundra predator in surviving one of the most unforgiving environments on earth! Discover how their short limbs and long, bushy tails help adapt them to the extreme cold, as well as see how their fur changes colour from dark brown in the summer to white in the winter. The exhibit highlights the impact of humans on their habitat while covering key behaviours of this species.''',
        'animals': ['Arctic Fox'],
        'highlights': [
            'Arctic foxes change fur color from dark brown in summer to white in winter',
            'Short limbs and long bushy tails help adapt to extreme cold',
            'Exhibit highlights human impact on habitat',
            'Arctic foxes have the warmest fur in the animal kingdom'
        ],
        'what_near_by': [
            'Arctic Blast (Thrill Rides)',
            'Polar Adventure',
            'Summit attractions'
        ],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/arctic-fox-den'
    },
    
    # ===== ADD MORE ATTRACTIONS BELOW =====
    # Paste content from image 2 (attraction detail page) following this format:
    
    # 'dive_into_local_diversity': {
    #     'name': 'Dive Into Local Diversity',
    #     'location': 'Amazing Asian Animals | Waterfront',  # FROM IMAGE: shows "Amazing Asian Animals | Waterfront"
    #     'zone': 'Waterfront',
    #     'description': '''[PASTE DESCRIPTION FROM WEBSITE]''',
    #     'animals': ['[LIST ANIMALS SHOWN]'],
    #     'highlights': [
    #         '[PASTE KEY POINTS FROM DESCRIPTION]',
    #         '[EACH AS SEPARATE ITEM]'
    #     ],
    #     'what_near_by': [
    #         '[PASTE FROM "What\'s Near By" SECTION]'
    #     ],
    #     'url': 'https://www.oceanpark.com.hk/en/...'
    # },
    
    # ===== INSTRUCTIONS FOR MANUAL DATA ENTRY =====
    # 1. Click on each attraction from the Ocean Park website
    # 2. Copy the title → 'name'
    # 3. Copy location text (e.g., "Polar Adventure | Summit") → 'location' and 'zone'
    # 4. Copy main description paragraph → 'description'
    # 5. Extract key facts → 'highlights' (one per line)
    # 6. Copy "What's Near By" items → 'what_near_by'
    # 7. Copy page URL → 'url'
    # 8. Create a key by lowercasing name and replacing spaces with underscores
    #    Example: "Arctic Fox Den" → 'arctic_fox_den'
    
}

# ===== AFTER FILLING OUT =====
# 1. Copy everything above
# 2. Open park_knowledge.py
# 3. Find PARK_ANIMAL_INFO = { section
# 4. Replace with your new data
# 5. Run: python update_zoo_database.py
# 6. Deploy to Docker

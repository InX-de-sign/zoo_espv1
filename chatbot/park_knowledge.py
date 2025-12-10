# park_knowledge.py - Ocean Park static knowledge base
"""
Static knowledge base for Ocean Park information.

TWO MAIN SECTIONS:
1. PARK_INFO - General park information (galleries, zones, transport, etc.)
2. PARK_ANIMAL_INFO - Detailed animal/attraction data from Ocean Park website

Update this file when park information changes.
To scrape latest data from Ocean Park website, run: python scrape_oceanpark.py
"""

# ============================================================================
# SECTION 1: DETAILED ANIMAL/ATTRACTION INFO (from Ocean Park website)
# ============================================================================

PARK_ANIMAL_INFO = {
    # Example entry based on Ocean Park website
    # Add more attractions below following this format
    
    'arctic_fox_den': {
        'name': 'Arctic Fox Den',
        'location': 'Polar Adventure | Summit',
        'zone': 'Summit',
        'description': '''Learn the secrets of this elusive tundra predator in surviving one of the most unforgiving environments on earth! Discover how their short limbs and long, bushy tails help adapt them to the extreme cold, as well as see how their fur changes colour from dark brown in the summer to white in the winter. The exhibit highlights the impact of humans on their habitat while covering key behaviours of this species.''',
        'animals': ['Arctic Fox'],
        'highlights': [
            'Arctic foxes change fur color from dark brown in summer to white in winter',
            'Short limbs and long bushy tails help them survive extreme cold',
            'Arctic foxes have the warmest fur in the animal kingdom',
            'Learn about human impact on their habitat'
        ],
        'what_near_by': ['Arctic Blast (Thrill Rides)', 'Polar Adventure exhibits'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/arctic-fox-den'
    },
    
    'croco_land': {
        'name': 'China Construction Bank (Asia) presents Croco Land',
        'location': 'Ocean Park Main Entrance | Waterfront',
        'zone': 'Waterfront',
        'description': '''The exotic crocodile found in Lin Fa Tei, Pat Heung last year has become an official resident of Ocean Park! The crocodile, Passion, whose name was selected by public voting, is now living at Croco Land, presented by China Construction Bank (Asia), located at the main entrance of the Park and opens to the public with free entry. Estimated to be four years old, this awe-inspiring exotic crocodile is growing gradually, measuring 1.97m in length and weighing 38.5kg now. DNA test result confirmed that Passion is a hybrid Siamese-Cuban crocodile. Passion has become our latest Ocean Park animal ambassador with a mission to raise awareness about the impacts to the local ecosystem brought by non-native species. Welcome this latest member of the Park and learn about the importance of biodiversity!''',
        'animals': ['Siamese-Cuban Crocodile (Passion)'],
        'highlights': [
            'Passion is a hybrid Siamese-Cuban crocodile rescued from Pat Heung',
            'Named by public voting',
            '1.97m in length and weighing 38.5kg (still growing)',
            'Free entry exhibit at main entrance',
            'Raises awareness about non-native species impacts'
        ],
        'what_near_by': 'None',
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/croco-land'
    },
    
    'dive_into_local_diversity': {
        'name': 'Dive Into Local Diversity',
        'location': 'Amazing Asian Animals | Waterfront',
        'zone': 'Waterfront',
        'description': '''Human life is closely intertwined with rivers. How much do you know about the diversity of riverine ecosystems? Visit the "Dive into Local Diversity" to learn about local freshwater habitats, including native freshwater species, riparian living organisms and commonly found invasive alien species in local freshwater habitats. Understand the values and threats of Hong Kong's freshwater ecosystem and appreciate the different local freshwater habitats and their biodiversity. Let's work together to conserve freshwater ecosystems!''',
        'animals': ['Native freshwater species', 'Riparian organisms', 'Local aquatic life'],
        'highlights': [
            'Learn about Hong Kong freshwater ecosystems',
            'Understand native vs invasive alien species',
            'Discover riparian living organisms',
            'Conservation education about local biodiversity'
        ],
        'what_near_by': ['Eco-Herbal Trail', 'Club Panda', 'Panda Kingdom Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/dive-into-local-diversity'
    },
    
    'dolphin_explorations': {
        'name': 'Dolphin Explorations',
        'location': 'Marine World | Summit',
        'zone': 'Summit',
        'description': '''As the biggest and best nature playground in Hong Kong, Ocean Park is launching a whole new experience, Dolphin Explorations, to provide our visitors with more opportunities to close encounter dolphins and sea lions, get to know their daily lives and conservation tips, become Ocean Guardians, not only our animal caretakers will share anecdotes from their daily husbandry and care, we will invite you to show your determination to protect the seas and your new animal friends. Dolphin Explorations provides a layered experience, which includes: Whiskers Village Ocean Guardians and Resting Area.''',
        'animals': ['Indo-Pacific Bottlenose Dolphin', 'California Sea Lion'],
        'highlights': [
            'Close encounter with dolphins and sea lions',
            'Learn about daily care and conservation',
            'Become an Ocean Guardian',
            'Interactive educational experience',
            'Includes Whiskers Village Ocean Guardians area'
        ],
        'what_near_by': ['Sea Jelly Spectacular', 'Café Ocean', 'Ocean Paradise'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/dolphin-explorations'
    },
    
    'emerald_trail': {
        'name': 'Emerald Trail',
        'location': 'Amazing Asian Animals | Waterfront',
        'zone': 'Waterfront',
        'description': '''Stroll through a verdant garden filled with the trills of birdsong, while admiring flowers in bloom. The picturesque Emerald Trail is the perfect place to relax and take in nature with your family while delighting in the sunlight shimmering across the pond or staring at the dappled leaves high above.''',
        'animals': ['Birds', 'Garden wildlife'],
        'highlights': [
            'Verdant garden with birdsong',
            'Flowers in bloom',
            'Perfect place to relax with family',
            'Scenic pond and nature views'
        ],
        'what_near_by': ['Panda Village', 'Club Panda', 'Panda Kingdom Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/emerald-trail'
    },
    
    'expedition_trail': {
        'name': 'Expedition Trail',
        'location': 'Rainforest | Summit',
        'zone': 'Summit',
        'description': '''Take the Expedition Trail into the heart of the Rainforest, where strange and beautiful creatures roam. Hear the calls of world's largest and smallest toucans, the toco toucan and spot the brilliantly coloured poison frogs. Discover one of the world's largest freshwater fish, the arapaima, and the wide-eyed kinkajou. More of the world's most astounding animals lurk beneath the leaves, like the pygmy marmoset, whose incredible adaptations to their habitats make them interesting to learn about and crucial to protect.''',
        'animals': ['Toco Toucan', 'Poison Dart Frog', 'Arapaima', 'Kinkajou', 'Pygmy Marmoset'],
        'highlights': [
            'World\'s largest and smallest toucans',
            'Brilliantly colored poison frogs',
            'Arapaima - one of world\'s largest freshwater fish',
            'Wide-eyed kinkajou',
            'Pygmy marmoset with incredible adaptations'
        ],
        'what_near_by': ['The Rapids', 'Rainforest Gift Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/expedition-trail'
    },
    
    'gator_marsh': {
        'name': 'Gator Marsh',
        'location': 'Amazing Asian Animals | Waterfront',
        'zone': 'Waterfront',
        'description': '''At the Gator Marsh, visitors get to see and learn about the critically endangered Chinese alligator. While this precious species has developed a mythical status among the locals living alongside the Yangtze River, habitat loss and illegal hunting for medicinal use both threaten the alligators' survival. Discover how these 'earth dragons', who can survive up to 50 years in the wild, need a helping hand in keeping their world and future generations safe!''',
        'animals': ['Chinese Alligator'],
        'highlights': [
            'Critically endangered Chinese alligator',
            'Known as "earth dragons" in Chinese mythology',
            'Can survive up to 50 years in the wild',
            'Learn about habitat loss and conservation',
            'Illegal hunting threatens their survival'
        ],
        'what_near_by': ['Eco-Herbal Trail', 'Club Panda', 'Panda Kingdom Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/gator-marsh'
    },
    
    'giant_panda_adventure': {
        'name': 'Giant Panda Adventure',
        'location': 'Amazing Asian Animals | Waterfront',
        'zone': 'Waterfront',
        'description': '''Join us on the "Giant Panda Adventure" to discover the fascinating side of these national treasures! In addition to meeting the beloved Hong Kong's homegrown giant panda twins, you can also visit the equally charming giant pandas, "Ying Ying" and "Le Le". Along the way, you'll see the adorable red pandas from the temperate forests of Mainland China. Smaller but just as cuddly, red pandas also reside here as ambassadors for their increasingly threatened habitat, along with Chinese giant salamander, the largest amphibian in the world. Together, they offer a vital lesson not just about their protection, but also the value of all the flora and fauna in their fragile ecosystem.''',
        'animals': ['Giant Panda', 'Red Panda', 'Chinese Giant Salamander'],
        'highlights': [
            'Meet Hong Kong\'s homegrown giant panda twins',
            'Visit Ying Ying and Le Le giant pandas',
            'See adorable red pandas from temperate forests',
            'Chinese giant salamander - largest amphibian in the world',
            'Learn about conservation and fragile ecosystems'
        ],
        'what_near_by': ['Gator Marsh', 'Club Panda', 'Panda Kingdom Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/giant-panda-adventure'
    },
    
    'hong_kong_jockey_club_sichuan_treasures': {
        'name': 'Hong Kong Jockey Club Sichuan Treasures',
        'location': 'Aqua City | Waterfront',
        'zone': 'Waterfront',
        'description': '''Come visit the giant pandas An An and Ke Ke from Sichuan. An An is agile, smart, and active, while Ke Ke is good at climbing, gentle and lovely. They also have lively neighbors - The Sichuan Golden Snub-nosed monkey, Le Le and Qi Qi! With the distinctive blue face and bright orange fur, Le Le and Qi Qi tell a cautionary tale of habitat loss while educating us about the crucial conservation efforts that will help save them.''',
        'animals': ['Giant Panda (An An, Ke Ke)', 'Sichuan Golden Snub-nosed Monkey (Le Le, Qi Qi)'],
        'highlights': [
            'An An - agile, smart, and active giant panda',
            'Ke Ke - good at climbing, gentle giant panda',
            'Le Le and Qi Qi - Golden Snub-nosed monkeys',
            'Distinctive blue face and bright orange fur',
            'Learn about habitat loss and conservation'
        ],
        'what_near_by': ['Old Hong Kong', 'Aqua City Bakery', 'Waterfront Gifts'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/hong-kong-jockey-club-sichuan-treasures'
    },
    
    'little_meerkat_and_giant_tortoise_adventure': {
        'name': 'Little Meerkat and Giant Tortoise Adventure',
        'location': 'Whiskers Harbour | Waterfront',
        'zone': 'Waterfront',
        'description': '''You'll feel like you've stepped into the savanna at our exhibit, the Little Meerkat and Giant Tortoise Adventure! Learn all about Africa's wildlife as you visit our exciting new stars. The adorable, energetic meerkats love to dart about, stand up and look around, while the Aldabra giant tortoises do everything slowly, from walking to eating. Be attention! Our animal friends, meerkats need to get rest at 6pm everyday. If you want to catch a glimpse of them, make sure to visit the exhibit before their rest time. The exhibit also features African tribal-style decorations, as well as interactive games where you can help meerkats pick their food or run races with different African animals! Have fun and use all five of your senses to learn about our newest animal friends, the importance of preserving their habitats, and how to respect nature and be a responsible world citizen.''',
        'animals': ['Meerkat', 'Aldabra Giant Tortoise'],
        'highlights': [
            'Adorable energetic meerkats that stand up and look around',
            'Aldabra giant tortoises do everything slowly',
            'Meerkats rest at 6pm daily - visit before then',
            'African tribal-style decorations',
            'Interactive games to help meerkats pick food',
            'Run races with different African animals'
        ],
        'what_near_by': ['Whiskers Herbal Valley', 'HiPP presents Jungle of Giants', 'Merry-Go-Round'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/little-meerkat-and-giant-tortoise-adventure'
    },
    
    'marine_mammal_breeding_and_research_centre': {
        'name': 'Marine Mammal Breeding and Research Centre',
        'location': 'Marine World | Summit',
        'zone': 'Summit',
        'description': '''Right next to the Veterinary Centre, Marine Mammal Breeding and Research Centre (MMBRC) serves as the animal care headquarters benefiting animals in Ocean Park as well as in the wild. Let our dolphin trainer explain how the dolphins living in Ocean Park help humans to conserve their friends in the wild.''',
        'animals': ['Indo-Pacific Bottlenose Dolphin', 'California Sea Lion'],
        'highlights': [
            'Animal care headquarters for Ocean Park',
            'Dolphin trainer demonstrations',
            'Learn how dolphins help conservation efforts',
            'Dolphin Feeding Demonstration at 1:30pm',
            'Adjacent to Veterinary Centre'
        ],
        'what_near_by': ['Ocean Park Tower', 'Café Ocean', 'Ocean Paradise'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/marine-mammal-breeding-and-research-centre'
    },
    
    'monkey_tree_presents_south_pole_spectacular': {
        'name': 'Monkey Tree presents South Pole Spectacular',
        'location': 'Polar Adventure | Summit',
        'zone': 'Summit',
        'description': '''The Earth's southernmost tip is home to one of its most beloved animals - talkative and communal penguins! Over 90 penguins from three species inhabit the Monkey Tree presents South Pole Spectacular, including king penguins, the world's second largest penguin, dramatic southern rockhopper penguins, one of the world's tiniest penguins and white-bonneted, gentoo penguins, which sport unusual coloured eye markings. See these fascinating birds from stunning angles above and underwater like never before. Remarks: To keep our polar animals comfortable, the Polar Adventure will be kept at relatively low temperatures throughout the year (South Pole Spectacular at 8-10°C, North Pole Encounter at 15-17°C).''',
        'animals': ['King Penguin', 'Southern Rockhopper Penguin', 'Gentoo Penguin'],
        'highlights': [
            'Over 90 penguins from three species',
            'King penguins - world\'s second largest penguin',
            'Southern rockhopper penguins - one of world\'s tiniest',
            'Gentoo penguins with unusual colored eye markings',
            'View from stunning angles above and underwater',
            'Temperature kept at 8-10°C for comfort'
        ],
        'what_near_by': ['Arctic Fox Den', 'Tuxedos Restaurant', 'The Lodge'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/south-pole-spectacular'
    },
    
    'north_pole_encounter': {
        'name': 'North Pole Encounter',
        'location': 'Polar Adventure | Summit',
        'zone': 'Summit',
        'description': '''At 3.6m long and weighing over a tonne, the exhibit's two pacific walruses are as big in personality as they are in size. This area evokes the sounds, smells and sights of walruses and silvery spotted seals' northerly habitat. Guests will be able to view them from above as well as below the ice. Remarks: To keep our polar animals comfortable, the Polar Adventure will be kept at relatively low temperatures throughout the year (South Pole Spectacular at 8-10°C, North Pole Encounter at 15-17°C). Due to renovations, 'North Pole Encounter' will be closed from 5 January 2026 until further notice.''',
        'animals': ['Pacific Walrus', 'Spotted Seal'],
        'highlights': [
            'Two pacific walruses at 3.6m long and over a tonne',
            'View from above and below the ice',
            'Experience northerly habitat sounds, smells, and sights',
            'Temperature kept at 15-17°C',
            'Closed for renovations from 5 January 2026'
        ],
        'what_near_by': ['Arctic Blast', 'Tuxedos Restaurant', 'The Lodge'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/north-pole-encounter'
    },
    
    'pacific_pier': {
        'name': 'Pacific Pier',
        'location': 'Marine World | Summit',
        'zone': 'Summit',
        'description': '''Take a trip down the sunny Californian coast and catch some sun, surf and sand up close. View the rocky coastal habitat of seals and sea lions as they frolic, sunbathe and hunt below the pier in this interactive exhibit complete with simulated waves. You might even get a chance to feed some of these agile creatures personally!''',
        'animals': ['California Sea Lion', 'Harbour Seal'],
        'highlights': [
            'Sunny Californian coast themed exhibit',
            'Rocky coastal habitat simulation',
            'Seals and sea lions frolic and hunt',
            'Interactive exhibit with simulated waves',
            'Chance to feed animals personally'
        ],
        'what_near_by': ['Ferris Wheel', 'The Bayview Restaurant', 'Ocean Paradise'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/pacific-pier'
    },
    
    'panda_village': {
        'name': 'Panda Village',
        'location': 'Amazing Asian Animals | Waterfront',
        'zone': 'Waterfront',
        'description': '''At this idyllic setting, some of the region's most impressive and rare birdlife cheerfully flit between the branches and clever little otters frolic merrily in the water. Catch adorable demonstrations of Asia's smallest otters showing off their hunting prowess!''',
        'animals': ['Asian Small-clawed Otter', 'Various rare birdlife'],
        'highlights': [
            'Idyllic setting with rare Asian birdlife',
            'Clever little otters frolicking in water',
            'Asia\'s smallest otters',
            'Adorable hunting demonstrations',
            'Birds flitting between branches'
        ],
        'what_near_by': ['Dive Into Local Diversity', 'Club Panda', 'Panda Kingdom Shop'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/panda-village'
    },
    
    'sea_jelly_spectacular': {
        'name': 'Sea Jelly Spectacular',
        'location': 'Marine World | Summit',
        'zone': 'Summit',
        'description': '''In a delightful underwater 'garden', over 1,000 sea jellies of all sizes, shapes and colours from around the world float serenely overhead. Designed with the latest technology in lighting, music and multimedia special effects, visitors are encouraged to virtually touch the fluorescent sea jellies via an interactive Shadow Game and play hide-and-seek with them in the Mirror Maze as they discover their way through this mystical enclosure.''',
        'animals': ['Sea Jellies (1,000+)'],
        'highlights': [
            'Over 1,000 sea jellies from around the world',
            'All sizes, shapes and colours',
            'Latest lighting, music and multimedia effects',
            'Interactive Shadow Game to touch jellies',
            'Mirror Maze hide-and-seek experience'
        ],
        'what_near_by': ['Crazy Galleon', 'Café Ocean', 'Ocean Paradise'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/sea-jelly-spectacular'
    },
    
    'shark_mystique': {
        'name': 'Shark Mystique',
        'location': 'Marine World | Summit',
        'zone': 'Summit',
        'description': '''Shatter the myths and fears surrounding the ocean's top predators at Shark Mystique, a unique exhibit showcasing over a hundred sharks and rays! Get 360 degree views of incredible sea life, such as the sawfish with its saw-like rostrum and the zebra shark with leopard-like spots all over its body! As you uncover more fun facts about these beautiful animals, test your newfound knowledge at interactive games and join your favourite celebrities in saying no to shark fin!''',
        'animals': ['Sharks (100+)', 'Rays', 'Sawfish', 'Zebra Shark'],
        'highlights': [
            'Over a hundred sharks and rays',
            '360 degree views of sea life',
            'Sawfish with saw-like rostrum',
            'Zebra shark with leopard-like spots',
            'Interactive games to test knowledge',
            'Say no to shark fin campaign'
        ],
        'what_near_by': ['Sea Jelly Spectacular', 'Café Ocean', 'Ocean Paradise'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/shark-mystique'
    },
    
    'sloth_and_friends_studio': {
        'name': 'Sloth and Friends Studio',
        'location': 'Aqua City | Waterfront',
        'zone': 'Waterfront',
        'description': '''The "Sloth and Friends Studio" animal exhibit, located in Aqua City. This exhibit features two adorable slow-moving sloths, as well as other animals, including macaw, kinkajou, and ball python. During the "Animal Fun Talks", the animal caretaker will demonstrate how to feed the animals and share their interesting living habits. Inside the exhibit, there is an art gallery featuring a series of animal paintings generated by AI. You can also learn about "The IUCN Red List," established by the International Union for Conservation of Nature (IUCN). Using the tablet, you can enter simple commands to create your own animal-themed AI painting and learn more about these species from another perspective. Take action for conservation and enjoy an immersive and educational experience at the "Sloth and Friends Studio" exhibit. Due to renovations, 'Sloth and Friends Studio' will be closed from 13 October 2025 to 15 December 2025.''',
        'animals': ['Two-toed Sloth', 'Macaw', 'Kinkajou', 'Ball Python'],
        'highlights': [
            'Two adorable slow-moving sloths',
            'Animal Fun Talks with feeding demonstrations',
            'AI-generated animal art gallery',
            'Interactive IUCN Red List education',
            'Create your own AI animal paintings',
            'Closed for renovations: 13 Oct - 15 Dec 2025'
        ],
        'what_near_by': ['Sea Life Carousel', 'Neptune\'s Restaurant', 'Sichuan Treasures'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/sloth-and-friends-studio'
    },
    
    'the_grand_aquarium': {
        'name': 'The Grand Aquarium',
        'location': 'Aqua City | Waterfront',
        'zone': 'Waterfront',
        'description': '''The Grand Aquarium brings you and your family on a multisensory journey from the shore to the darkest depths of the ocean. You will have the exciting opportunity to explore the myriad forms of life that call the sea home, from a pool filled with sea cucumbers and starfish, to the spectacular Reef Tunnel, where you can view the profoundly beautiful ecosystem surrounding coral reefs. Expansive windows under the water like the 5.5m aquarium dome and an awe-inspiring 13m wide acrylic viewing panel takes you closer to an eye-opening collection of 5,000 fish from over 400 species!''',
        'animals': ['5,000 fish from 400+ species', 'Sea cucumbers', 'Starfish', 'Reef fish'],
        'highlights': [
            'Multisensory journey from shore to ocean depths',
            '5,000 fish from over 400 species',
            'Spectacular Reef Tunnel',
            '5.5m aquarium dome',
            '13m wide acrylic viewing panel',
            'Touch pool with sea cucumbers and starfish'
        ],
        'what_near_by': ['Hong Kong Jockey Club Sichuan Treasures', 'Neptune\'s Restaurant', 'Deep Sea Traders'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/the-grand-aquarium'
    },
    
    'whiskers_herbal_valley': {
        'name': 'Whiskers Herbal Valley',
        'location': 'Whiskers Harbour | Waterfront',
        'zone': 'Waterfront',
        'description': '''In the establishment of Whiskers Herbal Valley and Eco-Herbal Trail, we are grateful for generous funding from the Chinese Medicine Development Fund and valuable herbs from the Technological and Higher Education Institute of Hong Kong. Both zones aim to cultivate public interest in traditional Chinese medicine and share this piece of cultural heritage with the world.''',
        'animals': ['None'],
        'highlights': [
            'Traditional Chinese medicine education',
            'Valuable herbs display',
            'Cultural heritage experience',
            'Funded by Chinese Medicine Development Fund',
            'Educational about herbal medicine'
        ],
        'what_near_by': ['Little Meerkat and Giant Tortoise Adventure', 'Castle of Redd', 'Explorer R'],
        'url': 'https://www.oceanpark.com.hk/en/experience/attractions/whiskers-herbal-valley'
    },
    
    # ADD MORE ATTRACTIONS HERE
    # Copy the format above and paste data from Ocean Park website
}

# ============================================================================
# SECTION 2: GENERAL PARK INFO (hand-curated for reliability)
# ============================================================================

PARK_INFO = {
    # ============================================================================
    # RESTRUCTURED PARK ACTIVITIES - 5 CATEGORIES (Based on Ocean Park Website)
    # ============================================================================
    # Categories: Animals, Rides, Family Attractions, Programmes & Journey Experiences, In-Park Transportation
    
    "activities": {
        # CATEGORY 1: ANIMALS
        # Note: Detailed animal info is in PARK_ANIMAL_INFO section above
        "Animals": {
            "description": "Ocean Park houses over 400 species of animals across 12 galleries",
            "total_galleries": 12,
            "attractions": [
                {
                    "name": "Arctic Fox Den",
                    "location": "Polar Adventure | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Croco Land",
                    "location": "Ocean Park Main Entrance | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Free entry"]
                },
                {
                    "name": "Dive Into Local Diversity",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Dolphin Explorations",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Emerald Trail",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Expedition Trail",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Gator Marsh",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Giant Panda Adventure",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Hong Kong Jockey Club Sichuan Treasures",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Little Meerkat and Giant Tortoise Adventure",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Marine Mammal Breeding and Research Centre",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Monkey Tree presents South Pole Spectacular",
                    "location": "Polar Adventure | Summit",
                    "zone": "Summit",
                    "special_notes": ["Temperature: 8-10°C"]
                },
                {
                    "name": "North Pole Encounter",
                    "location": "Polar Adventure | Summit",
                    "zone": "Summit",
                    "special_notes": ["Temperature: 15-17°C", "Closed from 5 January 2026"]
                },
                {
                    "name": "Pacific Pier",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Panda Village",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Sea Jelly Spectacular",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Shark Mystique",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": []
                },
                {
                    "name": "Sloth and Friends Studio",
                    "location": "Aqua City | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Closed 13 Oct - 15 Dec 2025"]
                },
                {
                    "name": "The Grand Aquarium",
                    "location": "Aqua City | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Whiskers Herbal Valley",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                }
            ]
        },
        
        # CATEGORY 2: RIDES (Thrill Rides + Wet Rides)
        "Rides": {
            "description": "Exciting thrill rides and water attractions",
            "subcategories": ["Thrill Rides", "Wet Rides"],
            "attractions": [
                {
                    "name": "Arctic Blast",
                    "location": "Polar Adventure | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 100cm (39\")", "4 or above"]
                },
                {
                    "name": "Crazy Galleon",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 122cm (48\")"]
                },
                {
                    "name": "Flying Swing",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": [
                        "General Seat: 125cm (49\")",
                        "Children Seat: within 122cm (48\") < 125cm (49\")",
                        "General Seat: 8 or above",
                        "Children Seat: 6 or above"
                    ]
                },
                {
                    "name": "Hair Raiser",
                    "location": "Thrill Mountain | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 140cm (55\")"]
                },
                {
                    "name": "Rev Booster",
                    "location": "Thrill Mountain | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 130cm (51\")"]
                },
                {
                    "name": "The Flash",
                    "location": "Thrill Mountain | Summit",
                    "zone": "Summit",
                    "special_notes": [
                        "Between 137cm (54\") and 195cm (77\")",
                        "12 or above"
                    ]
                },
                {
                    "name": "The Rapids",
                    "location": "Rainforest | Summit",
                    "zone": "Summit",
                    "special_notes": ["Wet Ride", "Min. height: 120cm (47\")"]
                },
                {
                    "name": "Whirly Bird",
                    "location": "Thrill Mountain | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 122cm (48\")"]
                },
                {
                    "name": "Wild Twister",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": [
                        "Between 137cm (54\") and 195cm (77\")"
                    ]
                }
            ]
        },
        
        # CATEGORY 3: FAMILY ATTRACTIONS
        "Family Attractions": {
            "description": "Fun attractions for the whole family",
            "attractions": [
                {
                    "name": "Arctic Blast",
                    "location": "Polar Adventure | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 100cm (39\")", "4 or above"]
                },
                {
                    "name": "Balloons Up-Up-And-Away",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Min. height: 91cm (36\")", "1 or above", "May remain in wheelchair"]
                },
                {
                    "name": "Bumper Blaster",
                    "location": "Thrill Mountain | Summit",
                    "zone": "Summit",
                    "special_notes": [
                        "Single Rider/Driver: 145cm (57\")",
                        "Children: 120cm (47\")",
                        "Single Rider/Driver: 12 or above",
                        "Children: 8 or above"
                    ]
                },
                {
                    "name": "Castle of Redd",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Eco-Herbal Trail",
                    "location": "Amazing Asian Animals | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Explorer R",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Ferris Wheel",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 152cm (60\") (See Remarks)", "May remain in wheelchair"]
                },
                {
                    "name": "HiPP presents Jungle of Giants",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Little Meerkat and Giant Tortoise Adventure",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Old Hong Kong",
                    "location": "Aqua City | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": []
                },
                {
                    "name": "Merry-Go-Round",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Min. height: 107cm (42\")", "Max. weight: Below 77kg (170lb)"]
                },
                {
                    "name": "Ocean Park Tower",
                    "location": "Marine World | Summit",
                    "zone": "Summit",
                    "special_notes": ["Min. height: 122cm (48\")"]
                },
                {
                    "name": "Sea Life Carousel",
                    "location": "Aqua City | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Min. height: 107cm (42\")", "Max. weight: Below 125kg (275lb)", "May remain in wheelchair"]
                },
                {
                    "name": "Toto the Loco",
                    "location": "Whiskers Harbour | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["Min. height: 92cm", "1 or above"]
                }
            ]
        },
        
        # CATEGORY 4: PROGRAMMES & JOURNEY EXPERIENCES
        "Programmes & Journey Experiences": {
            "description": "Interactive educational programmes and immersive journey experiences",
            "attractions": [
                {
                    "name": "Ocean Park Academy",
                    "location": "Various locations",
                    "zone": "Waterfront/Summit",
                    "special_notes": ["Educational programmes", "Booking required"]
                },
                {
                    "name": "Animal Encounters",
                    "location": "Various animal galleries",
                    "zone": "Waterfront/Summit",
                    "special_notes": ["Interactive experiences", "Subject to availability"]
                },
                {
                    "name": "Behind-the-Scenes Tours",
                    "location": "Various locations",
                    "zone": "Waterfront/Summit",
                    "special_notes": ["Advance booking required"]
                }
            ]
        },
        
        # CATEGORY 5: IN-PARK TRANSPORTATION
        "In-Park Transportation": {
            "description": "Transportation connecting Waterfront and Summit zones",
            "attractions": [
                {
                    "name": "Cable Car (The Summit)",
                    "location": "Summit Cable Car Station | Summit",
                    "zone": "Summit",
                    "special_notes": ["May remain in wheelchair", "Connects Summit to Waterfront"]
                },
                {
                    "name": "Cable Car (The Waterfront)",
                    "location": "Waterfront Cable Car Station | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["May remain in wheelchair", "Connects Waterfront to Summit"]
                },
                {
                    "name": "Ocean Express (The Summit)",
                    "location": "Ocean Express Summit Station | Summit",
                    "zone": "Summit",
                    "special_notes": ["May remain in wheelchair", "Underground funicular railway"]
                },
                {
                    "name": "Ocean Express (The Waterfront)",
                    "location": "Ocean Express Waterfront Station | Waterfront",
                    "zone": "Waterfront",
                    "special_notes": ["May remain in wheelchair", "Underground funicular railway"]
                }
            ]
        }
    },
    
    "general_info": {
        "opening_hours": {
            "regular": "10:00 AM - 6:00 PM",
            "peak_season": "10:00 AM - 7:00 PM",
            "note": "Hours may vary during special events and holidays"
        },
        "location": {
            "address": "Ocean Park Road, Aberdeen, Hong Kong",
            "transport": [
                "MTR: Ocean Park Station (South Island Line)",
                "Bus: 629 from Central/Admiralty",
                "Citybus: 6X, 70, 75, 90, 97, 590"
            ]
        },
        "zones": {
            "Waterfront": [
                "Grand Aquarium",
                "Giant Panda Adventure", 
                "Marine Mammal Breeding Centre",
                "Whiskers Harbour (kids area)"
            ],
            "Summit": [
                "Polar Adventure",
                "Rainforest",
                "Amazing Asian Animals",
                "Thrill Mountain (rides)"
            ]
        },
        "transport_between_zones": [
            "Ocean Express (underground funicular railway)",
            "Cable Car (scenic aerial view)",
            "Both connect Waterfront to Summit"
        ]
    },
    
    "directions": {
        "from_entrance_to": {
            "giant_panda": "Take Ocean Express or Cable Car to Waterfront zone, then follow signs to Giant Panda Adventure",
            "aquarium": "Located at Waterfront zone near the entrance, 5-minute walk from main gate",
            "sea_lions": "Waterfront zone, next to the Grand Aquarium",
            "penguins": "Take Ocean Express to Summit, then walk to Polar Adventure",
            "capybara": "Summit zone - take Ocean Express, then head to Rainforest area"
        }
    },
    
    "conservation": {
        "message": "Ocean Park is committed to wildlife conservation and education",
        "programs": [
            "Giant Panda breeding program",
            "Marine animal rescue and rehabilitation",
            "Educational programs for schools",
            "Research partnerships with universities"
        ]
    },
    
    # 🆕 COMPREHENSIVE ANIMAL-TO-LOCATION MAPPING
    "animal_locations": {
        # Mammals
        "giant panda": {"gallery": "Giant Panda Adventure", "zone": "Waterfront", "type": "mammal"},
        "red panda": {"gallery": "Giant Panda Adventure", "zone": "Waterfront", "type": "mammal"},
        "california sea lion": {"gallery": "Marine Mammal Breeding and Research Centre", "zone": "Summit", "type": "mammal"},
        "sea lion": {"gallery": "Pacific Pier", "zone": "Summit", "type": "mammal"},
        "harbour seal": {"gallery": "Pacific Pier", "zone": "Summit", "type": "mammal"},
        "spotted seal": {"gallery": "North Pole Encounter", "zone": "Summit", "type": "mammal"},
        "seal": {"gallery": "Pacific Pier or North Pole Encounter", "zone": "Summit", "type": "mammal"},
        "arctic fox": {"gallery": "Arctic Fox Den", "zone": "Summit", "type": "mammal"},
        "pacific walrus": {"gallery": "North Pole Encounter", "zone": "Summit", "type": "mammal"},
        "walrus": {"gallery": "North Pole Encounter", "zone": "Summit", "type": "mammal"},
        "capybara": {"gallery": "Expedition Trail", "zone": "Summit", "type": "mammal"},
        "two-toed sloth": {"gallery": "Sloth and Friends Studio", "zone": "Waterfront", "type": "mammal"},
        "sloth": {"gallery": "Sloth and Friends Studio", "zone": "Waterfront", "type": "mammal"},
        "asian small-clawed otter": {"gallery": "Panda Village", "zone": "Waterfront", "type": "mammal"},
        "otter": {"gallery": "Panda Village", "zone": "Waterfront", "type": "mammal"},
        "meerkat": {"gallery": "Little Meerkat and Giant Tortoise Adventure", "zone": "Waterfront", "type": "mammal"},
        "tortoise": {"gallery": "Little Meerkat and Giant Tortoise Adventure", "zone": "Waterfront", "type": "reptile"},
        "aldabra giant tortoise": {"gallery": "Little Meerkat and Giant Tortoise Adventure", "zone": "Waterfront", "type": "reptile"},
        "golden snub-nosed monkey": {"gallery": "Hong Kong Jockey Club Sichuan Treasures", "zone": "Waterfront", "type": "mammal"},
        "monkey": {"gallery": "Hong Kong Jockey Club Sichuan Treasures", "zone": "Waterfront", "type": "mammal"},
        "kinkajou": {"gallery": "Expedition Trail or Sloth and Friends Studio", "zone": "Summit/Waterfront", "type": "mammal"},
        "dolphin": {"gallery": "Marine Mammal Breeding and Research Centre or Dolphin Explorations", "zone": "Summit", "type": "mammal"},
        "bottlenose dolphin": {"gallery": "Marine Mammal Breeding and Research Centre or Dolphin Explorations", "zone": "Summit", "type": "mammal"},
        
        # Birds
        "king penguin": {"gallery": "Monkey Tree presents South Pole Spectacular", "zone": "Summit", "type": "bird"},
        "gentoo penguin": {"gallery": "Monkey Tree presents South Pole Spectacular", "zone": "Summit", "type": "bird"},
        "southern rockhopper penguin": {"gallery": "Monkey Tree presents South Pole Spectacular", "zone": "Summit", "type": "bird"},
        "rockhopper penguin": {"gallery": "Monkey Tree presents South Pole Spectacular", "zone": "Summit", "type": "bird"},
        "penguin": {"gallery": "Monkey Tree presents South Pole Spectacular", "zone": "Summit", "type": "bird"},
        "macaw": {"gallery": "Expedition Trail or Sloth and Friends Studio", "zone": "Summit/Waterfront", "type": "bird"},
        "toco toucan": {"gallery": "Expedition Trail", "zone": "Summit", "type": "bird"},
        "toucan": {"gallery": "Expedition Trail", "zone": "Summit", "type": "bird"},
        
        # Reptiles & Amphibians
        "chinese giant salamander": {"gallery": "Giant Panda Adventure", "zone": "Waterfront", "type": "amphibian"},
        "salamander": {"gallery": "Giant Panda Adventure", "zone": "Waterfront", "type": "amphibian"},
        "chinese alligator": {"gallery": "Gator Marsh", "zone": "Waterfront", "type": "reptile"},
        "alligator": {"gallery": "Gator Marsh", "zone": "Waterfront", "type": "reptile"},
        "ball python": {"gallery": "Sloth and Friends Studio", "zone": "Waterfront", "type": "reptile"},
        "python": {"gallery": "Sloth and Friends Studio", "zone": "Waterfront", "type": "reptile"},
        "poison dart frog": {"gallery": "Expedition Trail", "zone": "Summit", "type": "amphibian"},
        "crocodile": {"gallery": "Croco Land", "zone": "Waterfront", "type": "reptile"},
        "siamese-cuban crocodile": {"gallery": "Croco Land", "zone": "Waterfront", "type": "reptile"},
        
        # Fish & Marine Life
        "shark": {"gallery": "Shark Mystique or The Grand Aquarium", "zone": "Waterfront", "type": "fish"},
        "sawfish": {"gallery": "Shark Mystique", "zone": "Summit", "type": "fish"},
        "zebra shark": {"gallery": "Shark Mystique", "zone": "Summit", "type": "fish"},
        "ray": {"gallery": "Shark Mystique or The Grand Aquarium", "zone": "Waterfront/Summit", "type": "fish"},
        "sea jelly": {"gallery": "Sea Jelly Spectacular", "zone": "Summit", "type": "invertebrate"},
        "jellyfish": {"gallery": "Sea Jelly Spectacular", "zone": "Summit", "type": "invertebrate"},
        "arapaima": {"gallery": "Expedition Trail", "zone": "Summit", "type": "fish"},
        "sea cucumber": {"gallery": "The Grand Aquarium", "zone": "Waterfront", "type": "invertebrate"},
        "starfish": {"gallery": "The Grand Aquarium", "zone": "Waterfront", "type": "invertebrate"},
        "reef fish": {"gallery": "The Grand Aquarium", "zone": "Waterfront", "type": "fish"},
        "pygmy marmoset": {"gallery": "Expedition Trail", "zone": "Summit", "type": "mammal"}
    }
}

# 🆕 Enhanced lookup functions
def find_animal_location(animal_name: str):
    """Find where a specific animal is located in the park"""
    animal_lower = animal_name.lower().strip()
    
    # Direct lookup first in animal_locations
    if "animal_locations" in PARK_INFO and animal_lower in PARK_INFO["animal_locations"]:
        location_info = PARK_INFO["animal_locations"][animal_lower]
        gallery = location_info["gallery"]
        zone = location_info["zone"]
        animal_type = location_info["type"]
        
        # Try to get more details from PARK_ANIMAL_INFO
        attraction_info = get_detailed_attraction_info(gallery)
        if attraction_info:
            return {
                "animal": animal_name,
                "gallery": gallery,
                "zone": zone,
                "type": animal_type,
                "description": attraction_info.get("description", ""),
                "highlights": attraction_info.get("highlights", [])
            }
        else:
            return {
                "animal": animal_name,
                "gallery": gallery,
                "zone": zone,
                "type": animal_type
            }
    
    # Partial match search
    if "animal_locations" in PARK_INFO:
        for animal_key, location_info in PARK_INFO["animal_locations"].items():
            if animal_lower in animal_key or animal_key in animal_lower:
                return find_animal_location(animal_key)
    
    return None

def get_all_animals_in_gallery(gallery_name: str):
    """Get all animals in a specific gallery - uses PARK_ANIMAL_INFO"""
    attraction_info = get_detailed_attraction_info(gallery_name)
    if attraction_info:
        return {
            "gallery": attraction_info.get("name"),
            "zone": attraction_info.get("zone"),
            "animals": attraction_info.get("animals", []),
            "description": attraction_info.get("description", "")
        }
    return None

def get_galleries_by_zone(zone_name: str):
    """Get all animal galleries in a specific zone"""
    zone_title = zone_name.title()
    galleries = []
    
    # Get from PARK_INFO activities Animals category
    if "activities" in PARK_INFO and "Animals" in PARK_INFO["activities"]:
        for attraction in PARK_INFO["activities"]["Animals"]["attractions"]:
            if attraction.get("zone", "").lower() == zone_name.lower():
                # Get more details from PARK_ANIMAL_INFO
                detailed_info = get_detailed_attraction_info(attraction["name"])
                if detailed_info:
                    galleries.append({
                        "name": attraction["name"],
                        "animals": detailed_info.get("animals", []),
                        "description": detailed_info.get("description", "")
                    })
                else:
                    galleries.append({
                        "name": attraction["name"],
                        "location": attraction.get("location", "")
                    })
    
    return {
        "zone": zone_title,
        "gallery_count": len(galleries),
        "galleries": galleries
    }

def get_all_galleries_summary():
    """Get summary of all animal galleries from PARK_INFO activities"""
    if "activities" not in PARK_INFO or "Animals" not in PARK_INFO["activities"]:
        return {
            "total_galleries": 0,
            "waterfront_galleries": 0,
            "summit_galleries": 0,
            "waterfront": [],
            "summit": []
        }
    
    waterfront = []
    summit = []
    
    for attraction in PARK_INFO["activities"]["Animals"]["attractions"]:
        gallery_info = {
            "name": attraction["name"],
            "location": attraction["location"],
            "special_notes": attraction.get("special_notes", [])
        }
        
        if attraction.get("zone") == "Waterfront":
            waterfront.append(gallery_info)
        elif attraction.get("zone") == "Summit":
            summit.append(gallery_info)
    
    return {
        "total_galleries": PARK_INFO["activities"]["Animals"]["total_galleries"],
        "waterfront_galleries": len(waterfront),
        "summit_galleries": len(summit),
        "waterfront": waterfront,
        "summit": summit
    }

# Quick lookup functions
def get_attraction_info(animal_name: str):
    """Find which attraction houses a specific animal - uses PARK_ANIMAL_INFO"""
    # This function now references PARK_ANIMAL_INFO instead of old structure
    return search_animal_detailed_info(animal_name)

def get_directions(destination: str):
    """Get directions to a destination"""
    dest_lower = destination.lower()
    
    # Try exact match first from general_info
    if "directions" in PARK_INFO and "from_entrance_to" in PARK_INFO["directions"]:
        for key, directions in PARK_INFO["directions"]["from_entrance_to"].items():
            if key in dest_lower or dest_lower in key:
                return directions
    
    # Try searching in PARK_ANIMAL_INFO
    for key, data in PARK_ANIMAL_INFO.items():
        if dest_lower in data.get('name', '').lower():
            zone = data.get('zone', 'Unknown')
            if zone == "Waterfront":
                return f"{data['name']} is in the Waterfront zone, near the entrance. Just follow the signs!"
            else:
                return f"{data['name']} is at the Summit. Take the Ocean Express or Cable Car up, then follow signs!"
    
    return None

def get_zone_attractions(zone: str):
    """Get all attractions in a zone"""
    zone_title = zone.title()
    if "general_info" in PARK_INFO and "zones" in PARK_INFO["general_info"]:
        if zone_title in PARK_INFO["general_info"]["zones"]:
            return PARK_INFO["general_info"]["zones"][zone_title]
    return None

# 🆕 Functions to query PARK_ANIMAL_INFO (detailed website data)
def get_detailed_attraction_info(attraction_name: str):
    """Get detailed info from PARK_ANIMAL_INFO if available"""
    attraction_key = attraction_name.lower().replace(' ', '_')
    
    if attraction_key in PARK_ANIMAL_INFO:
        return PARK_ANIMAL_INFO[attraction_key]
    
    # Try partial match
    for key, data in PARK_ANIMAL_INFO.items():
        if attraction_name.lower() in data.get('name', '').lower():
            return data
    
    return None

def search_animal_detailed_info(animal_name: str):
    """Search for animal in detailed PARK_ANIMAL_INFO"""
    animal_lower = animal_name.lower()
    results = []
    
    for key, data in PARK_ANIMAL_INFO.items():
        # Check in animals list
        if 'animals' in data:
            for animal in data['animals']:
                if animal_lower in animal.lower():
                    results.append(data)
                    break
        
        # Check in description
        if animal_lower in data.get('description', '').lower():
            if data not in results:
                results.append(data)
    
    return results if results else None

# 🆕 NEW: Helper functions for the 5-category PARK_INFO structure
def get_activities_by_category(category_name: str):
    """Get all activities in a specific category (Animals, Rides, Family Attractions, etc.)"""
    if "activities" not in PARK_INFO:
        return None
    
    if category_name in PARK_INFO["activities"]:
        return PARK_INFO["activities"][category_name]
    return None

def get_all_rides():
    """Get all rides (Thrill + Wet)"""
    return get_activities_by_category("Rides")

def get_all_transportation():
    """Get all in-park transportation options"""
    return get_activities_by_category("In-Park Transportation")

def search_activity_by_name(activity_name: str):
    """Search for an activity across all categories"""
    activity_lower = activity_name.lower()
    
    for category_name, category_data in PARK_INFO["activities"].items():
        if "attractions" in category_data:
            for attraction in category_data["attractions"]:
                if activity_lower in attraction["name"].lower():
                    return {
                        "category": category_name,
                        "attraction": attraction
                    }
    return None

# Test
if __name__ == "__main__":
    print("=" * 60)
    print("OCEAN PARK KNOWLEDGE BASE - TESTING")
    print("=" * 60)
    
    # Test 1: Gallery summary
    print("\n1. GALLERY SUMMARY:")
    summary = get_all_galleries_summary()
    print(f"   Total animal galleries: {summary['total_galleries']}")
    print(f"   Waterfront zone: {summary['waterfront_galleries']} galleries")
    print(f"   Summit zone: {summary['summit_galleries']} galleries")
    
    # Test 2: Find specific animals
    print("\n2. FIND ANIMAL LOCATIONS:")
    test_animals = ["giant panda", "penguin", "shark", "sloth", "capybara"]
    for animal in test_animals:
        info = find_animal_location(animal)
        if info:
            print(f"   {animal.title()}: {info['gallery']} ({info['zone']} zone)")
    
    # Test 3: Get all animals in a gallery
    print("\n3. ANIMALS IN RAINFOREST GALLERY:")
    rainforest = get_all_animals_in_gallery("Rainforest")
    if rainforest:
        print(f"   Location: {rainforest['zone']} zone")
        if rainforest.get('animals'):
            print(f"   Animals: {', '.join(rainforest['animals'][:5])}...")
    
    # Test 4: Get galleries by zone
    print("\n4. WATERFRONT ZONE GALLERIES:")
    waterfront_galleries = get_galleries_by_zone("Waterfront")
    for gallery in waterfront_galleries['galleries'][:3]:
        animal_count = len(gallery.get('animals', []))
        print(f"   - {gallery['name']}: {animal_count} species")
    
    # Test 5: Directions
    print("\n5. DIRECTIONS:")
    directions_test = ["panda", "penguins", "aquarium"]
    for dest in directions_test:
        directions = get_directions(dest)
        if directions:
            print(f"   To {dest}: {directions[:80]}...")
    
    # Test 6: NEW - Test 5-category structure
    print("\n6. NEW 5-CATEGORY STRUCTURE:")
    print("   Categories available:")
    for category in PARK_INFO["activities"].keys():
        count = len(PARK_INFO["activities"][category].get("attractions", []))
        print(f"   - {category}: {count} attractions")
    
    # Test 7: Search activities
    print("\n7. SEARCH ACTIVITIES:")
    test_searches = ["Cable Car", "Hair Raiser", "Ferris Wheel"]
    for search_term in test_searches:
        result = search_activity_by_name(search_term)
        if result:
            print(f"   {search_term}: {result['category']} | {result['attraction']['zone']}")
    
    print("\n" + "=" * 60)
    print("✅ Knowledge base ready!")
    print("=" * 60)


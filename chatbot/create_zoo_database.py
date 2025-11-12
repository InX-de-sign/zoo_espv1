# create_zoo_database.py - Create SQLite database for Ocean Park Zoo
import sqlite3
import os

def create_zoo_database(db_path="zoo.db"):
    """Create zoo database with animal information"""
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing {db_path}")
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create animals table (similar structure to artifacts table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_name TEXT NOT NULL,
            scientific_name TEXT,
            distribution_range TEXT,
            habitat TEXT,
            phylum TEXT,
            class TEXT,
            order_name TEXT,
            family TEXT,
            genus TEXT,
            characteristics TEXT,
            body_measurements TEXT,
            diet TEXT,
            behavior TEXT,
            location_at_park TEXT,
            stories TEXT,
            conservation_status TEXT,
            threats TEXT,
            conservation_actions TEXT
        )
    ''')
    
    # Insert animal data
    animals = [
        # On-land Animals
        {
            'common_name': 'Capybara',
            'scientific_name': 'Hydrochoerus hydrochaeris',
            'distribution_range': 'Central and northern South America',
            'habitat': 'Wetlands and riversides',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Rodentia',
            'family': 'Caviidae',
            'genus': 'Hydrochoerus',
            'characteristics': "World's largest rodent; eyes, ears, mouth, and nose positioned at the top of the head for diving; water-loving behavior, enjoys baths and playing with enrichment items",
            'diet': 'Carrots, sweet potatoes, lettuce, peas, and apples',
            'location_at_park': 'Expedition Trail; Rainforest; Waterfront Plaza (for events)',
            'stories': "Arrived as animal ambassadors for events; featured in 2020 Lunar New Year celebrations with themed attractions like Capybara Garden of Fortune, Prosperity Pool, and workshops; received special treats like coin-shaped carrots and fai chun installations; highlighted in 2018 Animal Discovery Fest for up-close encounters and feeding",
            'threats': 'Over-hunting and illegal wildlife trade',
            'conservation_actions': 'Avoid products from threatened species'
        },
        {
            'common_name': 'Red Panda',
            'scientific_name': 'Ailurus fulgens',
            'distribution_range': 'Bamboo forests throughout the Himalayas, including China, Nepal, and India',
            'habitat': 'Bamboo forests',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Carnivora',
            'family': 'Ailuridae',
            'genus': 'Ailurus',
            'characteristics': 'Extra "thumb" (wrist bone extension) for grasping bamboo; active and playful, responds to training like target practice and scales',
            'body_measurements': 'Head and body: 56-63 cm; tail: 37-47 cm; weight: 4-6 kg',
            'diet': 'Mainly bamboo (3-5 kg/day), plus acorns, roots, berries, lichens, eggs, and birds',
            'behavior': 'Active and playful',
            'location_at_park': 'Amazing Asian Animals I Waterfront',
            'stories': "Four young red pandas (Tai Shan, Rou Rou, Cong Cong, Li Zi) arrived from Chengdu Research Base in March 2009 on loan for research and conservation; adapted well, each gained ~1 kg by April 2009; debuted in April 2009 at Giant Panda Adventure; female Li Zi died suddenly in June 2013 (possible heart failure or blood clots); serves as education ambassadors",
            'threats': 'Habitat loss and poaching; population dropped ~50% in 20 years',
            'conservation_actions': 'Support FSC-certified products'
        },
        {
            'common_name': 'Giant Panda',
            'scientific_name': 'Ailuropoda melanoleuca',
            'distribution_range': 'Bamboo forests, endemic to Sichuan, Shaanxi, and Gansu provinces in China',
            'habitat': 'Bamboo forests',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Carnivora',
            'family': 'Ursidae',
            'genus': 'Ailuropoda',
            'characteristics': 'Newborns weigh ~100 g, adults up to 1,000 times heavier; short mating periods; enjoy icy treats and fruits',
            'body_measurements': 'Body length: 1.2-1.8 m; weight: 100 kg',
            'diet': 'Need 4,300-5,500 kcal/day (equivalent to 20 bowls of rice)',
            'location_at_park': 'Amazing Asian Animals I Waterfront',
            'stories': "Home to Jia Jia (world's oldest under care at 36 in 2014), An An (28 in 2014), Ying Ying, and Le Le; birthday celebrations with icy treats in 2014; mating efforts in 2014 (no pregnancy, but optimistic for future)",
            'threats': 'Habitat fragmentation; fewer than 1,900 left in wild',
            'conservation_actions': 'Support FSC-certified products to protect forests'
        },
        {
            'common_name': 'Sloth',
            'scientific_name': 'Choloepus didactylus',
            'distribution_range': 'Tropical forests in Central America and northern South America, including Venezuela, Guyana, and Brazil',
            'habitat': 'Tropical forests; high in the canopy, hanging from branches',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Pilosa',
            'family': 'Choloepodidae',
            'genus': 'Choloepus',
            'characteristics': 'Slow metabolic rate allows survival on small amounts of vegetation; digestion takes nearly a month; discharge waste weekly; nocturnal, sleep >15 hours/day; live upside-down (eat, sleep, breed); only descend for defecation or new trees',
            'body_measurements': 'Body length: 46-86 cm; weight: 4-8 kg',
            'location_at_park': 'Rainforest I Summit; Aqua City I Waterfront',
            'stories': 'Featured in Sloth and Friends Studio (opened 2023) with AI art and conservation education',
            'threats': 'Logging and poaching',
            'conservation_actions': 'Reuse/recycle paper to protect habitats'
        },
        # Ice Land Animals
        {
            'common_name': 'Arctic Fox',
            'scientific_name': 'Vulpes lagopus',
            'distribution_range': 'Arctic tundra in countries such as Canada, Greenland, and Finland',
            'habitat': 'Arctic tundra',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Carnivora',
            'family': 'Canidae',
            'genus': 'Vulpes',
            'characteristics': 'Moult twice yearly (white in winter for camouflage, brown/grey in summer); opportunistic feeders; store excess food in dens for winter; grow quickly; solitary',
            'body_measurements': 'Head and body: 46-68 cm; tail: up to 35 cm; weight: 3-8 kg',
            'diet': 'Small mammals, birds, insects, berries',
            'location_at_park': 'Polar Adventure I Summit; Arctic Fox Den',
            'stories': 'Gochi (male) arrived from US in 2012; Mochi (female) confiscated from Mainland China in 2013; first-ever breeding in HK in 2014 (6 pups: 4 females, 2 males; one with greyish-black fur)',
            'threats': 'Fur hunting and farms',
            'conservation_actions': 'Avoid fur products'
        },
        {
            'common_name': 'California Sea Lion',
            'scientific_name': 'Zalophus californianus',
            'distribution_range': 'Eastern North Pacific, from British Columbia, Canada, to Baja California, Mexico',
            'habitat': 'Coastal waters, rocky shores, and islands',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Carnivora',
            'family': 'Otariidae',
            'genus': 'Zalophus',
            'characteristics': 'Streamlined body with external ear flaps; agile swimmers, can "walk" on land using flippers; known for intelligence and trainability, often perform in shows',
            'body_measurements': 'Body length: males 2.1-2.4 m, females 1.8 m; weight: males up to 350 kg, females up to 100 kg',
            'diet': 'Fish and squid',
            'location_at_park': 'Pacific Pier I Summit; Sea Lion and Seal Expedition',
            'stories': 'Featured in Ocean Theatre performances showcasing agility and intelligence; part of conservation education programs',
            'conservation_status': 'IUCN: Least Concern',
            'threats': 'Overfishing and marine pollution',
            'conservation_actions': 'Support sustainable seafood to protect marine habitats'
        },
        {
            'common_name': 'King Penguin',
            'scientific_name': 'Aptenodytes patagonicus',
            'distribution_range': 'Sub-Antarctic islands and southern coasts of Argentina and Chile',
            'habitat': 'Coastal and marine environments; forms large colonies',
            'phylum': 'Chordata',
            'class': 'Aves',
            'order_name': 'Sphenisciformes',
            'family': 'Spheniscidae',
            'genus': 'Aptenodytes',
            'characteristics': 'No nests—incubate single egg on feet under belly (55 days hatching, 30-40 days post-hatch care); social, form colonies of tens of thousands for protection and heat (huddle in cold)',
            'body_measurements': 'Body length: 85-95 cm; weight: 9.3-17.3 kg',
            'diet': 'Small fishes and squid',
            'behavior': 'Social, form large colonies',
            'location_at_park': 'Polar Adventure I Summit',
            'conservation_status': 'IUCN: Least Concern',
            'threats': 'Climate change shifting prey distribution, reducing food and breeding success (0.26°C rise could cut adult survival by ~10%)',
            'conservation_actions': 'Reduce carbon emissions'
        },
        {
            'common_name': 'Harbour Seal',
            'scientific_name': 'Phoca vitulina',
            'distribution_range': 'Coastal waters in temperate and Arctic regions of the Northern Hemisphere',
            'habitat': 'Coastal marine environments',
            'phylum': 'Chordata',
            'class': 'Mammalia',
            'order_name': 'Carnivora',
            'family': 'Phocidae',
            'genus': 'Phoca',
            'characteristics': 'Coat with unique dark spots and light rings; pups fed high-fat milk (50%); weaned at 4-6 weeks for rapid growth',
            'body_measurements': 'Body length: 1.6-1.9 m; weight: male 80-170 kg, female 60-145 kg',
            'location_at_park': 'Pacific Pier I Summit; Sea Lion and Seal Expedition',
            'conservation_status': 'IUCN: Least Concern',
            'threats': 'By-catch, entanglement in gear, reduced food from fishing, hunting to protect fisheries',
            'conservation_actions': 'Support sustainable seafood'
        }
    ]
    
    # Insert animals
    for animal in animals:
        cursor.execute('''
            INSERT INTO animals (
                common_name, scientific_name, distribution_range, habitat,
                phylum, class, order_name, family, genus,
                characteristics, body_measurements, diet, behavior,
                location_at_park, stories, conservation_status, threats, conservation_actions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            animal.get('common_name'),
            animal.get('scientific_name'),
            animal.get('distribution_range'),
            animal.get('habitat'),
            animal.get('phylum'),
            animal.get('class'),
            animal.get('order_name'),
            animal.get('family'),
            animal.get('genus'),
            animal.get('characteristics'),
            animal.get('body_measurements'),
            animal.get('diet'),
            animal.get('behavior'),
            animal.get('location_at_park'),
            animal.get('stories'),
            animal.get('conservation_status'),
            animal.get('threats'),
            animal.get('conservation_actions')
        ))
    
    conn.commit()
    
    # Verify
    cursor.execute('SELECT COUNT(*) FROM animals')
    count = cursor.fetchone()[0]
    print(f"✅ Created zoo.db with {count} animals")
    
    # Show sample
    cursor.execute('SELECT common_name, scientific_name, location_at_park FROM animals LIMIT 3')
    samples = cursor.fetchall()
    print("\nSample animals:")
    for name, sci_name, location in samples:
        print(f"  - {name} ({sci_name}) at {location}")
    
    conn.close()
    return db_path

if __name__ == "__main__":
    create_zoo_database()
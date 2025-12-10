# quick_add_attraction.py - Interactive tool to quickly add attraction data
"""
Quick interactive tool to add attraction data to park_knowledge.py
Easier than manually editing the file!
"""

import re

def sanitize_key(name):
    """Convert attraction name to dict key"""
    return name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace("'", '')

def add_attraction_interactive():
    """Interactive mode to add one attraction"""
    print("\n" + "=" * 60)
    print("QUICK ADD ATTRACTION TO PARK_ANIMAL_INFO")
    print("=" * 60)
    print("\n💡 Paste data from Ocean Park attraction page")
    print("   Press Enter after each field\n")
    
    # Collect data
    name = input("Attraction Name (e.g., 'Arctic Fox Den'): ").strip()
    if not name:
        print("❌ Name required!")
        return None
    
    location_full = input("Location (e.g., 'Polar Adventure | Summit'): ").strip()
    zone = location_full.split('|')[-1].strip() if '|' in location_full else input("Zone (Waterfront/Summit): ").strip()
    
    print("\nDescription (paste full text, then press Enter twice):")
    description_lines = []
    empty_count = 0
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
            description_lines.append(line)
    
    description = ' '.join(description_lines).strip()
    
    print("\nAnimals (comma-separated, e.g., 'Arctic Fox, Polar Bear'):")
    animals_input = input().strip()
    animals = [a.strip() for a in animals_input.split(',') if a.strip()]
    
    print("\nHighlights (one per line, press Enter twice when done):")
    highlights = []
    empty_count = 0
    while True:
        line = input().strip()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
            if line:
                highlights.append(line)
    
    print("\nWhat's Near By (comma-separated):")
    nearby_input = input().strip()
    nearby = [n.strip() for n in nearby_input.split(',') if n.strip()]
    
    url = input("\nURL (optional): ").strip()
    if not url:
        url = f"https://www.oceanpark.com.hk/en/experience/attractions/{sanitize_key(name)}"
    
    # Generate dict entry
    key = sanitize_key(name)
    
    entry = f"""
    '{key}': {{
        'name': '{name}',
        'location': '{location_full}',
        'zone': '{zone}',
        'description': '''{description}''',
        'animals': {animals},
        'highlights': {highlights},
        'what_near_by': {nearby},
        'url': '{url}'
    }},
"""
    
    return entry

def main():
    print("\n" + "=" * 60)
    print("OCEAN PARK ATTRACTION DATA ENTRY TOOL")
    print("=" * 60)
    
    entries = []
    
    while True:
        entry = add_attraction_interactive()
        if entry:
            entries.append(entry)
            print("\n✅ Attraction added!")
            print(entry)
        
        another = input("\nAdd another attraction? (y/n): ").strip().lower()
        if another != 'y':
            break
    
    if entries:
        output_file = 'new_attractions.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Copy these entries into park_knowledge.py PARK_ANIMAL_INFO section:\n\n")
            f.write("PARK_ANIMAL_INFO = {\n")
            for entry in entries:
                f.write(entry)
            f.write("}\n")
        
        print("\n" + "=" * 60)
        print(f"✅ Saved {len(entries)} attractions to {output_file}")
        print("=" * 60)
        print("\n📋 Next steps:")
        print(f"   1. Open {output_file}")
        print("   2. Copy the content")
        print("   3. Paste into park_knowledge.py PARK_ANIMAL_INFO section")
        print("   4. Run: python update_zoo_database.py")
        print("   5. Deploy to Docker")
    else:
        print("\n❌ No attractions added")

if __name__ == "__main__":
    main()

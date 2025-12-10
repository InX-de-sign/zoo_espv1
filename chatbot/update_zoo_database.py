# update_zoo_database.py - Update zoo.db with new animal information
"""
This script updates the zoo.db SQLite database with data from park_knowledge.py

Run this after updating PARK_ANIMAL_INFO to sync the database.

Usage:
    python update_zoo_database.py
"""

import sqlite3
import os
from park_knowledge import PARK_INFO, PARK_ANIMAL_INFO

DB_PATH = 'zoo.db'

def create_backup():
    """Backup existing database"""
    if os.path.exists(DB_PATH):
        backup_path = f"{DB_PATH}.backup"
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return True
    return False

def update_animals_table():
    """Update animals table with data from PARK_INFO and PARK_ANIMAL_INFO"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='animals'
    """)
    
    if not cursor.fetchone():
        print("⚠️ Table 'animals' doesn't exist. Creating it...")
        cursor.execute("""
            CREATE TABLE animals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                common_name TEXT NOT NULL,
                scientific_name TEXT,
                distribution_range TEXT,
                habitat TEXT,
                characteristics TEXT,
                body_measurements TEXT,
                diet TEXT,
                behavior TEXT,
                location_at_park TEXT,
                stories TEXT,
                conservation_status TEXT,
                threats TEXT,
                conservation_actions TEXT,
                gallery TEXT,
                zone TEXT,
                website_description TEXT,
                highlights TEXT,
                url TEXT
            )
        """)
        print("✅ Table 'animals' created")
    
    updated_count = 0
    inserted_count = 0
    
    # Process PARK_ANIMAL_INFO (detailed website data)
    for key, data in PARK_ANIMAL_INFO.items():
        name = data.get('name', '')
        animals_list = data.get('animals', [])
        
        # If specific animals listed, create entries for each
        if animals_list:
            for animal in animals_list:
                # Check if animal exists
                cursor.execute("""
                    SELECT id FROM animals WHERE LOWER(common_name) = LOWER(?)
                """, (animal,))
                
                exists = cursor.fetchone()
                
                highlights_text = '\n'.join(data.get('highlights', []))
                
                if exists:
                    # Update existing
                    cursor.execute("""
                        UPDATE animals SET
                            gallery = ?,
                            zone = ?,
                            website_description = ?,
                            highlights = ?,
                            url = ?,
                            location_at_park = ?
                        WHERE LOWER(common_name) = LOWER(?)
                    """, (
                        name,
                        data.get('zone', ''),
                        data.get('description', ''),
                        highlights_text,
                        data.get('url', ''),
                        data.get('location', ''),
                        animal
                    ))
                    updated_count += 1
                else:
                    # Insert new
                    cursor.execute("""
                        INSERT INTO animals (
                            common_name, gallery, zone, 
                            website_description, highlights, url, location_at_park
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        animal,
                        name,
                        data.get('zone', ''),
                        data.get('description', ''),
                        highlights_text,
                        data.get('url', ''),
                        data.get('location', '')
                    ))
                    inserted_count += 1
        else:
            # Gallery/exhibit without specific animals listed
            cursor.execute("""
                SELECT id FROM animals WHERE LOWER(common_name) = LOWER(?)
            """, (name,))
            
            exists = cursor.fetchone()
            highlights_text = '\n'.join(data.get('highlights', []))
            
            if exists:
                cursor.execute("""
                    UPDATE animals SET
                        zone = ?,
                        website_description = ?,
                        highlights = ?,
                        url = ?,
                        location_at_park = ?
                    WHERE LOWER(common_name) = LOWER(?)
                """, (
                    data.get('zone', ''),
                    data.get('description', ''),
                    highlights_text,
                    data.get('url', ''),
                    data.get('location', ''),
                    name
                ))
                updated_count += 1
            else:
                cursor.execute("""
                    INSERT INTO animals (
                        common_name, zone, website_description, 
                        highlights, url, location_at_park
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    data.get('zone', ''),
                    data.get('description', ''),
                    highlights_text,
                    data.get('url', ''),
                    data.get('location', '')
                ))
                inserted_count += 1
    
    conn.commit()
    conn.close()
    
    return updated_count, inserted_count

def verify_database():
    """Verify database contents"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM animals")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM animals WHERE website_description IS NOT NULL")
    with_web_data = cursor.fetchone()[0]
    
    cursor.execute("SELECT common_name, gallery, zone FROM animals LIMIT 5")
    samples = cursor.fetchall()
    
    conn.close()
    
    return {
        'total': total,
        'with_web_data': with_web_data,
        'samples': samples
    }

def main():
    print("=" * 60)
    print("ZOO DATABASE UPDATE TOOL")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"\n⚠️ Database not found: {DB_PATH}")
        print("Creating new database...")
    
    # Backup
    print("\n📦 Step 1: Creating backup...")
    create_backup()
    
    # Update
    print("\n🔄 Step 2: Updating animals table...")
    updated, inserted = update_animals_table()
    
    print(f"   ✅ Updated: {updated} records")
    print(f"   ✅ Inserted: {inserted} new records")
    
    # Verify
    print("\n🔍 Step 3: Verifying database...")
    stats = verify_database()
    print(f"   Total animals in database: {stats['total']}")
    print(f"   Animals with website data: {stats['with_web_data']}")
    
    print("\n📋 Sample entries:")
    for name, gallery, zone in stats['samples']:
        print(f"   - {name} ({gallery}, {zone})")
    
    print("\n" + "=" * 60)
    print("✅ DATABASE UPDATE COMPLETE!")
    print("=" * 60)
    
    print("\n💡 Next steps:")
    print("   1. Copy updated zoo.db to Docker container:")
    print("      docker cp zoo.db zoo_chatbot:/app/zoo.db")
    print("   2. Restart chatbot:")
    print("      docker-compose restart chatbot")

if __name__ == "__main__":
    main()

# OCEAN PARK DATA MANAGEMENT GUIDE

## Overview
This system manages Ocean Park animal and attraction data in three formats:
1. **PARK_ANIMAL_INFO** - Detailed data from Ocean Park website (Python dict)
2. **PARK_INFO** - Hand-curated general park info (Python dict)
3. **zoo.db** - SQLite database for fast querying

## Files

### Core Files
- `park_knowledge.py` - Main knowledge base with PARK_INFO and PARK_ANIMAL_INFO
- `zoo.db` - SQLite database

### Data Collection Tools
- `scrape_oceanpark.py` - Web scraper to extract data from Ocean Park website
- `scraper_requirements.txt` - Python packages needed for scraping

### Database Tools
- `update_zoo_database.py` - Sync PARK_ANIMAL_INFO → zoo.db
- `create_zoo_database.py` - Initialize new database

---

## Workflow: Adding New Animal Data

### Method 1: Web Scraping (Automated)

```bash
# Install scraper dependencies
pip install -r scraper_requirements.txt

# Run scraper
python scrape_oceanpark.py
# Choose option 1 for automated scraping

# This creates:
# - oceanpark_animals_raw.json (raw scraped data)
# - oceanpark_animals_formatted.py (formatted Python dict)
```

Then copy the content from `oceanpark_animals_formatted.py` into `park_knowledge.py` PARK_ANIMAL_INFO section.

### Method 2: Manual Entry (Recommended if scraping fails)

```bash
python scrape_oceanpark.py
# Choose option 2 for manual entry

# Follow prompts to copy-paste data from Ocean Park website
```

Or directly edit `park_knowledge.py`:

```python
PARK_ANIMAL_INFO = {
    'arctic_fox_den': {
        'name': 'Arctic Fox Den',
        'location': 'Polar Adventure | Summit',
        'zone': 'Summit',
        'description': '''Learn the secrets of this elusive tundra predator...''',
        'animals': ['Arctic Fox'],
        'highlights': [
            'Arctic foxes change fur color seasonally',
            'Short limbs help them survive extreme cold'
        ],
        'what_near_by': ['Arctic Blast', 'Polar Adventure'],
        'url': 'https://www.oceanpark.com.hk/en/...'
    },
    # Add more attractions...
}
```

---

## Workflow: Updating Database

After updating PARK_ANIMAL_INFO in `park_knowledge.py`:

```bash
# Update zoo.db
python update_zoo_database.py
```

This will:
1. ✅ Create backup (zoo.db.backup)
2. ✅ Update existing animal records
3. ✅ Insert new animal records
4. ✅ Verify changes

Then deploy to Docker:

```bash
# Copy updated files
docker cp chatbot/park_knowledge.py zoo_chatbot:/app/park_knowledge.py
docker cp chatbot/zoo.db zoo_chatbot:/app/zoo.db

# Restart
docker-compose restart chatbot
```

---

## Data Structure

### PARK_ANIMAL_INFO Format
```python
{
    'attraction_key': {
        'name': str,              # Display name
        'location': str,          # "Gallery | Zone"
        'zone': str,              # "Waterfront" or "Summit"
        'description': str,       # Full description from website
        'animals': list[str],     # List of specific animals
        'highlights': list[str],  # Key facts/features
        'what_near_by': list[str], # Nearby attractions
        'url': str                # Source URL
    }
}
```

### Database Schema
```sql
CREATE TABLE animals (
    id INTEGER PRIMARY KEY,
    common_name TEXT,           -- Animal name
    scientific_name TEXT,
    gallery TEXT,               -- From PARK_ANIMAL_INFO
    zone TEXT,                  -- Waterfront/Summit
    website_description TEXT,   -- From website
    highlights TEXT,            -- Newline-separated
    url TEXT,                   -- Source URL
    location_at_park TEXT,
    -- ... other fields
);
```

---

## Usage in Chatbot

The enhanced RAG system (`enhanced_rag_openai.py`) queries both:

1. **PARK_ANIMAL_INFO** - For latest detailed web content
2. **zoo.db** - For fast structured queries

Example queries:
- "Where is the Arctic Fox?" → Uses find_animal_location()
- "Tell me about Polar Adventure" → Uses get_detailed_attraction_info()
- "What's near the Arctic Fox?" → Returns 'what_near_by' data

---

## Maintenance Schedule

**Weekly**: Check Ocean Park website for updates
**Monthly**: Run scraper to update PARK_ANIMAL_INFO
**As needed**: Update zoo.db when PARK_ANIMAL_INFO changes

---

## Troubleshooting

### Scraper fails with "element not found"
- Ocean Park updated their website HTML
- Use Manual Entry mode instead
- Update scraper selectors in `scrape_oceanpark.py`

### Database update fails
- Check zoo.db permissions
- Verify backup exists
- Manually check with: `sqlite3 zoo.db "SELECT * FROM animals LIMIT 5;"`

### Data not showing in chatbot
- Verify files copied to Docker: `docker exec zoo_chatbot ls -la /app/*.py`
- Check logs: `docker logs zoo_chatbot`
- Restart: `docker-compose restart chatbot`

---

## Best Practices

✅ **Always backup** before database updates
✅ **Version control** PARK_ANIMAL_INFO changes
✅ **Verify** after updates with test queries
✅ **Document** sources for manual data entry
✅ **Test locally** before deploying to Docker

---

For questions or issues, check the scraper output logs or database verification step.

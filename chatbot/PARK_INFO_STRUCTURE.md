# PARK_INFO Structure - 5 Categories

## Overview
`PARK_INFO` has been restructured to match Ocean Park's website categorization with 5 main activity categories.

## New Structure

```python
PARK_INFO = {
    "activities": {
        "Animals": {...},
        "Rides": {...},
        "Family Attractions": {...},
        "Programmes & Journey Experiences": {...},
        "In-Park Transportation": {...}
    },
    "general_info": {...},
    "directions": {...},
    "conservation": {...},
    "animal_locations": {...}
}
```

## Category Details

### 1. Animals (20 attractions)
- **Description**: Ocean Park houses over 400 species across 12 galleries
- **Structure**: 
  ```python
  {
      "name": "Giant Panda Adventure",
      "location": "Amazing Asian Animals | Waterfront",
      "zone": "Waterfront",
      "special_notes": []
  }
  ```
- **Examples**: Arctic Fox Den, Giant Panda Adventure, Sea Jelly Spectacular
- **Note**: Detailed animal info is in `PARK_ANIMAL_INFO` section

### 2. Rides (8 attractions)
- **Description**: Exciting thrill rides and water attractions
- **Subcategories**: Thrill Rides, Wet Rides (only 1 wet ride)
- **Structure**:
  ```python
  {
      "name": "Hair Raiser",
      "location": "Thrill Mountain | Summit",
      "zone": "Summit",
      "special_notes": ["Min. height: 132cm", "May not remain in wheelchair"]
  }
  ```
- **Examples**: Hair Raiser, The Dragon, Rapids (wet ride)

### 3. Family Attractions (5 attractions)
- **Description**: Fun attractions for the whole family
- **Structure**:
  ```python
  {
      "name": "Ferris Wheel",
      "location": "Waterfront",
      "zone": "Waterfront",
      "special_notes": ["Min. height: 152cm (60\")", "May remain in wheelchair"]
  }
  ```
- **Examples**: Sea Life Carousel, Ferris Wheel, Bumper Blaster

### 4. Programmes & Journey Experiences (3 attractions)
- **Description**: Interactive educational programmes and immersive experiences
- **Structure**:
  ```python
  {
      "name": "Ocean Park Academy",
      "location": "Various locations",
      "zone": "Waterfront/Summit",
      "special_notes": ["Educational programmes", "Booking required"]
  }
  ```
- **Examples**: Ocean Park Academy, Animal Encounters, Behind-the-Scenes Tours

### 5. In-Park Transportation (4 attractions)
- **Description**: Transportation connecting Waterfront and Summit zones
- **Structure**:
  ```python
  {
      "name": "Cable Car (The Summit)",
      "location": "Summit Cable Car Station | Summit",
      "zone": "Summit",
      "special_notes": ["May remain in wheelchair"]
  }
  ```
- **Examples**: Cable Car (Summit & Waterfront), Ocean Express (Summit & Waterfront)

## Helper Functions

### Query by Category
```python
# Get all activities in a category
get_activities_by_category("Rides")
get_all_rides()
get_all_transportation()
```

### Search Activities
```python
# Search across all categories
search_activity_by_name("Cable Car")
# Returns: {"category": "In-Park Transportation", "attraction": {...}}
```

### Animal Queries (uses PARK_ANIMAL_INFO)
```python
find_animal_location("panda")
get_all_animals_in_gallery("Giant Panda Adventure")
search_animal_detailed_info("sloth")
```

## Data Fields

Each attraction entry contains:
- **name**: Full attraction name
- **location**: Gallery/Area | Zone
- **zone**: "Waterfront" or "Summit"
- **special_notes**: Array of important info
  - Height restrictions (e.g., "Min. height: 132cm")
  - Accessibility (e.g., "May remain in wheelchair")
  - Status (e.g., "Closed from 5 January 2026")
  - Special features (e.g., "Free entry", "Booking required")

## Usage in Chatbot

When user asks about activities:
1. Classify query into category (Animals, Rides, etc.)
2. Use `search_activity_by_name()` or `get_activities_by_category()`
3. For animals specifically, use `PARK_ANIMAL_INFO` for detailed descriptions
4. Return special_notes for accessibility/requirements

## Migration Notes

**Old Structure** (deprecated):
```python
PARK_INFO["attractions"]["Giant Panda Adventure"]
```

**New Structure**:
```python
PARK_INFO["activities"]["Animals"]["attractions"][index]
# For detailed info: PARK_ANIMAL_INFO["giant_panda_adventure"]
```

## Testing

Run: `python park_knowledge.py`

Expected output shows:
- ✅ 5 categories with correct counts
- ✅ Search functionality working
- ✅ Animal location queries working
- ✅ All helper functions operational

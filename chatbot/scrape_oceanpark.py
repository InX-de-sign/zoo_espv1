# scrape_oceanpark.py - Ocean Park Animal Data Scraper
"""
Web scraper to extract animal information from Ocean Park website.
Since the site uses heavy JavaScript, we'll use Selenium for dynamic content.

Install required packages:
pip install selenium beautifulsoup4 lxml requests webdriver-manager

NOTE: Selenium scraping often fails on Ocean Park website due to JavaScript.
RECOMMENDED: Use Option 2 (Manual Entry) or Option 3 (Quick Add Tool) instead.
"""

import json
import time
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("\n⚠️ Selenium not installed. Only manual entry available.")
    print("To install: pip install -r scraper_requirements.txt")

class OceanParkScraper:
    def __init__(self):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Use manual entry mode instead.")
        
        # Setup Chrome options
        chrome_options = Options()
        # chrome_options.add_argument('--headless')  # Uncomment to run without browser window
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Initialize driver with webdriver-manager
        print("🚀 Starting Chrome browser...")
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            print("\n💡 Try using Option 2 (Manual Entry) instead!")
            raise
        
        self.wait = WebDriverWait(self.driver, 10)
        
        self.animal_data = {}
    
    def scrape_attraction_list(self):
        """Step 1: Get list of all animal attractions"""
        url = "https://www.oceanpark.com.hk/en/experience/attractions/attractions#type-animals"
        print(f"\n📍 Navigating to: {url}")
        
        self.driver.get(url)
        time.sleep(5)  # Wait for page to load
        
        # Find all animal attraction cards
        try:
            # Wait for attraction cards to load
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "attraction-card")))
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find all attraction cards
            attractions = []
            
            # Look for attraction links/cards
            # Adjust selectors based on actual HTML structure
            attraction_cards = soup.find_all('a', class_=lambda x: x and 'attraction' in x.lower())
            
            for card in attraction_cards:
                try:
                    title_elem = card.find(['h2', 'h3', 'h4'], class_=lambda x: x and any(s in str(x).lower() for s in ['title', 'name', 'heading']))
                    location_elem = card.find(class_=lambda x: x and 'location' in str(x).lower())
                    link = card.get('href', '')
                    
                    if title_elem:
                        attraction = {
                            'title': title_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True) if location_elem else '',
                            'link': f"https://www.oceanpark.com.hk{link}" if link.startswith('/') else link
                        }
                        attractions.append(attraction)
                        print(f"   ✓ Found: {attraction['title']} ({attraction['location']})")
                except Exception as e:
                    continue
            
            return attractions
            
        except Exception as e:
            print(f"❌ Error scraping attraction list: {e}")
            return []
    
    def scrape_attraction_detail(self, url, title):
        """Step 2: Scrape detailed information from an attraction page"""
        print(f"\n🔍 Scraping: {title}")
        print(f"   URL: {url}")
        
        self.driver.get(url)
        time.sleep(3)
        
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            data = {
                'name': title,
                'url': url,
                'location': '',
                'zone': '',
                'description': '',
                'animals': [],
                'highlights': [],
                'what_near_by': []
            }
            
            # Extract location (e.g., "Polar Adventure | Summit")
            location_elem = soup.find(class_=lambda x: x and 'location' in str(x).lower())
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                data['location'] = location_text
                if '|' in location_text:
                    parts = location_text.split('|')
                    data['zone'] = parts[-1].strip()
            
            # Extract main description
            desc_elem = soup.find('p', class_=lambda x: not x or 'description' in str(x).lower())
            if desc_elem:
                data['description'] = desc_elem.get_text(strip=True)
            
            # Extract "What's Near By" section
            near_by_section = soup.find(['h2', 'h3'], string=lambda x: x and "What's Near By" in str(x))
            if near_by_section:
                near_by_items = near_by_section.find_next_siblings(['div', 'ul', 'li'])
                for item in near_by_items[:5]:  # Limit to 5 items
                    item_text = item.get_text(strip=True)
                    if item_text:
                        data['what_near_by'].append(item_text)
            
            # Extract any list items that might be highlights or features
            list_items = soup.find_all('li')
            for li in list_items:
                text = li.get_text(strip=True)
                if text and len(text) > 10 and len(text) < 200:
                    data['highlights'].append(text)
            
            print(f"   ✅ Extracted data for {title}")
            return data
            
        except Exception as e:
            print(f"   ❌ Error scraping {title}: {e}")
            return None
    
    def save_to_json(self, filename='oceanpark_animals_raw.json'):
        """Save scraped data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.animal_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved to {filename}")
    
    def generate_python_dict(self, filename='oceanpark_animals_formatted.py'):
        """Generate formatted Python dictionary for park_knowledge.py"""
        output = "# Auto-generated from Ocean Park website\n"
        output += "# Generated on: " + time.strftime('%Y-%m-%d %H:%M:%S') + "\n\n"
        output += "PARK_ANIMAL_INFO = {\n"
        
        for key, data in self.animal_data.items():
            output += f"    '{key}': {{\n"
            output += f"        'name': '{data.get('name', '')}',\n"
            output += f"        'location': '{data.get('location', '')}',\n"
            output += f"        'zone': '{data.get('zone', '')}',\n"
            output += f"        'description': '''{data.get('description', '')}''',\n"
            output += f"        'highlights': {data.get('highlights', [])},\n"
            output += f"        'what_near_by': {data.get('what_near_by', [])},\n"
            output += f"        'url': '{data.get('url', '')}'\n"
            output += "    },\n"
        
        output += "}\n"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"💾 Generated Python dict: {filename}")
    
    def close(self):
        """Close browser"""
        self.driver.quit()
        print("\n👋 Browser closed")
    
    def run_full_scrape(self):
        """Run complete scraping process"""
        print("=" * 60)
        print("OCEAN PARK ANIMAL DATA SCRAPER")
        print("=" * 60)
        
        try:
            # Step 1: Get all attractions
            print("\n📋 STEP 1: Getting list of animal attractions...")
            attractions = self.scrape_attraction_list()
            print(f"✓ Found {len(attractions)} attractions")
            
            # Step 2: Scrape each attraction
            print("\n🔍 STEP 2: Scraping detailed information...")
            for i, attr in enumerate(attractions, 1):
                print(f"\n[{i}/{len(attractions)}]")
                detail = self.scrape_attraction_detail(attr['link'], attr['title'])
                if detail:
                    self.animal_data[attr['title'].lower().replace(' ', '_')] = detail
                
                # Polite delay between requests
                time.sleep(2)
            
            # Step 3: Save results
            print("\n💾 STEP 3: Saving results...")
            self.save_to_json()
            self.generate_python_dict()
            
            print("\n" + "=" * 60)
            print(f"✅ SUCCESS! Scraped {len(self.animal_data)} attractions")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
        finally:
            self.close()


# MANUAL DATA ENTRY HELPER
def manual_data_entry():
    """
    If scraping fails, use this to manually enter data
    Copy-paste text from Ocean Park website
    """
    print("=" * 60)
    print("MANUAL DATA ENTRY MODE")
    print("=" * 60)
    print("\nPaste the content from Ocean Park attraction page.")
    print("Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) when done.\n")
    
    attractions = {}
    
    while True:
        print("\n" + "-" * 40)
        name = input("Attraction name (or 'done' to finish): ").strip()
        if name.lower() == 'done':
            break
        
        print(f"\nEntering data for: {name}")
        print("Paste the description and details below (press Enter twice when done):\n")
        
        lines = []
        while True:
            line = input()
            if line == "":
                if lines and lines[-1] == "":
                    break
            lines.append(line)
        
        full_text = "\n".join(lines)
        
        location = input("Location (e.g., 'Polar Adventure | Summit'): ").strip()
        zone = location.split('|')[-1].strip() if '|' in location else ''
        
        attractions[name.lower().replace(' ', '_')] = {
            'name': name,
            'location': location,
            'zone': zone,
            'description': full_text,
            'raw_content': full_text
        }
        
        print(f"✓ Added {name}")
    
    # Save
    filename = 'oceanpark_manual_data.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(attractions, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved {len(attractions)} attractions to {filename}")


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 60)
    print("OCEAN PARK DATA SCRAPER")
    print("=" * 60)
    print("\n⚠️  NOTE: Web scraping Ocean Park often fails due to JavaScript.")
    print("    Manual entry (Option 2) is more reliable!\n")
    print("1. Auto-scrape (requires ChromeDriver - may fail)")
    print("2. Manual entry (copy-paste data) - RECOMMENDED")
    print("3. Use quick_add_attraction.py instead (EASIEST)")
    print("4. Exit")
    
    choice = input("\nChoice (1/2/3/4): ").strip()
    
    if choice == '1':
        if not SELENIUM_AVAILABLE:
            print("\n❌ Selenium not installed!")
            print("Install with: pip install -r scraper_requirements.txt")
            print("\n💡 Or use Option 2 instead!")
        else:
            try:
                scraper = OceanParkScraper()
                scraper.run_full_scrape()
            except Exception as e:
                print(f"\n❌ Scraping failed: {e}")
                print("\n💡 Use Option 2 (Manual Entry) instead!")
    elif choice == '2':
        manual_data_entry()
    elif choice == '3':
        print("\n💡 Run this command instead:")
        print("   python quick_add_attraction.py")
        print("\nIt's much easier - just paste data when prompted!")
    else:
        print("Exited.")

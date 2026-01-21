#!/usr/bin/env python3
"""
GreenAI Cloud B200 GPU Pricing Scraper
Extracts B200 pricing from top banner on greenai.cloud

GreenAI Cloud displays B200 pricing in a prominent banner at the top of their website.

Reference: https://greenai.cloud/
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional


class GreenAIB200Scraper:
    """Scraper for GreenAI Cloud B200 GPU pricing"""
    
    def __init__(self):
        self.name = "GreenAI Cloud"
        self.base_url = "https://greenai.cloud/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices from GreenAI Cloud"""
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)
        
        b200_prices = {}
        
        # Try multiple methods
        methods = [
            ("Banner Scraping (HTML)", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]
        
        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices and self._validate_prices(prices):
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    break  # Return on first successful method
                else:
                    print(f"   ❌ No valid prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                continue
        
        if not b200_prices:
            print("\n❌ All live methods failed - no fallback data (live data only mode)")
            return {}
        
        print(f"\n✅ Final extraction: {len(b200_prices)} B200 price variants")
        return b200_prices
    
    def _validate_prices(self, prices: Dict[str, str]) -> bool:
        """Validate that prices are in a reasonable range for B200 GPUs"""
        if not prices:
            return False
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            try:
                price_match = re.search(r'([0-9.]+)', price_str.replace(',', '.'))
                if price_match:
                    price = float(price_match.group(1))
                    # GreenAI pricing is very competitive (around $3-$4/GPU/hr)
                    if 2 < price < 10:
                        return True
            except:
                continue
        return False
    
    def _try_pricing_page(self) -> Dict[str, str]:
        """Scrape the homepage banner for B200 prices"""
        b200_prices = {}
        
        try:
            print(f"    Trying: {self.base_url}")
            response = requests.get(self.base_url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text_content = soup.get_text()
                html_content = str(soup)
                
                print(f"      Content length: {len(text_content)}")
                
                # Check if page contains B200 data
                if 'B200' not in text_content and 'b200' not in text_content.lower():
                    print(f"      ⚠️  No B200 content found")
                    return b200_prices
                
                print(f"      ✓ Found B200 content")
                
                # Extract from banner
                found_prices = self._extract_from_banner(soup, html_content)
                if found_prices:
                    b200_prices.update(found_prices)
                    return b200_prices
                    
            else:
                print(f"      Status {response.status_code}")
                
        except Exception as e:
            print(f"      Error: {str(e)[:50]}...")
        
        return b200_prices
    
    def _extract_from_banner(self, soup: BeautifulSoup, html_content: str) -> Dict[str, str]:
        """Extract B200 prices from the top banner"""
        prices = {}
        
        # Banner text format: "Interested in B200 from NVIDIA ? – rates starting at 3,75 USD/GPU/H"
        # The price uses European format with comma (3,75) instead of period (3.75)
        
        # Method 1: Look for elements with elementor-heading-title class
        banner_elements = soup.find_all('span', class_='elementor-heading-title')
        print(f"      Found {len(banner_elements)} elementor-heading-title elements")
        
        for element in banner_elements:
            element_text = element.get_text()
            
            if 'B200' in element_text and 'USD/GPU/H' in element_text:
                print(f"         Banner text: {element_text[:150]}")
                
                # Extract price with European format (comma as decimal separator)
                # Pattern: "rates starting at 3,75 USD/GPU/H"
                price_match = re.search(r'rates starting at\s+([0-9]+[,.]?[0-9]*)\s*USD/GPU/H', element_text, re.IGNORECASE)
                
                if price_match:
                    price_str = price_match.group(1).replace(',', '.')  # Convert European to standard format
                    try:
                        price = float(price_str)
                        if 2 < price < 10:
                            variant_name = "B200 (GreenAI Cloud)"
                            prices[variant_name] = f"${price:.2f}/hr"
                            print(f"        Banner ✓ {variant_name} = ${price:.2f}/hr")
                    except ValueError:
                        continue
        
        # Method 2: Search text content with regex
        if not prices:
            print("      Trying text pattern search...")
            # Pattern for European format: "3,75 USD/GPU/H"
            price_patterns = [
                r'B200.*?rates starting at\s+([0-9]+[,.]?[0-9]*)\s*USD/GPU/H',
                r'B200.*?([0-9]+[,.]?[0-9]*)\s*USD/GPU/H',
            ]
            
            for pattern in price_patterns:
                matches = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if matches:
                    price_str = matches.group(1).replace(',', '.')
                    try:
                        price = float(price_str)
                        if 2 < price < 10:
                            variant_name = "B200 (GreenAI Cloud)"
                            prices[variant_name] = f"${price:.2f}/hr"
                            print(f"        Pattern ✓ {variant_name} = ${price:.2f}/hr")
                            break
                    except ValueError:
                        continue
        
        return prices
   
    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing from GreenAI Cloud"""
        b200_prices = {}
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.common.exceptions import WebDriverException
            
            print("    Setting up Selenium WebDriver...")
            
            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Initialize the driver
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                print("    Loading pricing page...")
                driver.get(self.base_url)
                
                # Wait for page to load
                print("    Waiting for dynamic content to load...")
                time.sleep(5)  # Wait for JavaScript to render banner
                
                # Get the page source after JavaScript has loaded
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                text_content = soup.get_text()
                
                print(f"    ✓ Page loaded, content length: {len(text_content)}")
                
                # Extract prices using same method
                found_prices = self._extract_from_banner(soup, page_source)
                if found_prices:
                    b200_prices.update(found_prices)
                
            finally:
                driver.quit()
                print("    WebDriver closed")
                
        except ImportError:
            print("      ⚠️  Selenium not installed. Run: pip install selenium")
        except WebDriverException as e:
            print(f"      ⚠️  Selenium WebDriver error: {str(e)[:100]}")
        except Exception as e:
            print(f"      ⚠️  Error: {str(e)[:100]}")
        
        return b200_prices
    
    def _get_known_pricing(self) -> Dict[str, str]:
        """
        Get known GreenAI Cloud B200 pricing as fallback.
        Based on their website banner.
        
        Reference: https://greenai.cloud/
        
        B200: 3.75 USD per GPU per hour (displayed as 3,75 USD/GPU/H)
        """
        print("    Using known GreenAI Cloud B200 pricing data...")
        
        known_prices = {
            'B200 (GreenAI Cloud)': '$3.75/hr',
        }
        
        print(f"    ✅ Using {len(known_prices)} known pricing entries")
        return known_prices
    
    def save_to_json(self, prices: Dict[str, str], filename: str = "greenai_b200_prices.json") -> bool:
        """Save results to a JSON file"""
        try:
            output_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": self.name,
                "prices": prices,
                "notes": {
                    "gpu_model": "NVIDIA B200",
                    "pricing_type": "on-demand per-GPU-hour",
                    "source": "https://greenai.cloud/",
                    "location": "Sweden (EU data protection compliant)"
                }
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results saved to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to file: {str(e)}")
            return False


def main():
    """Main function to run the GreenAI Cloud B200 scraper"""
    print("🚀 GreenAI Cloud B200 GPU Pricing Scraper")
    print("=" * 80)
    print("Note: GreenAI Cloud displays B200 pricing in top banner")
    print("=" * 80)
    
    scraper = GreenAIB200Scraper()
    
    start_time = time.time()
    prices = scraper.get_b200_prices()
    end_time = time.time()
    
    print(f"\n⏱️  Scraping completed in {end_time - start_time:.2f} seconds")
    
    # Display results
    if prices and 'Error' not in str(prices):
        print(f"\n✅ Successfully extracted {len(prices)} B200 price entries:\n")
        
        for variant, price in sorted(prices.items()):
            print(f"  • {variant:50s} {price}")
        
        # Save results to JSON
        scraper.save_to_json(prices)
    else:
        print("\n❌ No valid pricing data found")


if __name__ == "__main__":
    main()

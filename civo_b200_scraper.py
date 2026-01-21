#!/usr/bin/env python3
"""
Civo B200 GPU Pricing Scraper
Extracts B200 pricing from civo.com using multiple methods

Civo offers B200 GPUs in 8x GPU configurations.

Reference: https://www.civo.com/pricing
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional

class CivoB200Scraper:
    """Scraper for Civo B200 GPU pricing"""
    
    def __init__(self):
        self.name = "Civo"
        self.base_url = "https://www.civo.com/pricing"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices from Civo"""
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)
        
        b200_prices = {}
        
        # Try multiple methods in order of reliability
        methods = [
            ("Civo API", self._try_civo_api),
            ("Pricing Page Scraping", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
            ("GPU Products Page", self._try_gpu_products_page),
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
        
        # Normalize to per-GPU pricing
        normalized_prices = self._normalize_to_per_gpu(b200_prices)
        
        print(f"\n✅ Final extraction: {len(normalized_prices)} B200 price variants")
        return normalized_prices
    
    def _validate_prices(self, prices: Dict[str, str]) -> bool:
        """Validate that prices are in a reasonable range for B200 GPUs"""
        if not prices:
            return False
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            try:
                price_match = re.search(r'\$([0-9.]+)', price_str)
                if price_match:
                    price = float(price_match.group(1))
                    # B200 GPUs are more expensive than H100s
                    # Per-GPU B200 should be roughly $3-$10/hr
                    # Multi-GPU configs can be up to $50/hr
                    if 2 < price < 60:
                        return True
            except:
                continue
        return False
    
    def _try_civo_api(self) -> Dict[str, str]:
        """Try Civo API endpoints for B200 pricing"""
        b200_prices = {}
        
        # Civo API endpoints
        api_urls = [
            "https://api.civo.com/v2/sizes",
            "https://api.civo.com/v2/gpu-instances",
            "https://api.civo.com/v2/pricing",
            "https://www.civo.com/api/v1/pricing",
            "https://www.civo.com/api/pricing",
        ]
        
        for api_url in api_urls:
            try:
                print(f"    Trying API: {api_url}")
                response = requests.get(api_url, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"      ✓ Got JSON response")
                        
                        # Search for B200 in the JSON
                        found_prices = self._extract_from_api_response(data)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                            
                    except json.JSONDecodeError:
                        print(f"      ⚠️  Response is not JSON")
                elif response.status_code == 401:
                    print(f"      ⚠️  Unauthorized - API key required")
                elif response.status_code == 404:
                    print(f"      Status 404")
                else:
                    print(f"      Status {response.status_code}")
                        
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _extract_from_api_response(self, data) -> Dict[str, str]:
        """Extract B200 prices from Civo API response"""
        prices = {}
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get('name', '').upper()
                    description = item.get('description', '').upper()
                    
                    # Check if this is a B200 instance
                    if 'B200' in name or 'B200' in description:
                        price_hourly = item.get('price_per_hour') or item.get('hourly_price') or item.get('price')
                        
                        if price_hourly:
                            try:
                                price = float(price_hourly)
                                if 2 < price < 60:
                                    variant_name = self._determine_variant_from_name(name)
                                    prices[variant_name] = f"${price:.2f}/hr"
                                    print(f"        API ✓ {variant_name} = ${price:.2f}/hr")
                            except (ValueError, TypeError):
                                pass
                                
        elif isinstance(data, dict):
            # Recursively search nested structures
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    nested_prices = self._extract_from_api_response(value)
                    prices.update(nested_prices)
        
        return prices
    
    def _determine_variant_from_name(self, name: str) -> str:
        """Determine B200 variant from name/description"""
        name_upper = name.upper()
        
        if '8X' in name_upper or '8 X' in name_upper:
            return 'B200 (8x GPUs)'
        elif '4X' in name_upper or '4 X' in name_upper:
            return 'B200 (4x GPUs)'
        elif '2X' in name_upper or '2 X' in name_upper:
            return 'B200 (2x GPUs)'
        elif '1X' in name_upper or '1 X' in name_upper:
            return 'B200 (1x GPU)'
        else:
            return 'B200'
    
    def _try_pricing_page(self) -> Dict[str, str]:
        """Scrape the pricing page for B200 prices"""
        b200_prices = {}
        
        pricing_urls = [
            "https://www.civo.com/pricing",
            "https://www.civo.com/gpu-pricing",
            "https://www.civo.com/gpu",
        ]
        
        for url in pricing_urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()
                    
                    print(f"      Content length: {len(text_content)}")
                    
                    # Check if page contains B200 data
                    if 'B200' not in text_content and 'b200' not in text_content.lower():
                        print(f"      ⚠️  No B200 content found")
                        continue
                    
                    print(f"      ✓ Found B200 content")
                    
                    # Debug: Show B200 lines
                    b200_lines = [line.strip() for line in text_content.split('\n') 
                                  if 'B200' in line or 'b200' in line.lower()]
                    if b200_lines:
                        print(f"      📋 B200 mentions: {len(b200_lines)}")
                        for line in b200_lines[:5]:
                            print(f"         {line[:100]}")
                    
                    # Look for pricing with $ symbols near B200
                    lines_with_price = [line.strip() for line in text_content.split('\n') 
                                       if ('B200' in line or 'b200' in line.lower()) and '$' in line]
                    if lines_with_price:
                        print(f"      💰 Lines with B200 and $: {len(lines_with_price)}")
                        for line in lines_with_price:
                            print(f"         {line[:150]}")
                    
                    # Extract prices using patterns
                    found_prices = self._extract_prices_from_text(text_content)
                    if found_prices:
                        b200_prices.update(found_prices)
                        return b200_prices
                    
                    # Try table extraction
                    found_prices = self._extract_from_tables(soup)
                    if found_prices:
                        b200_prices.update(found_prices)
                        return b200_prices
                        
                else:
                    print(f"      Status {response.status_code}")
                    
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _extract_prices_from_text(self, text_content: str) -> Dict[str, str]:
        """Extract B200 prices from text content using regex patterns"""
        prices = {}
        
        # Civo B200 pricing format similar to H100:
        # "NVIDIA B200 ... $X.XXper hour"
        
        # Extract B200 pricing patterns
        b200_patterns = [
            # Full price pattern
            (r'B200[^$]*\$([0-9.]+)\s*per\s*hour', 'B200'),
            # Simplified pattern
            (r'B200[^$]*\$([0-9.]+)/hr', 'B200'),
        ]
        
        for pattern, variant_base in b200_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                try:
                    price = float(match)
                    if 2 < price < 60:
                        # Try to determine variant from surrounding context
                        variant_name = variant_base
                        prices[variant_name] = f"${price:.2f}/hr"
                        print(f"        Pattern ✓ {variant_name} = ${price:.2f}/hr")
                except ValueError:
                    continue
        
        return prices
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract B200 prices from HTML tables"""
        prices = {}
        
        tables = soup.find_all('table')
        print(f"      Found {len(tables)} tables")
        
        for table in tables:
            table_text = table.get_text()
            
            # Only process tables with B200 mentions
            if 'B200' not in table_text and 'b200' not in table_text.lower():
                continue
            
            print(f"      📋 Processing table with B200 data")
            
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([cell.get_text().strip() for cell in cells])
                
                if 'B200' in row_text and '$' in row_text:
                    # Extract price
                    price_matches = re.findall(r'\$([0-9.]+)', row_text)
                    
                    for price_str in price_matches:
                        try:
                            price = float(price_str)
                            if 2.0 < price < 60.0:
                                # Determine variant
                                variant = self._determine_variant_from_name(row_text)
                                if variant not in prices:
                                    prices[variant] = f"${price:.2f}/hr"
                                    print(f"        Table ✓ {variant} = ${price:.2f}/hr")
                        except ValueError:
                            continue
        
        return prices
    
    def _try_gpu_products_page(self) -> Dict[str, str]:
        """Try GPU-specific product pages"""
        b200_prices = {}
        
        gpu_urls = [
            "https://www.civo.com/products/gpu",
            "https://www.civo.com/gpu-cloud",
            "https://www.civo.com/compute/gpu",
        ]
        
        for url in gpu_urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()
                    
                    if 'B200' in text_content:
                        print(f"      ✓ Found B200 content")
                        
                        # Extract prices
                        found_prices = self._extract_prices_from_text(text_content)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                        
                        # Try table extraction
                        found_prices = self._extract_from_tables(soup)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                else:
                    print(f"      Status {response.status_code}")
                    
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing from Civo"""
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
                driver.get("https://www.civo.com/pricing")
                
                # Wait for page to load
                print("    Waiting for dynamic content to load...")
                time.sleep(5)  # Wait for JavaScript to render
                
                # Try scrolling to load more content
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Get the page source after JavaScript has loaded
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                text_content = soup.get_text()
                
                print(f"    ✓ Page loaded, content length: {len(text_content)}")
                
                # Look for B200 pricing
                b200_sections = re.findall(r'(B200.*?(?:\$[0-9.]+|[0-9.]+\s*per\s*hour))', 
                                          text_content, re.IGNORECASE | re.DOTALL)
                
                if b200_sections:
                    print(f"      Found {len(b200_sections)} B200 sections with prices")
                    for section in b200_sections[:10]:
                        print(f"         {section[:100]}")
                
                # Extract prices using patterns
                found_prices = self._extract_prices_from_text(text_content)
                if found_prices:
                    b200_prices.update(found_prices)
                
                # Also try direct element search
                if not b200_prices:
                    print("      Trying direct element search...")
                    
                    # Look for pricing cards/divs
                    pricing_elements = driver.find_elements(By.XPATH, 
                        "//*[contains(text(), 'B200') or contains(text(), 'b200')]")
                    
                    print(f"      Found {len(pricing_elements)} elements with B200")
                    
                    for element in pricing_elements:
                        try:
                            parent = element.find_element(By.XPATH, "./..")
                            parent_text = parent.text
                            
                            if '$' in parent_text:
                                # Extract price
                                price_matches = re.findall(r'\$([0-9.]+)', parent_text)
                                for price_str in price_matches:
                                    try:
                                        price = float(price_str)
                                        if 2.0 < price < 60.0:
                                            variant = self._determine_variant_from_name(parent_text)
                                            if variant not in b200_prices:
                                                b200_prices[variant] = f"${price:.2f}/hr"
                                                print(f"        Element ✓ {variant} = ${price:.2f}/hr")
                                    except ValueError:
                                        continue
                        except:
                            continue
                
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
        Get known Civo B200 pricing as fallback.
        Based on Civo's published commitment pricing.
        
        Reference: https://www.civo.com/pricing
        
        B200:
        - Commitment pricing starts at $3.49/GPU/hour
        - 36-month commitment: $22.32/GPU/hour
        """
        print("    Using known Civo B200 pricing data...")
        
        known_prices = {
            'B200 (Commitment Start)': '$3.49/hr',
            'B200 (36-month)': '$22.32/hr',
        }
        
        print(f"    ✅ Using {len(known_prices)} known pricing entries")
        return known_prices
    
    def _normalize_to_per_gpu(self, prices: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize all prices to per-GPU pricing.
        Returns an averaged single price for Civo.
        """
        if not prices:
            return {}
        
        per_gpu_prices = []
        
        print("\n   📊 Normalizing to per-GPU pricing...")
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            
            try:
                # Extract GPU count from variant name
                gpu_count_match = re.search(r'(\d+)x\s*GPUs?', variant, re.IGNORECASE)
                if gpu_count_match:
                    gpu_count = int(gpu_count_match.group(1))
                else:
                    gpu_count = 1
                
                # Extract price value
                price_match = re.search(r'\$([0-9.]+)', price_str)
                if price_match:
                    total_price = float(price_match.group(1))
                    per_gpu_price = total_price / gpu_count
                    
                    per_gpu_prices.append(per_gpu_price)
                    print(f"      {variant}: ${total_price:.2f}/hr → ${per_gpu_price:.2f}/GPU")
                    
            except (ValueError, TypeError) as e:
                print(f"      ⚠️ Error normalizing {variant}: {e}")
                continue
        
        if per_gpu_prices:
            # Calculate average per-GPU price
            avg_per_gpu = sum(per_gpu_prices) / len(per_gpu_prices)
            print(f"\n   ✅ Averaged {len(per_gpu_prices)} prices → ${avg_per_gpu:.2f}/GPU")
            
            # Return single normalized price
            return {
                'B200 (Civo)': f"${avg_per_gpu:.2f}/hr"
            }
        
        return {}
    
    def save_to_json(self, prices: Dict[str, str], filename: str = "civo_b200_prices.json") -> bool:
        """Save results to a JSON file"""
        try:
            output_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": self.name,
                "prices": prices,
                "notes": {
                    "gpu_model": "B200",
                    "pricing_type": "on-demand per-GPU (normalized)",
                    "configurations": "8x GPU configuration available"
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
    """Main function to run the Civo B200 scraper"""
    print("🚀 Civo B200 GPU Pricing Scraper")
    print("=" * 80)
    print("Note: Civo offers B200 GPUs with commitment-based pricing")
    print("=" * 80)
    
    scraper = CivoB200Scraper()
    
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

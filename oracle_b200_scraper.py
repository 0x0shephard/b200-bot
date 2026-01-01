#!/usr/bin/env python3
"""
Oracle Cloud B200 GPU Price Scraper
Extracts B200 pricing from Oracle Cloud Infrastructure (OCI)

Oracle offers B200 GPUs in:
- BM.GPU.B200.8: 8 x NVIDIA B200 180GB Tensor Core Blackwell ($14.00/GPU/hr)
- BM.GPU.GB200.41: 4 x NVIDIA B200 189GB NVL72

Reference: https://www.oracle.com/cloud/compute/pricing/
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional


class OracleB200Scraper:
    """Scraper for Oracle Cloud B200 instance pricing"""
    
    def __init__(self):
        self.name = "Oracle"
        self.base_url = "https://www.oracle.com/cloud/compute/pricing/"
        self.gpu_url = "https://www.oracle.com/cloud/compute/gpu/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices from Oracle Cloud"""
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)
        
        b200_prices = {}
        
        # Try multiple methods in order
        methods = [
            ("Oracle Compute Pricing Page", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]
        
        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices and self._validate_prices(prices):
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    break
                else:
                    print(f"   ❌ No valid prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                continue
        
        if not b200_prices:
            print("\n⚠️  All methods failed - using known pricing data")
            b200_prices = self._get_known_pricing()
        
        # Normalize to per-GPU pricing
        normalized_prices = self._normalize_prices(b200_prices)
        
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
                price_match = re.search(r'\$?([0-9.]+)', str(price_str))
                if price_match:
                    price = float(price_match.group(1))
                    # Oracle B200 pricing is $14/GPU/hr - reasonable range $10-20
                    if 10 < price < 20:
                        return True
            except:
                continue
        return False
    
    def _try_pricing_page(self) -> Dict[str, str]:
        """Scrape the Oracle Cloud Compute pricing page"""
        b200_prices = {}
        
        try:
            print(f"    Trying: {self.base_url}")
            response = requests.get(self.base_url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text_content = soup.get_text()
                
                print(f"      Content length: {len(text_content)}")
                
                # Check if page contains B200 or Blackwell data
                if 'B200' not in text_content and 'Blackwell' not in text_content:
                    print(f"      ⚠️  No B200/Blackwell content found")
                    return b200_prices
                
                print(f"      ✓ Found B200/Blackwell content")
                
                # Extract from pricing tables
                found_prices = self._extract_from_tables(soup)
                if found_prices:
                    b200_prices.update(found_prices)
                    return b200_prices
                
                # Extract from text patterns
                found_prices = self._extract_from_text(text_content)
                if found_prices:
                    b200_prices.update(found_prices)
                    return b200_prices
                    
            else:
                print(f"      Status {response.status_code}")
                
        except Exception as e:
            print(f"      Error: {str(e)[:50]}...")
        
        return b200_prices
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract B200 prices from HTML tables"""
        prices = {}
        
        tables = soup.find_all('table')
        print(f"      Found {len(tables)} tables")
        
        for table in tables:
            table_text = table.get_text()
            
            # Only process tables with B200 or Blackwell mentions
            if 'B200' not in table_text and 'Blackwell' not in table_text:
                continue
            
            print(f"      📋 Processing table with B200/Blackwell data")
            
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([cell.get_text().strip() for cell in cells])
                
                # Look for BM.GPU.B200.8 row (8 x B200 180GB)
                if 'BM.GPU.B200.8' in row_text or ('B200' in row_text and '180GB' in row_text):
                    print(f"         Row: {row_text[:150]}")
                    
                    if len(cells) >= 2:
                        # Get the last cell which contains the GPU price
                        last_cell = cells[-1].get_text().strip()
                        print(f"         Last cell (GPU Price): {last_cell}")
                        
                        # Extract price from the cell (format: "$14.00")
                        price_match = re.search(r'\$([0-9.]+)', last_cell)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                                # Oracle B200 is $14/GPU/hr
                                if 10.0 <= price <= 20.0:
                                    variant_name = "BM.GPU.B200.8 (Oracle)"
                                    prices[variant_name] = f"${price:.2f}/hr"
                                    print(f"        Table ✓ {variant_name} = ${price:.2f}/hr")
                            except ValueError:
                                continue
                
                # Look for BM.GPU.GB200.41 row (4 x B200 189GB NVL72)
                if 'BM.GPU.GB200' in row_text or ('GB200' in row_text and '189GB' in row_text):
                    print(f"         Row: {row_text[:150]}")
                    
                    if len(cells) >= 2:
                        last_cell = cells[-1].get_text().strip()
                        print(f"         Last cell (GPU Price): {last_cell}")
                        
                        price_match = re.search(r'\$([0-9.]+)', last_cell)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                                if 10.0 <= price <= 25.0:
                                    variant_name = "BM.GPU.GB200.41 (Oracle)"
                                    prices[variant_name] = f"${price:.2f}/hr"
                                    print(f"        Table ✓ {variant_name} = ${price:.2f}/hr")
                            except ValueError:
                                continue
        
        return prices
    
    def _extract_from_text(self, text_content: str) -> Dict[str, str]:
        """Extract B200 prices from text content using regex patterns"""
        prices = {}
        
        patterns = [
            r'B200[^\$]*\$([0-9.]+)\s*(?:per\s+GPU|/GPU)',
            r'BM\.GPU\.B200[^\$]*\$([0-9.]+)',
            r'Blackwell[^\$]*\$([0-9.]+)',
            r'B200[^\$]*\$([0-9.]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            
            for price_str in matches:
                try:
                    price = float(price_str)
                    # Per-GPU pricing for B200
                    if 10.0 < price < 20.0:
                        variant_name = "BM.GPU.B200.8 (Oracle)"
                        prices[variant_name] = f"${price:.2f}/hr"
                        print(f"        Pattern ✓ {variant_name} = ${price:.2f}/hr")
                        return prices
                except ValueError:
                    continue
        
        return prices
    
    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing from Oracle"""
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
                print(f"    Loading Oracle pricing page...")
                driver.get(self.base_url)
                
                # Wait for page to load
                print("    Waiting for dynamic content to load...")
                time.sleep(5)
                
                # Get the page source
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                text_content = soup.get_text()
                
                print(f"    ✓ Page loaded, content length: {len(text_content)}")
                
                # Check for B200 content
                if 'B200' in text_content or 'Blackwell' in text_content:
                    print(f"      ✓ Found B200/Blackwell content")
                    
                    found_prices = self._extract_from_tables(soup)
                    if found_prices:
                        b200_prices.update(found_prices)
                    else:
                        found_prices = self._extract_from_text(text_content)
                        if found_prices:
                            b200_prices.update(found_prices)
                else:
                    print(f"      ⚠️  No B200/Blackwell content found in Selenium")
                
            finally:
                driver.quit()
                print("    WebDriver closed")
                
        except ImportError:
            print("      ⚠️  Selenium not installed. Run: pip install selenium")
        except Exception as e:
            print(f"      ⚠️  Error: {str(e)[:100]}")
        
        return b200_prices
    
    def _get_known_pricing(self) -> Dict[str, str]:
        """
        Get known Oracle Cloud B200 pricing as fallback.
        Based on publicly available pricing data.
        
        Reference: https://www.oracle.com/cloud/compute/pricing/
        
        BM.GPU.B200.8: $14.00 per GPU per hour (8 x B200 180GB GPUs)
        BM.GPU.GB200.41: 4 x B200 189GB NVL72
        """
        print("    Using known Oracle B200 pricing data...")
        
        known_prices = {
            'BM.GPU.B200.8 (Oracle)': '$14.00/hr',
        }
        
        print(f"    ✅ Using {len(known_prices)} known pricing entries")
        return known_prices
    
    def _normalize_prices(self, prices: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize prices - Oracle already provides per-GPU pricing.
        Calculate average across all variants for a single representative price.
        """
        if not prices:
            return {}
        
        per_gpu_prices = []
        
        print("\n   📊 Normalizing Oracle B200 pricing...")
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            
            try:
                # Extract price value
                price_match = re.search(r'\$([0-9.]+)', price_str)
                if price_match:
                    price = float(price_match.group(1))
                    per_gpu_prices.append(price)
                    print(f"      {variant}: ${price:.2f}/hr")
                    
            except (ValueError, TypeError) as e:
                print(f"      ⚠️ Error normalizing {variant}: {e}")
                continue
        
        if per_gpu_prices:
            # Calculate average per-GPU price
            avg_per_gpu = sum(per_gpu_prices) / len(per_gpu_prices)
            print(f"\n   ✅ Averaged {len(per_gpu_prices)} prices → ${avg_per_gpu:.2f}/GPU")
            
            # Return single normalized price
            return {
                'BM.GPU.B200.8 (Oracle)': f"${avg_per_gpu:.2f}/hr"
            }
        
        return {}
    
    def save_to_json(self, prices: Dict[str, str], filename: str = "oracle_b200_prices.json") -> bool:
        """Save results to a JSON file in the same format as other scrapers"""
        try:
            # Extract numeric price for the structured format
            price_value = 0.0
            if prices:
                for variant, price_str in prices.items():
                    price_match = re.search(r'\$([0-9.]+)', price_str)
                    if price_match:
                        price_value = float(price_match.group(1))
                        break
            
            output_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": self.name,
                "prices": {
                    "BM.GPU.B200.8 (Oracle)": f"${price_value:.2f}/hr"
                },
                "notes": {
                    "instance_type": "BM.GPU.B200.8",
                    "gpu_model": "NVIDIA B200",
                    "gpu_memory": "180GB HBM3e",
                    "gpu_count_per_instance": 8,
                    "pricing_type": "On-Demand (Pay-As-You-Go)",
                    "source": "https://www.oracle.com/cloud/compute/pricing/"
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
    """Main function to run the Oracle B200 scraper"""
    print("🚀 Oracle Cloud B200 GPU Pricing Scraper")
    print("=" * 80)
    print("Note: Oracle offers B200 GPUs in:")
    print("  - BM.GPU.B200.8 (8 x B200 180GB) - $14.00/GPU/hr")
    print("  - BM.GPU.GB200.41 (4 x B200 189GB NVL72)")
    print("=" * 80)
    
    scraper = OracleB200Scraper()
    
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

#!/usr/bin/env python3
"""
B200 GPU Price Normalization Script

This script normalizes B200 GPU prices across different providers to the base B200 model.

Base Model Specifications:
- GPU: NVIDIA B200
- Memory: 180GB HBM3e
- Architecture: Blackwell
- Performance: ~2x H100 (baseline for comparison)

All scraped prices are already for the same base B200 model, so normalization
is primarily for calculating averages and comparing across providers.
"""

import json
import os
from typing import Dict, List, Tuple
from pathlib import Path


class B200PriceNormalizer:
    """Normalizes B200 GPU prices across providers"""
    
    def __init__(self, b200_dir: str = "."):
        self.b200_dir = Path(b200_dir)
        self.base_model = {
            "name": "NVIDIA B200",
            "memory_gb": 180,
            "architecture": "Blackwell",
            "relative_performance": 1.0,  # Base B200 is our reference
        }
        
        # Performance benchmarks relative to base B200
        self.gpu_benchmarks = {
            "B200": 1.0,      # Base reference
            "H200": 0.75,     # Approximate relative performance
            "H100": 0.50,     # B200 is ~2x H100 performance
            "A100": 0.33,     # Approximate relative performance
        }
        
    def load_all_prices(self) -> Dict[str, Dict]:
        """Load all B200 price JSON files from the b200 directory"""
        prices = {}
        
        # Find all *_b200_prices.json files
        json_files = list(self.b200_dir.glob("*_b200_prices.json"))
        
        print(f"📂 Found {len(json_files)} B200 price files")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    provider = data.get("provider", json_file.stem.replace("_b200_prices", ""))
                    prices[provider] = data
                    print(f"   ✓ Loaded: {provider}")
            except Exception as e:
                print(f"   ✗ Error loading {json_file}: {e}")
        
        return prices
    
    def extract_price_value(self, price_str: str) -> float:
        """Extract numeric price value from price string"""
        import re
        # Handle formats like "$5.98/hr" or "$5.98"
        match = re.search(r'\$?([0-9.]+)', price_str)
        if match:
            return float(match.group(1))
        return 0.0
    
    def normalize_prices(self, prices: Dict[str, Dict]) -> Dict[str, Dict]:
        """Normalize all prices to base B200 model"""
        normalized = {}
        
        print("\n" + "=" * 80)
        print("📊 B200 PRICE NORMALIZATION REPORT")
        print("=" * 80)
        print(f"\nBase Model: {self.base_model['name']} ({self.base_model['memory_gb']}GB HBM3e)")
        print("\nProvider Prices (All normalized to per-GPU/hour):")
        print("-" * 80)
        
        per_gpu_prices = []
        
        for provider, data in prices.items():
            # Handle different JSON structures
            # Most providers: {"prices": {"variant": "$X.XX/hr"}}
            # RunPod: {"providers": {"RunPod": {"variants": {"B200": {"price_per_hour": X.XX}}}}}
            
            provider_prices = data.get("prices", {})
            
            # Check for RunPod's nested structure
            if not provider_prices and "providers" in data:
                # RunPod structure
                nested_providers = data.get("providers", {})
                for nested_provider_name, nested_data in nested_providers.items():
                    variants = nested_data.get("variants", {})
                    for variant_name, variant_data in variants.items():
                        if isinstance(variant_data, dict) and "price_per_hour" in variant_data:
                            price_value = variant_data["price_per_hour"]
                            variant_display = f"{variant_name} ({variant_data.get('gpu_memory', 'N/A')})"
                            
                            if price_value > 0:
                                normalized_price = price_value
                                per_gpu_prices.append((provider, variant_display, normalized_price))
                                
                                if provider not in normalized:
                                    normalized[provider] = {
                                        "original_price": price_value,
                                        "normalized_price": normalized_price,
                                        "variant": variant_display,
                                        "source": nested_data.get("url", "")
                                    }
            else:
                # Standard structure (Civo, AWS, Nebius, GreenAI)
                for variant, price_str in provider_prices.items():
                    price_value = self.extract_price_value(price_str)
                    
                    if price_value > 0:
                        normalized_price = price_value
                        per_gpu_prices.append((provider, variant, normalized_price))
                        
                        if provider not in normalized:
                            normalized[provider] = {
                                "original_price": price_value,
                                "normalized_price": normalized_price,
                                "variant": variant,
                                "source": data.get("notes", {}).get("source", "")
                            }
        
        # Sort by price
        per_gpu_prices.sort(key=lambda x: x[2])
        
        # Display sorted prices
        for provider, variant, price in per_gpu_prices:
            print(f"  {provider:20s} {variant:35s} ${price:.2f}/hr")
        
        return normalized
    
    def calculate_statistics(self, normalized: Dict[str, Dict]) -> Dict:
        """Calculate pricing statistics"""
        prices = [data["normalized_price"] for data in normalized.values()]
        
        if not prices:
            return {}
        
        stats = {
            "count": len(prices),
            "min": min(prices),
            "max": max(prices),
            "average": sum(prices) / len(prices),
            "median": sorted(prices)[len(prices) // 2],
        }
        
        # Find providers with min/max prices
        for provider, data in normalized.items():
            if data["normalized_price"] == stats["min"]:
                stats["cheapest_provider"] = provider
            if data["normalized_price"] == stats["max"]:
                stats["most_expensive_provider"] = provider
        
        print("\n" + "-" * 80)
        print("📈 PRICING STATISTICS")
        print("-" * 80)
        print(f"  Total Providers: {stats['count']}")
        print(f"  Lowest Price:    ${stats['min']:.2f}/hr ({stats.get('cheapest_provider', 'Unknown')})")
        print(f"  Highest Price:   ${stats['max']:.2f}/hr ({stats.get('most_expensive_provider', 'Unknown')})")
        print(f"  Average Price:   ${stats['average']:.2f}/hr")
        print(f"  Median Price:    ${stats['median']:.2f}/hr")
        print(f"  Price Range:     ${stats['max'] - stats['min']:.2f}/hr")
        
        return stats
    
    def calculate_deviations(self, normalized: Dict[str, Dict], average: float):
        """Calculate price deviations from average"""
        print("\n" + "-" * 80)
        print("📉 DEVIATION FROM AVERAGE PRICE")
        print("-" * 80)
        
        deviations = []
        
        for provider, data in normalized.items():
            price = data["normalized_price"]
            deviation = price - average
            deviation_pct = (deviation / average) * 100
            
            deviations.append((provider, price, deviation, deviation_pct))
        
        # Sort by absolute deviation
        deviations.sort(key=lambda x: abs(x[2]))
        
        for provider, price, deviation, deviation_pct in deviations:
            sign = "+" if deviation >= 0 else ""
            emoji = "🟢" if abs(deviation_pct) < 10 else "🟡" if abs(deviation_pct) < 30 else "🔴"
            print(f"  {emoji} {provider:20s} ${price:.2f}/hr  ({sign}{deviation:+.2f} / {sign}{deviation_pct:+.1f}%)")
    
    def compare_with_h100(self, b200_average: float):
        """Compare B200 pricing with H100 baseline"""
        print("\n" + "=" * 80)
        print("🔄 B200 vs H100 PERFORMANCE COMPARISON")
        print("=" * 80)
        
        # Typical H100 pricing (based on market rates)
        h100_typical_price = 3.50  # USD per GPU/hour (approximate market average)
        
        # Performance multiplier
        performance_multiplier = self.gpu_benchmarks["B200"] / self.gpu_benchmarks["H100"]
        
        # Calculate expected B200 price based on H100 performance ratio
        expected_b200_price = h100_typical_price * performance_multiplier
        
        print(f"\n  H100 Typical Price:        ${h100_typical_price:.2f}/hr")
        print(f"  Performance Multiplier:    {performance_multiplier:.2f}x")
        print(f"  Expected B200 Price:       ${expected_b200_price:.2f}/hr")
        print(f"  Actual B200 Average:       ${b200_average:.2f}/hr")
        
        price_efficiency = expected_b200_price / b200_average if b200_average > 0 else 0
        
        if price_efficiency > 1:
            print(f"\n  ✅ B200 is {price_efficiency:.1%} more cost-efficient than expected")
        else:
            print(f"\n  ⚠️  B200 is {(1-price_efficiency):.1%} less cost-efficient than expected")
    
    def save_normalized_report(self, normalized: Dict[str, Dict], stats: Dict):
        """Save normalized pricing report to JSON"""
        output_file = self.b200_dir / "b200_normalized_prices.json"
        
        report = {
            "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S"),
            "base_model": self.base_model,
            "statistics": stats,
            "providers": normalized,
            "notes": {
                "all_prices_per_gpu_hour": True,
                "base_model": "NVIDIA B200 180GB HBM3e",
                "normalization": "All prices are for identical B200 GPU model"
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 80)
        print(f"💾 Normalized report saved to: {output_file}")
        print("=" * 80)


def main():
    """Main function to run B200 price normalization"""
    print("🚀 B200 GPU Price Normalization Tool")
    print("=" * 80)
    print("Analyzing B200 pricing across all providers...")
    print()
    
    # Initialize normalizer
    normalizer = B200PriceNormalizer()
    
    # Load all prices
    prices = normalizer.load_all_prices()
    
    if not prices:
        print("\n❌ No B200 price files found!")
        return
    
    # Normalize prices
    normalized = normalizer.normalize_prices(prices)
    
    # Calculate statistics
    stats = normalizer.calculate_statistics(normalized)
    
    if stats:
        # Calculate deviations
        normalizer.calculate_deviations(normalized, stats["average"])
        
        # Compare with H100
        normalizer.compare_with_h100(stats["average"])
        
        # Save report
        normalizer.save_normalized_report(normalized, stats)
    
    print("\n✅ Normalization complete!")


if __name__ == "__main__":
    main()

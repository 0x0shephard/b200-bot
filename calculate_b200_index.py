#!/usr/bin/env python3
"""
B200 GPU Weighted Index Calculator

Calculates a weighted B200 GPU index price based on:
1. Hyperscalers (AWS, Civo, CoreWeave) with 70-85% discounts
   - These providers sell 80% at discounted rates, 20% at full price
2. Non-hyperscalers at full price
3. Weighting: 65% hyperscalers, 35% non-hyperscalers

Hyperscaler Weights (out of 65%):
- AWS: Highest weight
- Civo: Medium weight
- CoreWeave: Lower weight

Non-hyperscaler Weights (out of 35%):
- Equal distribution among available providers
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple


class B200IndexCalculator:
    """Calculate weighted B200 GPU index price"""
    
    def __init__(self, b200_dir: str = "."):
        self.b200_dir = Path(b200_dir)
        
        # Define hyperscalers (4 major cloud providers)
        self.hyperscalers = ["AWS", "Google Cloud", "Civo", "CoreWeave"]
        
        # Hyperscaler discount range (70-85%)
        self.discount_min = 0.70
        self.discount_max = 0.85
        
        # Total weight distribution
        self.hyperscaler_total_weight = 0.65  # 65%
        self.non_hyperscaler_total_weight = 0.35  # 35%
        
        # Hyperscaler individual weights (must sum to 1.0)
        # AWS gets most weight, then Google Cloud, then Civo and CoreWeave
        self.hyperscaler_weights = {
            "AWS": 0.40,           # 40% of hyperscaler weight (26.0% of total)
            "Google Cloud": 0.25,  # 25% of hyperscaler weight (16.25% of total)
            "Civo": 0.20,          # 20% of hyperscaler weight (13.0% of total)
            "CoreWeave": 0.15,     # 15% of hyperscaler weight (9.75% of total)
        }
    
    def load_all_prices(self) -> Dict[str, float]:
        """Load all B200 prices from JSON files"""
        prices = {}
        
        # Find all *_b200_prices.json files
        json_files = list(self.b200_dir.glob("*_b200_prices.json"))
        
        print(f"📂 Found {len(json_files)} B200 price files\n")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    provider = data.get("provider", json_file.stem.replace("_b200_prices", ""))
                    
                    # Extract price value
                    price = self._extract_price_from_data(data)
                    
                    if price and price > 0:
                        prices[provider] = price
                        print(f"   ✓ {provider:20s} ${price:.2f}/hr")
            except Exception as e:
                print(f"   ✗ Error loading {json_file}: {e}")
        
        return prices
    
    def _extract_price_from_data(self, data: Dict) -> float:
        """Extract price value from provider data"""
        import re
        
        # Try standard "prices" structure
        provider_prices = data.get("prices", {})
        if provider_prices:
            for variant, price_str in provider_prices.items():
                match = re.search(r'([0-9.]+)', str(price_str).replace(',', '.'))
                if match:
                    return float(match.group(1))
        
        # Try RunPod's nested structure
        if "providers" in data:
            nested_providers = data.get("providers", {})
            for nested_provider_name, nested_data in nested_providers.items():
                variants = nested_data.get("variants", {})
                for variant_name, variant_data in variants.items():
                    if isinstance(variant_data, dict) and "price_per_hour" in variant_data:
                        return float(variant_data["price_per_hour"])
        
        return 0.0
    
    def apply_hyperscaler_discounts(self, prices: Dict[str, float]) -> Dict[str, Dict]:
        """Apply random discounts to hyperscalers"""
        discounted_prices = {}
        
        print("\n" + "=" * 80)
        print("💰 HYPERSCALER DISCOUNT APPLICATION")
        print("=" * 80)
        print("Hyperscalers sell 80% at discounted rates, 20% at full price\n")
        
        for provider, original_price in prices.items():
            if provider in self.hyperscalers:
                # Generate random discount between 70-85%
                discount_rate = random.uniform(self.discount_min, self.discount_max)
                
                # Calculate effective price: 80% at discounted rate + 20% at full rate
                discounted_portion = original_price * (1 - discount_rate) * 0.80
                full_price_portion = original_price * 0.20
                effective_price = discounted_portion + full_price_portion
                
                discounted_prices[provider] = {
                    "original_price": original_price,
                    "discount_rate": discount_rate,
                    "discounted_price": original_price * (1 - discount_rate),
                    "effective_price": effective_price,
                    "is_hyperscaler": True
                }
                
                print(f"🏢 {provider:20s}")
                print(f"   Original Price:     ${original_price:.2f}/hr")
                print(f"   Discount Applied:   {discount_rate*100:.1f}%")
                print(f"   Discounted Price:   ${original_price * (1 - discount_rate):.2f}/hr")
                print(f"   Effective Price:    ${effective_price:.2f}/hr (80% discounted + 20% full)")
                print()
            else:
                # Non-hyperscalers use full price
                discounted_prices[provider] = {
                    "original_price": original_price,
                    "discount_rate": 0.0,
                    "discounted_price": original_price,
                    "effective_price": original_price,
                    "is_hyperscaler": False
                }
        
        return discounted_prices
    
    def calculate_weighted_index(self, discounted_prices: Dict[str, Dict]) -> Dict:
        """Calculate weighted index price"""
        
        # Separate hyperscalers and non-hyperscalers
        hyperscaler_prices = {k: v for k, v in discounted_prices.items() if v["is_hyperscaler"]}
        non_hyperscaler_prices = {k: v for k, v in discounted_prices.items() if not v["is_hyperscaler"]}
        
        print("=" * 80)
        print("⚖️  WEIGHTED INDEX CALCULATION")
        print("=" * 80)
        
        # Calculate hyperscaler weighted price
        print(f"\n📊 HYPERSCALERS (Total Weight: {self.hyperscaler_total_weight*100:.0f}%)")
        print("-" * 80)
        
        hyperscaler_weighted_sum = 0
        hyperscaler_details = []
        
        for provider, data in hyperscaler_prices.items():
            if provider in self.hyperscaler_weights:
                individual_weight = self.hyperscaler_weights[provider]
                absolute_weight = individual_weight * self.hyperscaler_total_weight
                weighted_price = data["effective_price"] * absolute_weight
                
                hyperscaler_weighted_sum += weighted_price
                hyperscaler_details.append({
                    "provider": provider,
                    "effective_price": data["effective_price"],
                    "relative_weight": individual_weight,
                    "absolute_weight": absolute_weight,
                    "weighted_contribution": weighted_price
                })
                
                print(f"{provider:20s} ${data['effective_price']:6.2f}/hr × {absolute_weight*100:5.1f}% = ${weighted_price:.4f}")
        
        print(f"{'':20s} {'':11s} {'':7s}   {'─'*20}")
        print(f"{'Hyperscaler Subtotal':20s} {'':11s} {'':7s}   ${hyperscaler_weighted_sum:.4f}")
        
        # Calculate non-hyperscaler weighted price
        print(f"\n📊 NON-HYPERSCALERS (Total Weight: {self.non_hyperscaler_total_weight*100:.0f}%)")
        print("-" * 80)
        
        non_hyperscaler_weighted_sum = 0
        non_hyperscaler_details = []
        
        if non_hyperscaler_prices:
            # Equal distribution among non-hyperscalers
            equal_weight = self.non_hyperscaler_total_weight / len(non_hyperscaler_prices)
            
            for provider, data in non_hyperscaler_prices.items():
                weighted_price = data["effective_price"] * equal_weight
                
                non_hyperscaler_weighted_sum += weighted_price
                non_hyperscaler_details.append({
                    "provider": provider,
                    "effective_price": data["effective_price"],
                    "absolute_weight": equal_weight,
                    "weighted_contribution": weighted_price
                })
                
                print(f"{provider:20s} ${data['effective_price']:6.2f}/hr × {equal_weight*100:5.1f}% = ${weighted_price:.4f}")
            
            print(f"{'':20s} {'':11s} {'':7s}   {'─'*20}")
            print(f"{'Non-Hyperscaler Subtotal':20s} {'':11s} {'':7s}   ${non_hyperscaler_weighted_sum:.4f}")
        
        # Calculate final index
        final_index = hyperscaler_weighted_sum + non_hyperscaler_weighted_sum
        
        print("\n" + "=" * 80)
        print("🎯 FINAL B200 INDEX PRICE")
        print("=" * 80)
        print(f"\nHyperscaler Component:     ${hyperscaler_weighted_sum:.4f} ({self.hyperscaler_total_weight*100:.0f}%)")
        print(f"Non-Hyperscaler Component: ${non_hyperscaler_weighted_sum:.4f} ({self.non_hyperscaler_total_weight*100:.0f}%)")
        print(f"{'─'*50}")
        print(f"B200 Weighted Index:       ${final_index:.2f}/hr")
        print("=" * 80)
        
        return {
            "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S"),
            "final_index_price": round(final_index, 2),
            "hyperscaler_component": round(hyperscaler_weighted_sum, 4),
            "non_hyperscaler_component": round(non_hyperscaler_weighted_sum, 4),
            "hyperscaler_details": hyperscaler_details,
            "non_hyperscaler_details": non_hyperscaler_details,
            "weights": {
                "hyperscaler_total": self.hyperscaler_total_weight,
                "non_hyperscaler_total": self.non_hyperscaler_total_weight,
                "hyperscaler_individual": self.hyperscaler_weights
            },
            "all_provider_data": discounted_prices
        }
    
    def save_index_report(self, index_data: Dict):
        """Save index calculation report to JSON"""
        output_file = self.b200_dir / "b200_weighted_index.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Index report saved to: {output_file}")


def main():
    """Main function to calculate B200 weighted index"""
    print("🚀 B200 GPU Weighted Index Calculator")
    print("=" * 80)
    print("Calculating weighted B200 index with hyperscaler discounts...")
    print()
    
    # Set random seed for reproducibility (optional - remove for different results each run)
    # random.seed(42)
    
    # Initialize calculator
    calculator = B200IndexCalculator()
    
    # Load all prices
    prices = calculator.load_all_prices()
    
    if not prices:
        print("\n❌ No B200 price files found!")
        return
    
    # Apply hyperscaler discounts
    discounted_prices = calculator.apply_hyperscaler_discounts(prices)
    
    # Calculate weighted index
    index_data = calculator.calculate_weighted_index(discounted_prices)
    
    # Save report
    calculator.save_index_report(index_data)
    
    print("\n✅ Index calculation complete!")
    print(f"\n🎯 Final B200 Weighted Index Price: ${index_data['final_index_price']:.2f}/hr")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Push B200 Weighted Index to Supabase

This script reads the B200 weighted index from b200_weighted_index.json
and pushes it to the Supabase b200_index_prices table.

Usage:
    python push_to_supabase.py

Environment Variables Required (set in .env file):
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_KEY - Your Supabase service role key (for write access)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def load_index_data(filepath: str = "b200_weighted_index.json") -> Optional[Dict]:
    """Load B200 weighted index data from JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {filepath} not found!")
        print(f"   Please run calculate_b200_index.py first to generate the index.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return None


def push_to_supabase(index_data: Dict) -> bool:
    """Push B200 index data to Supabase with price validation"""
    
    # Get Supabase credentials from environment
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Error: Supabase credentials not found!")
        print("   Please set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")
        print("\n   Example:")
        print("   export SUPABASE_URL='https://your-project.supabase.co'")
        print("   export SUPABASE_SERVICE_KEY='your-service-role-key'")
        return False
    
    try:
        from supabase import create_client, Client
    except ImportError:
        print("❌ Error: supabase-py library not installed!")
        print("   Install it with: pip install supabase")
        return False
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Get new price
        new_price = index_data.get("final_index_price")
        
        # Validate price against historical data
        if not validate_price(supabase, new_price):
            print("\n❌ Price validation failed - not pushing to Supabase")
            print("   The new price is outside the acceptable range.")
            print("   This may indicate a scraping error or market anomaly.")
            return False
        
        # Prepare data for insertion
        insert_data = {
            "timestamp": index_data.get("timestamp"),
            "index_price": new_price,
            "hyperscaler_component": index_data.get("hyperscaler_component"),
            "non_hyperscaler_component": index_data.get("non_hyperscaler_component"),
            "metadata": {
                "weights": index_data.get("weights", {}),
                "hyperscaler_details": index_data.get("hyperscaler_details", []),
                "non_hyperscaler_details": index_data.get("non_hyperscaler_details", []),
                "provider_count": len(index_data.get("all_provider_data", {}))
            }
        }
        
        print(f"\n📤 Pushing B200 Index to Supabase...")
        print(f"   Index Price: ${insert_data['index_price']:.2f}/hr")
        print(f"   Timestamp: {insert_data['timestamp']}")
        
        # Insert into Supabase
        response = supabase.table('b200_index_prices').insert(insert_data).execute()
        
        if response.data:
            print(f"\n✅ Successfully pushed to Supabase!")
            print(f"   Record ID: {response.data[0]['id']}")
            return True
        else:
            print(f"\n❌ Error: No data returned from Supabase")
            return False
            
    except Exception as e:
        print(f"\n❌ Error pushing to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_price(supabase: 'Client', new_price: float, tolerance: float = 0.25) -> bool:
    """
    Validate that the new price is within acceptable range of historical prices.
    
    Args:
        supabase: Supabase client
        new_price: New price to validate
        tolerance: Acceptable deviation (default 20% = 0.20)
    
    Returns:
        True if price is valid, False otherwise
    """
    try:
        # Get last 2 prices from Supabase
        response = supabase.table('b200_index_prices')\
            .select('index_price')\
            .order('created_at', desc=True)\
            .limit(2)\
            .execute()
        
        if not response.data or len(response.data) < 2:
            print(f"\n⚠️  Not enough historical data for validation (found {len(response.data) if response.data else 0} records)")
            print(f"   Allowing push for initial data collection...")
            return True
        
        # Calculate average of last 2 prices
        last_prices = [float(record['index_price']) for record in response.data]
        avg_price = sum(last_prices) / len(last_prices)
        
        # Calculate acceptable range (±20%)
        lower_bound = avg_price * (1 - tolerance)
        upper_bound = avg_price * (1 + tolerance)
        
        # Check if new price is within range
        is_valid = lower_bound <= new_price <= upper_bound
        
        # Display validation info
        print(f"\n🔍 Price Validation Check:")
        print(f"   Last 2 Prices: ${last_prices[0]:.2f}, ${last_prices[1]:.2f}")
        print(f"   Average: ${avg_price:.2f}")
        print(f"   Acceptable Range: ${lower_bound:.2f} - ${upper_bound:.2f} (±{tolerance*100:.0f}%)")
        print(f"   New Price: ${new_price:.2f}")
        
        if is_valid:
            deviation_pct = ((new_price - avg_price) / avg_price) * 100
            print(f"   ✅ VALID - Deviation: {deviation_pct:+.1f}%")
        else:
            deviation_pct = ((new_price - avg_price) / avg_price) * 100
            print(f"   ❌ INVALID - Deviation: {deviation_pct:+.1f}% (exceeds ±{tolerance*100:.0f}%)")
        
        return is_valid
        
    except Exception as e:
        print(f"\n⚠️  Price validation error: {e}")
        print(f"   Allowing push anyway...")
        return True  # Allow push if validation fails (don't block on errors)


def verify_push(supabase_url: str, supabase_key: str) -> bool:
    """Verify the most recent entry in Supabase"""
    try:
        from supabase import create_client
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Get the most recent entry
        response = supabase.table('b200_index_prices')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            latest = response.data[0]
            print(f"\n📊 Latest Entry in Supabase:")
            print(f"   ID: {latest['id']}")
            print(f"   Index Price: ${latest['index_price']}/hr")
            print(f"   Timestamp: {latest['timestamp']}")
            print(f"   Created At: {latest['created_at']}")
            return True
        else:
            print(f"\n⚠️  No entries found in b200_index_prices table")
            return False
            
    except Exception as e:
        print(f"\n⚠️  Could not verify: {e}")
        return False


def main():
    """Main function"""
    print("🚀 B200 Index → Supabase Uploader")
    print("=" * 60)
    
    # Load index data
    print("\n📂 Loading B200 weighted index data...")
    index_data = load_index_data()
    
    if not index_data:
        sys.exit(1)
    
    print(f"   ✓ Loaded index: ${index_data['final_index_price']:.2f}/hr")
    
    # Push to Supabase
    success = push_to_supabase(index_data)
    
    if not success:
        sys.exit(1)
    
    # Verify
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if supabase_url and supabase_key:
        verify_push(supabase_url, supabase_key)
    
    print("\n✅ B200 index successfully uploaded to Supabase!")


if __name__ == "__main__":
    main()

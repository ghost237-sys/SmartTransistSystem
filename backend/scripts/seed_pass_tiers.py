"""
Seed script to create default pass tiers for the commuter pass system.
Run with: python manage.py shell < scripts/seed_pass_tiers.py
"""

import os
import django


from decimal import Decimal
from domains.passes.models import PassTier
from domains.tenants.models import Tenant

def seed_pass_tiers():
    """Create default pass tiers for all tenants."""
    
    tiers_data = [
        {
            'name': 'Weekly Bundle',
            'tier_type': 'weekly',
            'trip_allowance': 10,
            'discount_percent': Decimal('5.00'),
            'price': Decimal('950.00'),  # 10 trips at 5% discount (assuming 100 KES per trip)
            'duration_days': 7,
            'min_credit_score': None,
            'max_credit_limit': None,
            'is_active': True
        },
        {
            'name': 'Monthly Season Pass',
            'tier_type': 'monthly',
            'trip_allowance': 44,
            'discount_percent': Decimal('12.00'),
            'price': Decimal('3872.00'),  # 44 trips at 12% discount
            'duration_days': 30,
            'min_credit_score': None,
            'max_credit_limit': None,
            'is_active': True
        },
        {
            'name': 'Post-Paid Line',
            'tier_type': 'postpaid',
            'trip_allowance': 0,
            'discount_percent': Decimal('8.00'),
            'price': Decimal('0.00'),
            'duration_days': 30,
            'min_credit_score': 60,
            'max_credit_limit': Decimal('5000.00'),
            'is_active': True
        }
    ]
    
    # Create tiers for each tenant
    tenants = Tenant.objects.all()
    
    if not tenants.exists():
        print("No tenants found. Please create a tenant first.")
        return
    
    for tenant in tenants:
        print(f"\nCreating pass tiers for tenant: {tenant.name}")
        
        for tier_data in tiers_data:
            # Check if tier already exists for this tenant
            existing = PassTier.objects.filter(
                tenant=tenant,
                name=tier_data['name'],
                tier_type=tier_data['tier_type']
            ).first()
            
            if existing:
                print(f"  - {tier_data['name']} already exists, skipping...")
                continue
            
            tier = PassTier.objects.create(
                tenant=tenant,
                **tier_data
            )
            print(f"  ✓ Created {tier.name} ({tier.tier_type})")
    
    print("\n✅ Pass tiers seeded successfully!")

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    seed_pass_tiers()

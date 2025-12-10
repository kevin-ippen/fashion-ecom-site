"""
Analyze the fashion dataset to understand what we're working with
"""
import asyncio
import sys
sys.path.insert(0, '.')

from repositories.lakebase import LakebaseRepository
from core.database import get_async_session


async def analyze_dataset():
    """Analyze product dataset structure and distribution"""

    async for session in get_async_session():
        repo = LakebaseRepository(session)

        # Get sample products
        products = await repo.get_products(limit=100)

        print('=' * 80)
        print('DATASET OVERVIEW')
        print('=' * 80)
        print(f'Sample size: {len(products)} products\n')

        # Show one complete product
        if products:
            print('=' * 80)
            print('SAMPLE PRODUCT STRUCTURE')
            print('=' * 80)
            sample = products[0]
            for key, value in sample.items():
                print(f'  {key:25s} = {value}')
            print()

        print('=' * 80)
        print('ATTRIBUTE DISTRIBUTION (100 samples)')
        print('=' * 80)

        # Master categories
        categories = {}
        for p in products:
            cat = p.get('master_category')
            categories[cat] = categories.get(cat, 0) + 1
        print(f'\nMaster Categories:')
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f'  {cat:20s}: {count:3d} ({count/len(products)*100:.1f}%)')

        # Article types
        articles = {}
        for p in products:
            art = p.get('article_type')
            articles[art] = articles.get(art, 0) + 1
        print(f'\nArticle Types (top 10):')
        for art, count in sorted(articles.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f'  {art:30s}: {count:3d}')

        # Colors
        colors = {}
        for p in products:
            col = p.get('base_color')
            colors[col] = colors.get(col, 0) + 1
        print(f'\nColors (top 10):')
        for col, count in sorted(colors.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f'  {col:20s}: {count:3d}')

        # Price ranges
        prices = [p.get('price', 0) for p in products if p.get('price')]
        if prices:
            print(f'\nPrice Distribution:')
            print(f'  Min:     ${min(prices):.2f}')
            print(f'  Max:     ${max(prices):.2f}')
            print(f'  Average: ${sum(prices)/len(prices):.2f}')
            print(f'  Median:  ${sorted(prices)[len(prices)//2]:.2f}')

        # Genders
        genders = {}
        for p in products:
            gen = p.get('gender')
            genders[gen] = genders.get(gen, 0) + 1
        print(f'\nGenders:')
        for gen, count in sorted(genders.items(), key=lambda x: x[1], reverse=True):
            print(f'  {gen:20s}: {count:3d} ({count/len(products)*100:.1f}%)')

        # Seasons
        seasons = {}
        for p in products:
            sea = p.get('season')
            seasons[sea] = seasons.get(sea, 0) + 1
        print(f'\nSeasons:')
        for sea, count in sorted(seasons.items(), key=lambda x: x[1], reverse=True):
            print(f'  {str(sea):20s}: {count:3d}')

        # Usage
        usages = {}
        for p in products:
            use = p.get('usage')
            usages[use] = usages.get(use, 0) + 1
        print(f'\nUsage:')
        for use, count in sorted(usages.items(), key=lambda x: x[1], reverse=True):
            print(f'  {str(use):20s}: {count:3d}')

        print('\n' + '=' * 80)
        print('WHAT IS MISSING (not in structured data)')
        print('=' * 80)
        print('  - Material (leather, cotton, denim, etc.)')
        print('  - Pattern (solid, striped, floral, etc.)')
        print('  - Specific style (vintage, modern, minimalist, etc.)')
        print('  - Fit (slim, regular, oversized, etc.)')
        print('  - Details (pockets, buttons, collars, etc.)')
        print('  - Formality level (casual → formal spectrum)')
        print('  - Texture (smooth, rough, shiny, matte)')
        print('  - Occasion specificity (beyond "Casual"/"Formal")')

        break

if __name__ == '__main__':
    asyncio.run(analyze_dataset())

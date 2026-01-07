"""
Outfit compatibility service - determines what products pair well together
"""
import logging
from typing import List, Dict, Any, Set, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class OutfitCompatibilityService:
    """Service for filtering and scoring outfit compatibility"""

    # Category pairing rules - what items naturally go together
    COMPATIBLE_PAIRS = {
        # Apparel combinations
        ("Topwear", "Bottomwear"),
        ("Topwear", "Footwear"),
        ("Bottomwear", "Footwear"),
        ("Dress", "Footwear"),

        # Accessories with apparel
        ("Topwear", "Watches"),
        ("Topwear", "Bags"),
        ("Topwear", "Eyewear"),
        ("Topwear", "Jewellery"),
        ("Topwear", "Belts"),
        ("Bottomwear", "Belts"),
        ("Bottomwear", "Bags"),
        ("Dress", "Bags"),
        ("Dress", "Jewellery"),

        # Footwear with accessories
        ("Footwear", "Bags"),
        ("Footwear", "Watches"),
    }

    # Category anti-patterns - what should NOT be paired
    INCOMPATIBLE_PAIRS = {
        # Duplicate apparel types
        ("Topwear", "Topwear"),
        ("Bottomwear", "Bottomwear"),
        ("Dress", "Dress"),
        ("Footwear", "Footwear"),

        # Redundant combinations
        ("Dress", "Bottomwear"),  # Dress already covers bottom
        ("Dress", "Topwear"),     # Dress already covers top

        # Multiple accessories of same type
        ("Bags", "Bags"),
        ("Watches", "Watches"),
        ("Belts", "Belts"),
        ("Eyewear", "Eyewear"),
    }

    # Color clash rules - combinations that typically don't work well
    CLASHING_COLORS = {
        ("Red", "Pink"),
        ("Red", "Orange"),
        ("Red", "Purple"),
        ("Orange", "Pink"),
        ("Orange", "Purple"),
        ("Green", "Red"),  # Unless intentional Christmas theme
        ("Yellow", "Orange"),
        ("Brown", "Black"),  # Debatable, but often clashes
    }

    # Neutral colors that go with everything
    NEUTRAL_COLORS = {
        "Black", "White", "Grey", "Navy", "Beige", "Cream",
        "Tan", "Khaki", "Charcoal", "Off White", "Mushroom"
    }

    def __init__(self):
        logger.info("🎨 OutfitCompatibilityService initialized")

    def normalize_pair(self, cat1: str, cat2: str) -> Tuple[str, str]:
        """Normalize category pair for lookup (order-independent)"""
        return tuple(sorted([cat1, cat2]))

    def is_category_compatible(
        self,
        source_category: str,
        source_subcategory: str,
        rec_category: str,
        rec_subcategory: str
    ) -> bool:
        """
        Check if two items' categories are compatible for an outfit

        Args:
            source_category: Master category of source product
            source_subcategory: Sub category of source product
            rec_category: Master category of recommended product
            rec_subcategory: Sub category of recommended product

        Returns:
            True if compatible, False otherwise
        """
        # Check for explicit incompatibilities first
        pair = self.normalize_pair(source_category, rec_category)
        if pair in self.INCOMPATIBLE_PAIRS:
            logger.debug(f"❌ Incompatible pair: {pair}")
            return False

        # Check for explicit compatibilities
        if pair in self.COMPATIBLE_PAIRS:
            logger.debug(f"✅ Compatible pair: {pair}")
            return True

        # Check subcategory-level rules
        subcat_pair = self.normalize_pair(source_subcategory, rec_subcategory)

        # Same subcategory is usually bad (2 shirts, 2 jeans, etc.)
        if source_subcategory == rec_subcategory and source_category == rec_category:
            logger.debug(f"❌ Duplicate subcategory: {source_subcategory}")
            return False

        # Default: allow if not explicitly blocked
        # (Lookbook data should have good co-occurrences already)
        return True

    def is_color_compatible(
        self,
        source_color: str,
        rec_color: str
    ) -> bool:
        """
        Check if two colors work well together

        Args:
            source_color: Color of source product
            rec_color: Color of recommended product

        Returns:
            True if colors don't clash, False otherwise
        """
        # Normalize color names (handle variations)
        source_color = source_color.strip()
        rec_color = rec_color.strip()

        # Same color is always fine (monochrome)
        if source_color.lower() == rec_color.lower():
            return True

        # Neutrals go with everything
        if source_color in self.NEUTRAL_COLORS or rec_color in self.NEUTRAL_COLORS:
            return True

        # Check for explicit clashes
        pair = self.normalize_pair(source_color, rec_color)
        if pair in self.CLASHING_COLORS:
            logger.debug(f"❌ Clashing colors: {source_color} + {rec_color}")
            return False

        # Default: allow
        return True

    def diversify_by_color(
        self,
        candidates: List[Dict[str, Any]],
        limit: int = 4,
        max_per_color: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Diversify recommendations by color

        Args:
            candidates: List of candidate products
            limit: Maximum number to return
            max_per_color: Maximum items of same color

        Returns:
            Diversified list of products
        """
        if len(candidates) <= limit:
            return candidates

        result = []
        color_counts = Counter()

        for product in candidates:
            color = product.get("base_color", "Unknown")

            # Skip if we've hit the limit for this color
            if color_counts[color] >= max_per_color:
                continue

            result.append(product)
            color_counts[color] += 1

            if len(result) >= limit:
                break

        logger.debug(f"Color diversity: {dict(color_counts)}")
        return result

    def diversify_by_category(
        self,
        candidates: List[Dict[str, Any]],
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Diversify recommendations by category (avoid all accessories)

        Args:
            candidates: List of candidate products
            limit: Maximum number to return

        Returns:
            Diversified list of products
        """
        if len(candidates) <= limit:
            return candidates

        result = []
        category_counts = Counter()

        for product in candidates:
            category = product.get("master_category", "Unknown")

            # Prefer variety - skip if this category is over-represented
            if len(result) > 0 and category_counts[category] >= 2:
                continue

            result.append(product)
            category_counts[category] += 1

            if len(result) >= limit:
                break

        # If we didn't get enough, add remaining items
        if len(result) < limit:
            for product in candidates:
                if product not in result:
                    result.append(product)
                    if len(result) >= limit:
                        break

        logger.debug(f"Category diversity: {dict(category_counts)}")
        return result

    def filter_outfit_recommendations(
        self,
        source_product: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Filter and diversify outfit recommendations

        Args:
            source_product: Source product dict
            candidates: List of candidate products from lookbook data
            limit: Number of recommendations to return

        Returns:
            Filtered and diversified list of outfit recommendations
        """
        source_category = source_product.get("master_category", "")
        source_subcategory = source_product.get("sub_category", "")
        source_color = source_product.get("base_color", "")

        logger.info(f"Filtering {len(candidates)} candidates for {source_category}/{source_subcategory} ({source_color})")

        # Step 1: Filter by category compatibility
        category_filtered = []
        for candidate in candidates:
            rec_category = candidate.get("master_category", "")
            rec_subcategory = candidate.get("sub_category", "")

            if self.is_category_compatible(
                source_category, source_subcategory,
                rec_category, rec_subcategory
            ):
                category_filtered.append(candidate)

        logger.info(f"After category filtering: {len(category_filtered)} products")

        # Step 2: Filter by color compatibility
        color_filtered = []
        for candidate in category_filtered:
            rec_color = candidate.get("base_color", "")

            if self.is_color_compatible(source_color, rec_color):
                color_filtered.append(candidate)

        logger.info(f"After color filtering: {len(color_filtered)} products")

        # Step 3: Diversify by color (max 2 of same color)
        color_diversified = self.diversify_by_color(color_filtered, limit=limit * 2, max_per_color=2)

        logger.info(f"After color diversification: {len(color_diversified)} products")

        # Step 4: Diversify by category (avoid all accessories)
        final = self.diversify_by_category(color_diversified, limit=limit)

        logger.info(f"✅ Final recommendations: {len(final)} products")

        return final


# Singleton instance
outfit_compatibility_service = OutfitCompatibilityService()

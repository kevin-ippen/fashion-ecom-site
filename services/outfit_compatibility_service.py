"""
Outfit compatibility service - determines what products pair well together
Enhanced with comprehensive deterministic rules for outfit pairing
"""
import logging
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class OutfitCompatibilityService:
    """Service for filtering and scoring outfit compatibility with deterministic rules"""

    # Outerwear article types (layering pieces)
    OUTERWEAR_TYPES = {
        "Jackets", "Blazers", "Sweaters", "Sweatshirts", "Rain Jacket",
        "Nehru Jackets", "Shrug", "Coats", "Cardigans"
    }

    # Athletic/Activewear indicators
    ATHLETIC_USAGE = {"Sports"}
    ATHLETIC_ARTICLE_TYPES = {
        "Track Pants", "Tracksuits", "Sports Shoes", "Sports Sandals",
        "Leggings", "Tights"  # When usage="Sports"
    }

    # Formal wear indicators
    FORMAL_USAGE = {"Formal", "Smart Casual", "Party"}
    FORMAL_ARTICLE_TYPES = {
        "Formal Shoes", "Heels", "Blazers", "Suits", "Cufflinks"
    }

    # Items that should never be paired with regular apparel
    ISOLATED_SUBCATEGORIES = {
        "Innerwear",  # Underwear/Intimates
        "Loungewear and Nightwear",  # Sleepwear
    }

    # Swimwear (keep separate except for cover-ups)
    SWIMWEAR_TYPES = {"Swimwear"}

    # Special accessory subcategories
    HOSIERY_TYPES = {"Stockings", "Tights", "Socks"}  # Only with appropriate footwear

    # Category pairing rules - ALWAYS MATCH
    COMPATIBLE_PAIRS = {
        # Tops with everything (except other tops)
        ("tops", "bottoms"),
        ("tops", "outerwear"),
        ("tops", "footwear"),
        ("tops", "accessories"),

        # Bottoms with everything (except other bottoms)
        ("bottoms", "tops"),
        ("bottoms", "outerwear"),
        ("bottoms", "footwear"),
        ("bottoms", "accessories"),

        # Dresses with limited items
        ("dress", "outerwear"),
        ("dress", "footwear"),
        ("dress", "accessories"),

        # Outerwear with everything
        ("outerwear", "tops"),
        ("outerwear", "bottoms"),
        ("outerwear", "dress"),
        ("outerwear", "footwear"),
        ("outerwear", "accessories"),

        # Footwear with everything (except other footwear)
        ("footwear", "tops"),
        ("footwear", "bottoms"),
        ("footwear", "dress"),
        ("footwear", "outerwear"),
        ("footwear", "accessories"),

        # Accessories with everything (except underwear/sleepwear/swim)
        ("accessories", "tops"),
        ("accessories", "bottoms"),
        ("accessories", "dress"),
        ("accessories", "outerwear"),
        ("accessories", "footwear"),
    }

    # Category anti-patterns - NEVER MATCH
    INCOMPATIBLE_PAIRS = {
        # Same type duplicates
        ("tops", "tops"),
        ("bottoms", "bottoms"),
        ("dress", "dress"),
        ("footwear", "footwear"),
        ("outerwear", "outerwear"),  # Except layering

        # Dress is complete
        ("dress", "tops"),
        ("dress", "bottoms"),

        # Isolated categories
        ("innerwear", "*"),  # Underwear with anything
        ("sleepwear", "*"),  # Sleepwear with regular apparel
        ("swimwear", "*"),  # Swimwear with regular apparel (except cover-ups)
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
        logger.info("🎨 OutfitCompatibilityService initialized with deterministic rules")

    def normalize_pair(self, cat1: str, cat2: str) -> Tuple[str, str]:
        """Normalize category pair for lookup (order-independent)"""
        return tuple(sorted([cat1, cat2]))

    def categorize_product(self, product: Dict[str, Any]) -> str:
        """
        Categorize a product into conceptual categories for rule matching

        Returns one of: tops, bottoms, dress, outerwear, footwear, accessories,
                       innerwear, sleepwear, swimwear
        """
        master_cat = product.get("master_category", "")
        sub_cat = product.get("sub_category", "")
        article_type = product.get("article_type", "")
        usage = product.get("usage", "")

        # Check isolated categories first (highest priority)
        if sub_cat == "Innerwear":
            return "innerwear"
        if sub_cat == "Loungewear and Nightwear":
            return "sleepwear"
        if article_type in self.SWIMWEAR_TYPES:
            return "swimwear"

        # Check structural categories
        if master_cat == "Footwear":
            return "footwear"
        if master_cat == "Accessories":
            return "accessories"

        # Apparel subcategories
        if sub_cat == "Dress":
            return "dress"
        if sub_cat == "Bottomwear":
            return "bottoms"

        # Outerwear vs regular tops
        if sub_cat == "Topwear":
            if article_type in self.OUTERWEAR_TYPES:
                return "outerwear"
            return "tops"

        # Default fallback
        logger.warning(f"Unknown category for product: {master_cat}/{sub_cat}/{article_type}")
        return "unknown"

    def get_style_category(self, product: Dict[str, Any]) -> str:
        """
        Determine style category for coherence checking

        Returns one of: athletic, formal, casual, ethnic
        """
        usage = product.get("usage", "")
        article_type = product.get("article_type", "")

        # Athletic/Sports
        if usage in self.ATHLETIC_USAGE or article_type in self.ATHLETIC_ARTICLE_TYPES:
            return "athletic"

        # Formal/Dressy
        if usage in self.FORMAL_USAGE or article_type in self.FORMAL_ARTICLE_TYPES:
            return "formal"

        # Ethnic
        if usage == "Ethnic":
            return "ethnic"

        # Default to casual
        return "casual"

    def is_style_compatible(self, source_style: str, rec_style: str) -> bool:
        """
        Check if two style categories are compatible

        Rules:
        - Athletic only with athletic
        - Formal with formal or casual (not athletic)
        - Casual is versatile (works with formal and casual, not athletic)
        - Ethnic with ethnic or casual
        """
        # Athletic is strict - only with athletic
        if source_style == "athletic" or rec_style == "athletic":
            return source_style == rec_style

        # Formal with formal or casual
        if source_style == "formal":
            return rec_style in {"formal", "casual", "ethnic"}

        # Ethnic with ethnic or casual
        if source_style == "ethnic":
            return rec_style in {"ethnic", "casual"}

        # Casual is versatile
        return True

    def is_category_compatible(
        self,
        source_product: Dict[str, Any],
        rec_product: Dict[str, Any]
    ) -> bool:
        """
        Check if two items' categories are compatible for an outfit
        Uses deterministic rules based on product categorization

        Args:
            source_product: Source product dict
            rec_product: Recommended product dict

        Returns:
            True if compatible, False otherwise
        """
        # Categorize both products
        source_cat = self.categorize_product(source_product)
        rec_cat = self.categorize_product(rec_product)

        logger.debug(f"Checking compatibility: {source_cat} + {rec_cat}")

        # NEVER MATCH: Isolated categories
        if source_cat in {"innerwear", "sleepwear", "swimwear"}:
            logger.debug(f"❌ Source is isolated category: {source_cat}")
            return False
        if rec_cat in {"innerwear", "sleepwear", "swimwear"}:
            logger.debug(f"❌ Recommendation is isolated category: {rec_cat}")
            return False

        # NEVER MATCH: Same category duplicates (except outerwear layering)
        if source_cat == rec_cat:
            # Allow layering for outerwear (e.g., cardigan over sweater)
            if source_cat == "outerwear":
                # Check if they're actually different article types for layering
                source_article = source_product.get("article_type", "")
                rec_article = rec_product.get("article_type", "")
                if source_article != rec_article:
                    # Allow light outerwear combinations
                    light_outer = {"Cardigans", "Shrug"}
                    if source_article in light_outer or rec_article in light_outer:
                        logger.debug(f"✅ Allowed layering: {source_article} + {rec_article}")
                        return True

            logger.debug(f"❌ Duplicate category: {source_cat}")
            return False

        # NEVER MATCH: Dress with tops/bottoms (dress is complete)
        if source_cat == "dress" and rec_cat in {"tops", "bottoms"}:
            logger.debug(f"❌ Dress with {rec_cat} (dress is complete)")
            return False
        if rec_cat == "dress" and source_cat in {"tops", "bottoms"}:
            logger.debug(f"❌ {source_cat} with dress (dress is complete)")
            return False

        # SPECIAL RULES: Athletic/Activewear
        source_style = self.get_style_category(source_product)
        rec_style = self.get_style_category(rec_product)

        if not self.is_style_compatible(source_style, rec_style):
            logger.debug(f"❌ Style mismatch: {source_style} + {rec_style}")
            return False

        # SPECIAL RULES: Belts only with items that have waistbands
        source_article = source_product.get("article_type", "")
        rec_article = rec_product.get("article_type", "")

        if source_article == "Belts" and rec_cat not in {"bottoms", "dress"}:
            logger.debug(f"❌ Belt with {rec_cat} (no waistband)")
            return False
        if rec_article == "Belts" and source_cat not in {"bottoms", "dress"}:
            logger.debug(f"❌ Belt with {source_cat} (no waistband)")
            return False

        # SPECIAL RULES: Hosiery/socks only with appropriate footwear
        if source_article in self.HOSIERY_TYPES and rec_cat != "footwear":
            logger.debug(f"❌ Hosiery with {rec_cat} (needs footwear)")
            return False
        if rec_article in self.HOSIERY_TYPES and source_cat != "footwear":
            logger.debug(f"❌ Hosiery with {source_cat} (needs footwear)")
            return False

        # SPECIAL RULES: Formal dresses → only heels, clutches, formal jewelry
        if source_style == "formal" and source_cat == "dress":
            if rec_cat == "footwear":
                # Only heels or formal shoes
                if rec_article not in {"Heels", "Formal Shoes", "Flats"}:
                    logger.debug(f"❌ Formal dress with {rec_article} (needs heels/formal)")
                    return False
            if rec_cat == "accessories":
                rec_subcat = rec_product.get("sub_category", "")
                # Prefer formal accessories (clutches, formal jewelry)
                if rec_subcat == "Bags" and rec_article != "Clutches":
                    # Allow formal handbags
                    if rec_product.get("usage") != "Formal":
                        logger.debug(f"❌ Formal dress with casual bag")
                        return False

        # SPECIAL RULES: Suits/Blazers → dress shirts, dress pants, dress shoes
        if source_article in {"Blazers", "Suits"}:
            if rec_cat == "bottoms":
                # Should be dress pants/trousers, not jeans/shorts
                if rec_article not in {"Trousers", "Formal Pants"}:
                    logger.debug(f"❌ Blazer/Suit with {rec_article} (needs dress pants)")
                    return False
            if rec_cat == "footwear":
                # Should be formal shoes
                if rec_article not in {"Formal Shoes", "Heels"}:
                    logger.debug(f"❌ Blazer/Suit with {rec_article} (needs formal shoes)")
                    return False

        # ALWAYS MATCH: Check against compatible pairs
        pair = self.normalize_pair(source_cat, rec_cat)
        if pair in self.COMPATIBLE_PAIRS:
            logger.debug(f"✅ Compatible pair: {pair}")
            return True

        # Check for wildcard incompatibilities
        for incomp_pair in self.INCOMPATIBLE_PAIRS:
            if "*" in incomp_pair:
                restricted_cat = incomp_pair[0] if incomp_pair[1] == "*" else incomp_pair[1]
                if source_cat == restricted_cat or rec_cat == restricted_cat:
                    logger.debug(f"❌ Wildcard incompatibility: {restricted_cat}")
                    return False

        # Default: allow if not explicitly blocked
        logger.debug(f"✅ Default allow: {pair}")
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

    def is_category_compatible_relaxed(
        self,
        source_product: Dict[str, Any],
        rec_product: Dict[str, Any],
        check_style: bool = True
    ) -> bool:
        """
        Relaxed version of category compatibility (optionally skip style checking)

        Args:
            source_product: Source product dict
            rec_product: Recommended product dict
            check_style: If False, skip style coherence checking (allow athletic with casual, etc.)

        Returns:
            True if compatible, False otherwise
        """
        # Categorize both products
        source_cat = self.categorize_product(source_product)
        rec_cat = self.categorize_product(rec_product)

        # NEVER MATCH: Isolated categories (always enforce)
        if source_cat in {"innerwear", "sleepwear", "swimwear"}:
            return False
        if rec_cat in {"innerwear", "sleepwear", "swimwear"}:
            return False

        # NEVER MATCH: Same category duplicates (always enforce, except outerwear layering)
        if source_cat == rec_cat:
            if source_cat == "outerwear":
                source_article = source_product.get("article_type", "")
                rec_article = rec_product.get("article_type", "")
                if source_article != rec_article:
                    light_outer = {"Cardigans", "Shrug"}
                    if source_article in light_outer or rec_article in light_outer:
                        return True
            return False

        # NEVER MATCH: Dress with tops/bottoms (always enforce)
        if source_cat == "dress" and rec_cat in {"tops", "bottoms"}:
            return False
        if rec_cat == "dress" and source_cat in {"tops", "bottoms"}:
            return False

        # OPTIONAL: Style compatibility (can be relaxed)
        if check_style:
            source_style = self.get_style_category(source_product)
            rec_style = self.get_style_category(rec_product)
            if not self.is_style_compatible(source_style, rec_style):
                return False

        # ALWAYS MATCH: Check against compatible pairs
        pair = self.normalize_pair(source_cat, rec_cat)
        if pair in self.COMPATIBLE_PAIRS:
            return True

        # Default: allow if not explicitly blocked
        return True

    def filter_outfit_recommendations(
        self,
        source_product: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Filter and diversify outfit recommendations using strict deterministic rules
        (relies on large candidate pool including lower quality matches)

        Args:
            source_product: Source product dict
            candidates: List of candidate products from lookbook data
            limit: Number of recommendations to return

        Returns:
            Filtered and diversified list of outfit recommendations
        """
        source_category = self.categorize_product(source_product)
        source_style = self.get_style_category(source_product)
        source_color = source_product.get("base_color", "")

        logger.info(f"Filtering {len(candidates)} candidates for {source_category} ({source_style}, {source_color})")

        # Step 1: Filter by strict category and style compatibility rules
        compatible = []
        for candidate in candidates:
            if self.is_category_compatible(source_product, candidate):
                compatible.append(candidate)

        logger.info(f"After strict compatibility filtering: {len(compatible)} products")

        if len(compatible) == 0:
            logger.warning("No compatible products found after strict filtering!")
            return []

        # Step 2: Filter by color compatibility
        color_filtered = []
        for candidate in compatible:
            rec_color = candidate.get("base_color", "")

            if self.is_color_compatible(source_color, rec_color):
                color_filtered.append(candidate)

        logger.info(f"After color filtering: {len(color_filtered)} products")

        if len(color_filtered) == 0:
            # If color filtering is too strict, relax it and use compatible list
            logger.warning("Color filtering too strict, using compatibility-only filter")
            color_filtered = compatible

        # Step 3: Diversify by color (max 2 of same color)
        color_diversified = self.diversify_by_color(color_filtered, limit=limit * 2, max_per_color=2)

        logger.info(f"After color diversification: {len(color_diversified)} products")

        # Step 4: Diversify by category (avoid all accessories)
        final = self.diversify_by_category(color_diversified, limit=limit)

        logger.info(f"✅ Final recommendations: {len(final)} products")

        return final


# Singleton instance
outfit_compatibility_service = OutfitCompatibilityService()

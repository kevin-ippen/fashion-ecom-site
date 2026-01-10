"""
Business Features Service

Provides business-driven product discovery features:
- Trending products (based on popularity signals)
- Seasonal collections (current season highlights)
- New arrivals (recently added products)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter
import random

logger = logging.getLogger(__name__)


class BusinessFeaturesService:
    """Service for business-driven product discovery"""

    # Season mapping (Northern Hemisphere)
    SEASON_MONTHS = {
        "Spring": [3, 4, 5],
        "Summer": [6, 7, 8],
        "Fall": [9, 10, 11],
        "Winter": [12, 1, 2]
    }

    def get_current_season(self) -> str:
        """
        Get current season based on current month

        Returns:
            Season name (Spring, Summer, Fall, Winter)
        """
        current_month = datetime.now().month

        for season, months in self.SEASON_MONTHS.items():
            if current_month in months:
                return season

        return "All-Season"

    async def get_trending_products(
        self,
        lakebase_repo,
        limit: int = 20,
        time_window: str = "7_days"
    ) -> List[Dict[str, Any]]:
        """
        Get trending products

        In production, this would use real user interaction data (views, add-to-cart, purchases).
        For demo, we use a weighted random selection with category balance.

        Args:
            lakebase_repo: Lakebase repository instance
            limit: Number of trending products
            time_window: Time window for trending calculation (7_days, 30_days)

        Returns:
            List of trending products
        """
        logger.info(f"Getting trending products (limit={limit}, window={time_window})")

        # Fetch a large pool of candidates (3x limit for randomization)
        candidate_pool = await lakebase_repo.get_products(
            limit=limit * 5,
            filters=None,
            sort_by="product_id",
            sort_order="DESC"  # Bias toward newer products
        )

        if not candidate_pool:
            logger.warning("No products available for trending")
            return []

        # Mock trending score based on:
        # - Price (higher price = higher engagement potential)
        # - Recency (newer = more trending)
        # - Category diversity
        for product in candidate_pool:
            base_score = random.uniform(0.5, 1.0)  # Random baseline

            # Price boost (higher prices get slight boost - luxury appeal)
            price = product.get("price", 0)
            if price > 2000:
                base_score *= 1.3
            elif price > 1000:
                base_score *= 1.15

            # Recency boost
            year = product.get("year", 2015)
            if year >= 2018:
                base_score *= 1.4
            elif year >= 2017:
                base_score *= 1.2

            # Category balance (favor Apparel and Footwear over Accessories)
            master_cat = product.get("master_category", "")
            if master_cat == "Apparel":
                base_score *= 1.1
            elif master_cat == "Footwear":
                base_score *= 1.05

            product["trending_score"] = base_score

        # Sort by trending score
        candidate_pool.sort(key=lambda x: x.get("trending_score", 0), reverse=True)

        # Apply category diversity (max 40% from any single category)
        max_per_category = max(1, int(limit * 0.4))
        category_counts = Counter()
        trending_products = []

        for product in candidate_pool:
            if len(trending_products) >= limit:
                break

            master_cat = product.get("master_category", "Unknown")
            if category_counts[master_cat] < max_per_category:
                trending_products.append(product)
                category_counts[master_cat] += 1

        logger.info(
            f"Selected {len(trending_products)} trending products: "
            f"category_dist={dict(category_counts)}"
        )

        return trending_products

    async def get_seasonal_products(
        self,
        lakebase_repo,
        season: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get seasonal collection products

        Args:
            lakebase_repo: Lakebase repository instance
            season: Season name (Spring, Summer, Fall, Winter) or None for current
            limit: Number of products

        Returns:
            List of seasonal products
        """
        if not season:
            season = self.get_current_season()

        logger.info(f"Getting seasonal products for {season} (limit={limit})")

        # Build filters for season
        filters = {}

        # Season-based filtering
        if season != "All-Season":
            # Filter by season column
            # Note: Many products are marked "All-Season" so we include those too
            # This would need a better approach in production (tags, attributes, etc.)
            pass

        # Season-based category preferences
        category_preferences = self._get_season_category_preferences(season)

        # Fetch candidates with category bias
        all_products = []
        for category, weight in category_preferences.items():
            category_filters = {"master_category": category}
            category_limit = int(limit * weight * 2)  # Fetch 2x for randomization

            products = await lakebase_repo.get_products(
                limit=category_limit,
                filters=category_filters,
                sort_by="product_id",
                sort_order="DESC"
            )
            all_products.extend(products)

        # Shuffle and sample
        random.shuffle(all_products)
        seasonal_products = all_products[:limit]

        logger.info(
            f"Selected {len(seasonal_products)} {season} products from {len(all_products)} candidates"
        )

        return seasonal_products

    def _get_season_category_preferences(self, season: str) -> Dict[str, float]:
        """
        Get category weight preferences for a season

        Args:
            season: Season name

        Returns:
            Dict of category -> weight (sums to 1.0)
        """
        if season == "Summer":
            return {
                "Apparel": 0.5,      # Lightweight clothing
                "Footwear": 0.3,     # Sandals, flip-flops
                "Accessories": 0.2   # Sunglasses, hats
            }
        elif season == "Winter":
            return {
                "Apparel": 0.6,      # Sweaters, jackets, coats
                "Footwear": 0.25,    # Boots
                "Accessories": 0.15  # Scarves, gloves
            }
        elif season == "Spring":
            return {
                "Apparel": 0.5,
                "Footwear": 0.3,
                "Accessories": 0.2
            }
        elif season == "Fall":
            return {
                "Apparel": 0.55,     # Layers
                "Footwear": 0.25,
                "Accessories": 0.2
            }
        else:  # All-Season
            return {
                "Apparel": 0.5,
                "Footwear": 0.3,
                "Accessories": 0.2
            }

    async def get_new_arrivals(
        self,
        lakebase_repo,
        limit: int = 20,
        min_year: int = 2017
    ) -> List[Dict[str, Any]]:
        """
        Get new arrival products

        In production, this would use creation_date or ingestion_date.
        For demo, we use the 'year' field as a proxy.

        Args:
            lakebase_repo: Lakebase repository instance
            limit: Number of products
            min_year: Minimum year to consider "new"

        Returns:
            List of new arrival products
        """
        logger.info(f"Getting new arrivals (limit={limit}, min_year={min_year})")

        # Fetch products from recent years
        filters = {"min_year": min_year}

        new_products = await lakebase_repo.get_products(
            limit=limit * 3,  # Fetch 3x for diversity
            filters=filters,
            sort_by="year",
            sort_order="DESC"
        )

        # Apply category diversity
        max_per_category = max(1, int(limit * 0.4))
        category_counts = Counter()
        arrivals = []

        for product in new_products:
            if len(arrivals) >= limit:
                break

            master_cat = product.get("master_category", "Unknown")
            if category_counts[master_cat] < max_per_category:
                arrivals.append(product)
                category_counts[master_cat] += 1

        logger.info(
            f"Selected {len(arrivals)} new arrivals: "
            f"category_dist={dict(category_counts)}"
        )

        return arrivals


# Global service instance
business_features_service = BusinessFeaturesService()

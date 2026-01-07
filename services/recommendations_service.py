"""
Product recommendations service
Provides "you might also like" recommendations based on visual similarity
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class RecommendationsService:
    """Service for generating product recommendations"""

    # Category compatibility rules - categories that should NOT be recommended together
    INCOMPATIBLE_CATEGORIES = {
        # Don't recommend same type items together
        ("Apparel", "Apparel"): {
            ("Topwear", "Topwear"),  # Don't recommend shirt with shirt
            ("Bottomwear", "Bottomwear"),  # Don't recommend pants with pants
            ("Innerwear", "Innerwear"),
        },
        ("Footwear", "Footwear"): {
            ("Shoes", "Shoes"),  # Don't recommend shoes with shoes
            ("Flip Flops", "Flip Flops"),
            ("Sandal", "Sandal"),
        },
        ("Accessories", "Accessories"): {
            ("Bags", "Bags"),  # Don't recommend bag with bag
            ("Belts", "Belts"),
            ("Ties", "Ties"),
            ("Watches", "Watches"),
        },
        # Don't mix formal with casual accessories
        ("Accessories", "Accessories"): {
            ("Ties", "Watches"),  # Ties are formal, watches are everywhere
            ("Cufflinks", "Watches"),
        }
    }

    def __init__(self):
        logger.info("🔧 RecommendationsService initialized")

    def is_compatible(
        self,
        source_category: str,
        source_subcategory: str,
        target_category: str,
        target_subcategory: str
    ) -> bool:
        """
        Check if two products are compatible for recommendations

        Args:
            source_category: Master category of source product
            source_subcategory: Sub category of source product
            target_category: Master category of target product
            target_subcategory: Sub category of target product

        Returns:
            True if compatible, False otherwise
        """
        # Same product is never compatible
        if (source_category == target_category and
            source_subcategory == target_subcategory):
            return False

        # Check category-level incompatibility
        category_pair = (source_category, target_category)
        if category_pair in self.INCOMPATIBLE_CATEGORIES:
            incompatible_subcats = self.INCOMPATIBLE_CATEGORIES[category_pair]
            subcat_pair = (source_subcategory, target_subcategory)
            if subcat_pair in incompatible_subcats:
                return False

        return True

    def diversify_by_color(
        self,
        candidates: List[Dict[str, Any]],
        target_count: int = 6,
        min_colors: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Best-effort diversification by color

        Args:
            candidates: List of candidate products with 'base_color' field
            target_count: Target number of recommendations
            min_colors: Minimum number of different colors to aim for

        Returns:
            Diversified list of products
        """
        if len(candidates) <= target_count:
            return candidates

        # Group by color
        color_groups = defaultdict(list)
        for product in candidates:
            color = product.get("base_color", "Unknown")
            color_groups[color].append(product)

        # If we already have min_colors, try to distribute evenly
        if len(color_groups) >= min_colors:
            result = []
            colors = list(color_groups.keys())
            color_idx = 0

            # Round-robin through colors
            while len(result) < target_count:
                color = colors[color_idx % len(colors)]
                if color_groups[color]:
                    result.append(color_groups[color].pop(0))
                color_idx += 1

                # If we've exhausted all colors, break
                if all(len(group) == 0 for group in color_groups.values()):
                    break

            return result
        else:
            # Not enough color diversity, just return top N
            return candidates[:target_count]

    async def get_similar_products(
        self,
        source_product: Dict[str, Any],
        source_embedding: np.ndarray,
        vector_search_service,
        lakebase_repo,
        limit: int = 6,
        search_pool_multiplier: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get similar products with category filtering and diversity

        Args:
            source_product: Source product dict with metadata
            source_embedding: Source product embedding (512-dim)
            vector_search_service: Vector search service instance
            lakebase_repo: Lakebase repository instance
            limit: Number of recommendations to return
            search_pool_multiplier: Search N*limit products before filtering

        Returns:
            List of similar products with similarity scores
        """
        try:
            source_id = str(source_product.get("product_id"))
            source_category = source_product.get("master_category")
            source_subcategory = source_product.get("sub_category")

            logger.info(f"Finding similar products for {source_id} ({source_category}/{source_subcategory})")

            # Search for more candidates than needed (for filtering)
            search_limit = limit * search_pool_multiplier

            # Use vector search to find similar products
            candidates = await vector_search_service.search(
                query_vector=source_embedding,
                index_name=vector_search_service.index_name,
                num_results=search_limit,
                filters=None  # No filters at vector search level
            )

            logger.info(f"Vector search returned {len(candidates)} candidates")

            # Filter out source product and incompatible categories
            filtered = []
            for candidate in candidates:
                candidate_id = str(candidate.get("product_id"))

                # Skip source product
                if candidate_id == source_id:
                    continue

                # Check category compatibility
                target_category = candidate.get("master_category")
                target_subcategory = candidate.get("sub_category")

                if not self.is_compatible(
                    source_category, source_subcategory,
                    target_category, target_subcategory
                ):
                    logger.debug(f"Filtered out {candidate_id}: incompatible categories")
                    continue

                filtered.append(candidate)

            logger.info(f"After category filtering: {len(filtered)} products")

            # Diversify by color (best effort)
            diversified = self.diversify_by_color(filtered, target_count=limit, min_colors=2)

            logger.info(f"After diversification: {len(diversified)} products")

            # Enrich with full product data from Lakebase (for price, etc.)
            enriched = []
            for product in diversified:
                try:
                    product_id = int(float(product.get("product_id")))
                    full_product = await lakebase_repo.get_product_by_id(product_id)

                    if full_product:
                        # Merge vector search data with Lakebase data
                        full_product["similarity_score"] = product.get("score", 0.0)
                        enriched.append(full_product)
                except Exception as e:
                    logger.warning(f"Failed to enrich product {product.get('product_id')}: {e}")
                    # Use vector search data as fallback
                    enriched.append(product)

            # Log color diversity achieved
            colors = [p.get("base_color") for p in enriched]
            unique_colors = len(set(colors))
            logger.info(f"✅ Returning {len(enriched)} recommendations with {unique_colors} unique colors")

            return enriched

        except Exception as e:
            logger.error(f"Error generating similar products: {type(e).__name__}: {e}")
            raise


# Singleton instance
recommendations_service = RecommendationsService()

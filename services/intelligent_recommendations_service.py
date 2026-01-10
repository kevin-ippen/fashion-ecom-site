"""
Intelligent Recommendations Service

Multi-signal recommendation engine combining:
- Vector similarity (user embedding → product embedding)
- Business rule boosting (category match, color preference, price affinity)
- Diversity via Maximal Marginal Relevance (MMR)
- Persona-aware filtering
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Set
from collections import Counter
import json

logger = logging.getLogger(__name__)


class IntelligentRecommendationsService:
    """Service for generating intelligent personalized recommendations"""

    def __init__(self):
        self.mmr_lambda = 0.7  # Balance relevance (0.7) vs diversity (0.3)

    def calculate_business_score(
        self,
        product: Dict[str, Any],
        user_preferences: Dict[str, Any],
        persona_style: str
    ) -> float:
        """
        Calculate business rule score based on user preferences

        Args:
            product: Product dict
            user_preferences: User preference dict (categories, colors, price range)
            persona_style: Persona style (luxury, budget, etc.)

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0
        max_score = 0.0

        # Category match (weight: 0.35)
        preferred_categories = user_preferences.get("preferred_categories", [])
        if preferred_categories:
            max_score += 0.35
            product_cat = product.get("master_category", "")
            product_subcat = product.get("sub_category", "")

            if product_cat in preferred_categories:
                score += 0.35
            elif product_subcat in preferred_categories:
                score += 0.25  # Partial match for sub-category

        # Color preference (weight: 0.25)
        preferred_colors = user_preferences.get("color_prefs", [])
        if preferred_colors:
            max_score += 0.25
            product_color = product.get("base_color", "")
            if product_color in preferred_colors:
                score += 0.25

        # Price affinity (weight: 0.25)
        avg_price = user_preferences.get("avg_price_point") or user_preferences.get("avg_price")
        if avg_price and avg_price > 0:
            max_score += 0.25
            product_price = product.get("price", 0)
            if product_price > 0:
                # Score based on how close to user's average price
                price_ratio = min(product_price, avg_price) / max(product_price, avg_price)
                # Accept 0.5x to 2x user's average price
                if 0.5 <= product_price / avg_price <= 2.0:
                    score += 0.25 * price_ratio
                elif product_price / avg_price < 0.5:
                    # Too cheap for user's budget (gradual penalty)
                    score += 0.15 * price_ratio
                else:
                    # Too expensive (gradual penalty)
                    score += 0.10 * price_ratio

        # Recency boost (weight: 0.15) - newer products get slight boost
        product_year = product.get("year")
        if product_year:
            max_score += 0.15
            # Boost products from 2017-2018 (most recent in dataset)
            if product_year >= 2017:
                score += 0.15
            elif product_year >= 2015:
                score += 0.10
            elif product_year >= 2013:
                score += 0.05

        # Normalize to 0-1 range
        if max_score > 0:
            return score / max_score
        return 0.0

    def apply_mmr(
        self,
        candidates: List[Dict[str, Any]],
        query_embedding: np.ndarray,
        target_count: int,
        lambda_param: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Apply Maximal Marginal Relevance for diversity

        MMR = λ * Similarity(query, doc) - (1-λ) * max Similarity(doc, selected_docs)

        Args:
            candidates: List of candidate products with similarity scores
            query_embedding: User embedding
            target_count: Number of products to select
            lambda_param: Balance between relevance and diversity (0.7 = 70% relevance)

        Returns:
            Diversified list of products
        """
        if len(candidates) <= target_count:
            return candidates

        # Extract product embeddings if available
        # For now, use color and category as diversity signals
        selected = []
        remaining = candidates.copy()

        # Select first item (highest similarity)
        selected.append(remaining.pop(0))

        while len(selected) < target_count and remaining:
            best_mmr_score = -float('inf')
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # Relevance: Use original similarity score
                relevance = candidate.get("similarity_score", 0.5)

                # Diversity penalty: Check similarity to already selected items
                max_similarity = 0.0
                for selected_product in selected:
                    # Simple diversity metric: same category/color = high similarity
                    similarity = 0.0
                    if candidate.get("master_category") == selected_product.get("master_category"):
                        similarity += 0.4
                    if candidate.get("sub_category") == selected_product.get("sub_category"):
                        similarity += 0.3
                    if candidate.get("base_color") == selected_product.get("base_color"):
                        similarity += 0.3

                    max_similarity = max(max_similarity, similarity)

                # Calculate MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            # Select best MMR candidate
            selected.append(remaining.pop(best_idx))

        logger.info(f"MMR diversification: {len(candidates)} → {len(selected)} products")
        return selected

    async def get_recommendations(
        self,
        user: Dict[str, Any],
        user_embedding: np.ndarray,
        persona_style: str,
        vector_search_service,
        limit: int = 20,
        apply_diversity: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate intelligent personalized recommendations

        Args:
            user: User dict with preferences
            user_embedding: User's behavioral embedding (512-dim)
            persona_style: Persona style (luxury, budget, athletic, etc.)
            vector_search_service: Vector search service instance
            limit: Number of recommendations
            apply_diversity: Whether to apply MMR for diversity

        Returns:
            List of recommended products with scores
        """
        logger.info(f"Generating intelligent recommendations for {persona_style} persona")

        # Build persona-specific filters
        filters = self._build_persona_filters(persona_style, user)

        # Fetch more candidates for filtering and diversity
        candidate_limit = limit * 3 if apply_diversity else limit

        # Vector search using user embedding
        candidates = await vector_search_service.search_hybrid(
            query_vector=user_embedding,
            num_results=candidate_limit,
            filters=filters
        )

        logger.info(f"Vector search returned {len(candidates)} candidates")

        if not candidates:
            logger.warning("No candidates from vector search, returning empty")
            return []

        # Calculate business rule scores and combine with similarity
        for product in candidates:
            similarity_score = product.get("similarity_score", 0.5)
            business_score = self.calculate_business_score(product, user, persona_style)

            # Combined score: 60% vector similarity + 40% business rules
            product["combined_score"] = 0.6 * similarity_score + 0.4 * business_score
            product["business_score"] = business_score

            logger.debug(
                f"Product {product.get('product_id')}: "
                f"similarity={similarity_score:.3f}, "
                f"business={business_score:.3f}, "
                f"combined={product['combined_score']:.3f}"
            )

        # Sort by combined score
        candidates.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

        # Apply MMR for diversity
        if apply_diversity and len(candidates) > limit:
            recommendations = self.apply_mmr(
                candidates=candidates,
                query_embedding=user_embedding,
                target_count=limit,
                lambda_param=self.mmr_lambda
            )
        else:
            recommendations = candidates[:limit]

        # Log diversity stats
        categories = [p.get("master_category") for p in recommendations]
        colors = [p.get("base_color") for p in recommendations]
        category_dist = Counter(categories)
        color_dist = Counter(colors)

        logger.info(
            f"Recommendations diversity: "
            f"categories={dict(category_dist)}, "
            f"colors={dict(color_dist.most_common(5))}"
        )

        return recommendations

    def _build_persona_filters(self, persona_style: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build filters based on persona style

        Args:
            persona_style: Persona style
            user: User dict

        Returns:
            Filters dict for vector search
        """
        filters = {}

        # Persona-specific filters (actual product price range: $0-300)
        # Note: We do NOT filter by category here to allow vector search to return diverse results
        # Category diversity is handled by MMR after fetching candidates
        if persona_style == "luxury":
            filters["min_price"] = 200
        elif persona_style in ["budget", "budget_savvy"]:
            filters["min_price"] = 10
            filters["max_price"] = 100
        elif persona_style == "athletic":
            filters["min_price"] = 80
            filters["max_price"] = 180
            # Athletic can include all categories, MMR will handle diversity
        elif persona_style in ["formal", "professional"]:
            filters["min_price"] = 150
            # Professional can include all categories, MMR will handle diversity
        elif persona_style in ["casual", "urban_casual"]:
            filters["min_price"] = 100
            filters["max_price"] = 200

        # Note: Removed user-specific category filtering here
        # Category diversity is now handled by MMR algorithm which ensures
        # we don't get all footwear or all apparel

        logger.info(f"Built filters for {persona_style} persona: {filters}")
        return filters

    def get_category_weights(self, persona_style: str) -> Dict[str, float]:
        """
        Get category sampling weights for persona to ensure diversity

        Args:
            persona_style: The persona style

        Returns:
            Dict of category -> weight for balanced sampling
        """
        PERSONA_CATEGORY_WEIGHTS = {
            "luxury": {"Apparel": 0.50, "Accessories": 0.25, "Footwear": 0.25},
            "budget": {"Apparel": 0.50, "Footwear": 0.30, "Accessories": 0.20},
            "budget_savvy": {"Apparel": 0.50, "Footwear": 0.30, "Accessories": 0.20},
            "athletic": {"Apparel": 0.60, "Footwear": 0.40},
            "formal": {"Apparel": 0.55, "Accessories": 0.30, "Footwear": 0.15},
            "professional": {"Apparel": 0.55, "Accessories": 0.30, "Footwear": 0.15},
            "casual": {"Apparel": 0.60, "Footwear": 0.25, "Accessories": 0.15},
            "urban_casual": {"Apparel": 0.60, "Footwear": 0.25, "Accessories": 0.15},
        }
        return PERSONA_CATEGORY_WEIGHTS.get(
            persona_style,
            {"Apparel": 0.50, "Footwear": 0.25, "Accessories": 0.25}
        )


# Global service instance
intelligent_recommendations_service = IntelligentRecommendationsService()


"""
Recommendation Service
Multi-signal scoring combining visual similarity, user preferences, and attributes
"""
from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class ScoringWeights:
    """Configuration for recommendation scoring weights."""
    visual: float = 0.5
    user: float = 0.3
    attribute: float = 0.2

    def normalize(self) -> "ScoringWeights":
        """Normalize weights to sum to 1.0."""
        total = self.visual + self.user + self.attribute
        return ScoringWeights(
            visual=self.visual / total,
            user=self.user / total,
            attribute=self.attribute / total
        )


class RecommendationService:
    """Service for scoring and ranking product recommendations."""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        self.weights = self.weights.normalize()

    def compute_attribute_score(
        self,
        product: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> float:
        """
        Compute attribute-based score using user preferences.
        
        Args:
            product: Product data dict
            user_preferences: User preference data
            
        Returns:
            Attribute score (0-1)
        """
        scores = []

        # Color match
        if user_preferences.get("color_prefs") and product.get("base_color"):
            color_prefs = user_preferences["color_prefs"]
            if isinstance(color_prefs, dict):
                color_score = color_prefs.get(product["base_color"], 0.0)
            elif isinstance(color_prefs, list):
                color_score = 1.0 if product["base_color"] in color_prefs else 0.0
            else:
                color_score = 0.5
            scores.append(color_score)

        # Category match
        if user_preferences.get("category_prefs") and product.get("master_category"):
            cat_prefs = user_preferences["category_prefs"]
            if isinstance(cat_prefs, dict):
                cat_score = cat_prefs.get(product["master_category"], 0.0)
            elif isinstance(cat_prefs, list):
                cat_score = 1.0 if product["master_category"] in cat_prefs else 0.0
            else:
                cat_score = 0.5
            scores.append(cat_score)

        # Price compatibility
        if product.get("price") is not None:
            price = product["price"]
            min_price = user_preferences.get("min_price", 0)
            max_price = user_preferences.get("max_price", float('inf'))
            
            if min_price <= price <= max_price:
                price_score = 1.0
            elif price < min_price:
                price_score = 0.7
            else:
                avg_price = user_preferences.get("avg_price", max_price)
                if avg_price > 0:
                    overage_ratio = (price - max_price) / avg_price
                    price_score = max(0.3, 1.0 - overage_ratio)
                else:
                    price_score = 0.3
            
            scores.append(price_score)

        return float(np.mean(scores)) if scores else 0.5

    def score_products(
        self,
        products: List[Dict[str, Any]],
        visual_scores: List[float],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Score and rank products using multiple signals.
        
        Args:
            products: List of product dicts
            visual_scores: List of visual similarity scores
            user_preferences: Optional user preference data
            
        Returns:
            List of products with computed scores, sorted by final_score
        """
        scored_products = []
        
        for product, visual_score in zip(products, visual_scores):
            product["visual_score"] = visual_score
            
            if user_preferences:
                attr_score = self.compute_attribute_score(product, user_preferences)
                product["attribute_score"] = attr_score
                product["user_score"] = attr_score
            else:
                product["attribute_score"] = 0.5
                product["user_score"] = 0.0
            
            final_score = (
                self.weights.visual * product["visual_score"] +
                self.weights.user * product["user_score"] +
                self.weights.attribute * product["attribute_score"]
            )
            product["final_score"] = final_score
            product["similarity_score"] = final_score
            
            # Generate personalization reason
            if user_preferences:
                reasons = []
                if product.get("base_color") in user_preferences.get("color_prefs", []):
                    reasons.append(f"Matches your preference for {product['base_color']} items")
                if user_preferences.get("min_price", 0) <= product.get("price", 0) <= user_preferences.get("max_price", float('inf')):
                    reasons.append("Within your typical price range")
                
                if reasons:
                    product["personalization_reason"] = " • ".join(reasons)
            
            scored_products.append(product)
        
        scored_products.sort(key=lambda x: x["final_score"], reverse=True)
        return scored_products

    def diversify_results(
        self,
        products: List[Dict[str, Any]],
        max_per_category: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Apply diversity constraints to avoid too many similar items.
        """
        category_counts: Dict[str, int] = {}
        diversified = []

        for product in products:
            category = product.get("master_category", "Unknown")
            count = category_counts.get(category, 0)

            if count < max_per_category:
                diversified.append(product)
                category_counts[category] = count + 1

        return diversified


# Global service instance
recommendation_service = RecommendationService()

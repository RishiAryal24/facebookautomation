from copy import deepcopy
from typing import Any, Dict, Optional


DEFAULT_BRAND_PROFILE: Dict[str, Any] = {
    "company_name": "PyLoom Technologies Pvt. Ltd.",
    "tagline": "Weaving Innovation Beyond Expectations.",
    "website": "https://pyloomtech.com/",
    "contact_details": {},
    "verified_services": [
        "AI-powered software development",
        "Business process automation",
        "Custom software solutions",
        "Data analytics",
        "Hospital management systems",
        "E-commerce software",
    ],
    "products": [
        {
            "name": "PyLoom AI HMS",
            "aliases": ["HMS", "hospital management system", "hospital management systems"],
            "description": "",
            "approved_features": [],
        },
        {
            "name": "Insight360",
            "aliases": ["data analytics"],
            "description": "",
            "approved_features": [],
        },
        {
            "name": "Khusiko Ecommerce",
            "aliases": ["e-commerce", "ecommerce", "online store"],
            "description": "",
            "approved_features": [],
        },
    ],
    "target_industries": [],
    "target_audiences": [],
    "brand_tone": "Knowledgeable, professional, approachable, and specific.",
    "preferred_writing_style": (
        "Natural editorial writing with varied sentence lengths, useful detail, "
        "and a practical next step where appropriate."
    ),
    "approved_claims": [],
    "restricted_claims": [
        "Unverified product features, integrations, prices, discounts, availability, "
        "customer stories, results, performance claims, or statistics.",
        "Claims that generated content was written by a human.",
    ],
}


def build_brand_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine the known company facts with administrator-verified additions."""
    result = deepcopy(DEFAULT_BRAND_PROFILE)
    if not isinstance(profile, dict):
        return result
    for key, value in profile.items():
        if key == "products" and isinstance(value, list):
            result[key] = value
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result


def find_relevant_product(topic: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    normalized_topic = topic.casefold()
    products = profile.get("products", [])
    if not isinstance(products, list):
        return None
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get("name"), str):
            continue
        name = product["name"]
        aliases = product.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        if any(
            isinstance(term, str) and term.casefold() in normalized_topic
            for term in [name, *aliases]
            if term
        ):
            return product
    return None

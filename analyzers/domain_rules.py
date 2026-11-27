"""Business-domain and capability classification rules."""
from __future__ import annotations

_DOMAIN_RULES = {
    "Payments": {
        "keywords": {"payment", "payments", "visa", "mastercard", "stripe", "paypal", "billing", "refund", "authorize"},
        "responsibility": "Handles payment methods, authorization, capture, and refunds.",
    },
    "Catalog": {
        "keywords": {"catalog", "product", "products", "attribute", "attributes", "category", "categories"},
        "responsibility": "Manages product information, attributes, and category organization.",
    },
    "Orders": {
        "keywords": {"order", "orders", "checkout", "cart", "basket"},
        "responsibility": "Supports cart, checkout, and order lifecycle workflows.",
    },
    "Inventory": {
        "keywords": {"inventory", "stock", "warehouse", "availability"},
        "responsibility": "Tracks stock, warehouse, and product availability information.",
    },
    "Customer Experience": {
        "keywords": {"customer", "customers", "account", "accounts", "registration", "profile", "identity"},
        "responsibility": "Supports customer accounts, registration, and profile experiences.",
    },
    "Shipping": {
        "keywords": {"shipping", "shipment", "delivery", "fulfillment", "carrier"},
        "responsibility": "Coordinates shipment, delivery, and fulfillment workflows.",
    },
    "Marketing": {
        "keywords": {"marketing", "campaign", "campaigns", "advertising", "advertisement", "ad", "ads", "promotion", "coupon"},
        "responsibility": "Supports campaigns, promotions, and customer-facing merchandising.",
    },
    "Search": {
        "keywords": {"search", "index", "indexing", "elasticsearch", "opensearch"},
        "responsibility": "Indexes and retrieves information for product and content discovery.",
    },
    "Loyalty": {
        "keywords": {"loyalty", "rewards", "points"},
        "responsibility": "Manages customer rewards, points, and loyalty programs.",
    },
    "ERP Integrations": {
        "keywords": {"erp", "sap", "netsuite", "dynamics", "oracle"},
        "responsibility": "Connects application workflows with enterprise resource planning systems.",
    },
}


_HIGH_VALUE_DOMAINS = {"Payments", "Orders", "Inventory", "ERP Integrations"}


_CAPABILITY_RULES = {
    "Customer Registration": {"customer", "account", "registration", "register", "create"},
    "Order Processing": {"order", "checkout", "cart", "process"},
    "Payment Authorization": {"payment", "visa", "mastercard", "stripe", "paypal", "authorize"},
    "Inventory Management": {"inventory", "stock", "warehouse", "availability"},
    "Product Search": {"product", "catalog", "search", "index", "indexing"},
    "ERP Synchronization": {"erp", "sap", "netsuite", "dynamics", "oracle", "sync", "synchronization"},
    "Shipping and Fulfillment": {"shipping", "shipment", "delivery", "fulfillment", "carrier"},
    "Promotions and Campaigns": {"marketing", "campaign", "advertising", "ad", "ads", "promotion", "coupon"},
    "Customer Loyalty": {"loyalty", "rewards", "points"},
}


_CAPABILITY_DOMAINS = {
    "Customer Registration": {"Customer Experience"},
    "Order Processing": {"Orders"},
    "Payment Authorization": {"Payments"},
    "Inventory Management": {"Inventory"},
    "Product Search": {"Catalog", "Search"},
    "ERP Synchronization": {"ERP Integrations"},
    "Shipping and Fulfillment": {"Shipping"},
    "Promotions and Campaigns": {"Marketing"},
    "Customer Loyalty": {"Loyalty"},
}

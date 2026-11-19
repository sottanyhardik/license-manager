"""Product Intelligence Engine — our own, database-trained, CPU-only (no hosted / paid AI, no Ollama).

Service map (owner spec 2026-11-19 → code):

1  Description Normalizer ............ product_matching.normalise / product_segments
2  Feature Extractor ................. product_intelligence.features.pair_features (financial fields excluded)
3  Similarity Engine ................. features.TfidfIndex (char 3–5-gram TF-IDF, inverted index) + text_score + local MiniLM
4  Historical Knowledge Repository ... product_intelligence.knowledge (inventory, observations, versioned datasets)
5  Domain-Specific Classifier ........ product_intelligence.learn (logistic regression / boosted stumps, numpy)
6  Canonical Product Resolver ........ product_intelligence.resolver.resolve
7  Approved Alias Registry ........... product_intelligence.aliases (ProductAlias)
8–10 HSN / SION / Entitlement validators  product_matching.suggest → evaluate() + _validate()
11 Match Confidence Evaluator ........ product_matching._band (95 / 90 / 80; conflicts override)
12 Human Decision and Audit .......... product_matching.decide (ProductMatchDecision) + ProductIntelAuditEvent
13 Product Aggregation ............... item_pivot_intelligence.build_intelligence (+ integrity check)
14 Licence Eligibility ............... item_pivot_intelligence._status / eligibility cells
15 Planning Recommendation ........... item_pivot_intelligence.recommend_for_licenses (Auto Plan preview, rolled back)
16–18 Training / Evaluation / Version + Rollback  product_intelligence.lifecycle (ProductIntelModel)
"""

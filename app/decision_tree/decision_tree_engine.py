"""
Decision Tree Engine for Awaaz Setu.

Architectural Context:
- Evaluates queries through a formal, hierarchical Decision Tree.
- Determines whether a caller query belongs to:
    1. Karnataka Government Domain (State schemes, portals, land records, welfare) -> Routes to RAG
    2. General / Open Domain Knowledge -> Routes to Google Gemini
- Emits transparent decision paths and confidence metrics for auditability.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import get_logger
from app.decision_tree.tree_nodes import DecisionNode, DecisionTrace, RoutingTarget

logger = get_logger("awaaz_setu.decision_tree")


class FeatureExtractor:
    """Extracts domain, syntactic, and entity signals from caller queries."""

    # 1. Karnataka Guarantee Schemes & Official Programs
    KARNATAKA_SCHEMES = [
        "gruha lakshmi", "gruhalakshmi", "graha lakshmi", "gruha jyothi", "gruhajyothi", "graha jyothi",
        "yuva nidhi", "yuvanidhi", "anna bhagya", "annabhagya", "shakti scheme", "shakthi scheme",
        "ganga kalyana", "gangakalyana", "raitha siri", "krishi bhagya", "pashu bhagya", "sandhya suraksha",
        "vidyasiri", "arogya karnataka", "k-kisan", "manasvini", "mythri scheme",
    ]

    # 2. Karnataka Official Portals & E-Governance Systems
    KARNATAKA_PORTALS = [
        "seva sindhu", "sevasindhu", "bhoomi", "nadakacheri", "nada kacheri", "eswathu", "e-swathu",
        "kutumba", "fruits portal", "ahara portal", "ahara.kar.nic.in", "ssp portal", "ssp scholarship",
        "bescom", "mescom", "hescom", "gescom", "cesc", "ksrtc", "bmtc", "nwkrtc", "kkrtc",
        "grama one", "bangalore one", "karnataka one", "ajsk", "kaveri online", "rdpr karnataka",
    ]

    # 3. Karnataka Land & Revenue Terms
    KARNATAKA_LAND_TERMS = [
        "rtc", "pahani", "mutation", "survey number", "akarband", "tippan", "form 9", "form 11",
        "khata", "b-khata", "a-khata", "gram thana", "village accountant", "tahsildar", "taluk office",
        "hobli", "revenue inspector", "surnoc", "hissa", "land record", "mr status",
    ]

    # 4. Karnataka State / Administrative Identifiers
    KARNATAKA_GEO_TERMS = [
        "karnataka", "karnatak", "gok", "bangalore", "bengaluru", "mysore", "mysuru", "hubli",
        "hubballi", "dharwad", "belgaum", "belagavi", "mangalore", "mangaluru", "kalaburagi",
        "gulbarga", "shimoga", "shivamogga", "tumkur", "tumakuru", "bellary", "ballari", "davangere",
        "udupi", "dakshina kannada", "uttara kannada", "hassan", "mandya", "chikkamagaluru",
        "chamarajanagar", "bidar", "raichur", "koppal", "bagalkot", "vijayapura", "bijapur",
    ]

    # 5. Citizen Welfare, Subsidy & Scheme Intent Keywords
    WELFARE_INTENT_TERMS = [
        "free electricity", "200 units", "2000 rupees", "2000 rs", "free bus", "bus pass",
        "unemployment allowance", "graduate stipend", "diploma stipend", "borewell subsidy",
        "free borewell", "millet incentive", "dairy subsidy", "cow loan", "cattle loan", "sheep subsidy",
        "goat loan", "old age pension", "widow pension", "senior citizen pension", "caste certificate",
        "income certificate", "ration card bpl", "bpl card", "antyodaya", "food grains dbt",
        "student scholarship", "fee reimbursement", "cashless hospital", "health card",
    ]

    # 6. General / Open Knowledge Patterns (Non-Karnataka)
    OPEN_DOMAIN_PATTERNS = [
        r"\b(who is|who was|who wrote|who invented|who discovered)\b",
        r"\b(what is the capital of|population of|distance between|speed of light)\b",
        r"\b(write a python|write code|debug this|programming in|sql query)\b",
        r"\b(tell me a joke|write a poem|sing a song|story about)\b",
        r"\b(what is the weather in (delhi|mumbai|london|new york|paris|tokyo))\b",
        r"\b(french revolution|world war|einstein|newton|shakespeare|president of us)\b",
    ]

    # 7. Greetings / Chitchat
    GREETING_PATTERNS = [
        r"^(hi|hello|hey|namaste|namaskara|good morning|good evening|good afternoon)[\s!.]*$",
        r"^(who are you|what can you do|what is your name|help)[\s!.]*$",
    ]

    @classmethod
    def extract_features(cls, query: str) -> Dict[str, Any]:
        """Extracts boolean flags, matched keywords, and signals from query text."""
        q_norm = (query or "").lower().strip()
        matched_keywords: List[str] = []

        # 1. Explicit Scheme Match
        matched_schemes = [s for s in cls.KARNATAKA_SCHEMES if s in q_norm]
        matched_keywords.extend(matched_schemes)

        # 2. Portal Match
        matched_portals = [p for p in cls.KARNATAKA_PORTALS if p in q_norm]
        matched_keywords.extend(matched_portals)

        # 3. Land / Revenue Terms
        matched_land = [lt for lt in cls.KARNATAKA_LAND_TERMS if re.search(r"\b" + re.escape(lt) + r"\b", q_norm)]
        matched_keywords.extend(matched_land)

        # 4. Karnataka Geo Match
        matched_geo = [g for g in cls.KARNATAKA_GEO_TERMS if re.search(r"\b" + re.escape(g) + r"\b", q_norm)]
        matched_keywords.extend(matched_geo)

        # 5. Welfare Intent Match
        matched_welfare = [w for w in cls.WELFARE_INTENT_TERMS if w in q_norm]
        matched_keywords.extend(matched_welfare)

        # 6. Open Domain Pattern Match
        is_open_domain = any(re.search(pat, q_norm) for pat in cls.OPEN_DOMAIN_PATTERNS)

        # 7. Greeting Pattern Match
        is_greeting = any(re.search(pat, q_norm) for pat in cls.GREETING_PATTERNS)

        # General Scheme intent (asking about government schemes or benefits)
        has_generic_scheme_query = bool(
            re.search(r"\b(scheme|yojana|subsidy|pension|scholarship|ration|welfare|allowance|helpline)\b", q_norm)
        )

        return {
            "query": query,
            "normalized_query": q_norm,
            "has_scheme_entity": len(matched_schemes) > 0,
            "has_portal_entity": len(matched_portals) > 0,
            "has_land_term": len(matched_land) > 0,
            "has_geo_term": len(matched_geo) > 0,
            "has_welfare_intent": len(matched_welfare) > 0,
            "has_generic_scheme_query": has_generic_scheme_query,
            "is_open_domain": is_open_domain,
            "is_greeting": is_greeting,
            "matched_schemes": matched_schemes,
            "matched_portals": matched_portals,
            "matched_land": matched_land,
            "matched_geo": matched_geo,
            "matched_welfare": matched_welfare,
            "matched_keywords": list(dict.fromkeys(matched_keywords)),  # deduplicate preserving order
        }


class DecisionTreeRouter:
    """
    Formal Hierarchical Decision Tree evaluating whether a query belongs to
    the Karnataka Government RAG knowledge base or Google Gemini general LLM.
    """

    def __init__(self):
        self.root = self._build_decision_tree()
        logger.info("DecisionTreeRouter initialized with hierarchical rules.")

    def _build_decision_tree(self) -> DecisionNode:
        """
        Constructs the hierarchical Decision Tree nodes:

        Root: Check Explicit Karnataka Schemes / Portals
         |-- TRUE  -> RAG Leaf (High confidence: 0.98)
         |-- FALSE -> Node 2: Check Karnataka Land / Revenue Terms (RTC, Pahani, Form 9/11)
              |-- TRUE  -> RAG Leaf (High confidence: 0.95)
              |-- FALSE -> Node 3: Check Specific Welfare Intents (free electricity, 2000 rs, borewell, etc.)
                   |-- TRUE  -> RAG Leaf (High confidence: 0.92)
                   |-- FALSE -> Node 4: Check Generic Scheme Intent + Karnataka Geo Context
                        |-- TRUE  -> RAG Leaf (Medium confidence: 0.88)
                        |-- FALSE -> Node 5: Check Open Domain Patterns or Non-State Topics
                             |-- TRUE  -> GEMINI Leaf (High confidence: 0.95)
                             |-- FALSE -> Node 6: Check Greetings / Chitchat
                                  |-- TRUE  -> GEMINI Leaf (Confidence: 0.90)
                                  |-- FALSE -> GEMINI Default Leaf (Confidence: 0.80)
        """

        # --- Leaf Nodes ---
        leaf_rag_scheme = DecisionNode(
            name="Leaf: Karnataka Scheme/Portal Match",
            leaf_target=RoutingTarget.RAG,
            leaf_category="Karnataka Guarantee Schemes & Portals",
            leaf_confidence=0.98,
            explanation="Query explicitly matches official Government of Karnataka guarantee scheme or citizen portal.",
        )

        leaf_rag_land = DecisionNode(
            name="Leaf: Karnataka Land & Revenue Records",
            leaf_target=RoutingTarget.RAG,
            leaf_category="Karnataka Land & Revenue Administration",
            leaf_confidence=0.95,
            explanation="Query inquires about Karnataka land administration, RTC, Pahani, mutation, or e-Swathu property records.",
        )

        leaf_rag_welfare = DecisionNode(
            name="Leaf: Karnataka Citizen Welfare Intent",
            leaf_target=RoutingTarget.RAG,
            leaf_category="Karnataka Citizen Welfare & Subsidies",
            leaf_confidence=0.92,
            explanation="Query matches specific welfare services (e.g. 200 units electricity, ₹2000 women aid, borewell subsidy, bus pass).",
        )

        leaf_rag_geo_scheme = DecisionNode(
            name="Leaf: Karnataka Scheme Inferred via Context",
            leaf_target=RoutingTarget.RAG,
            leaf_category="General Karnataka Government Services",
            leaf_confidence=0.88,
            explanation="Query combines citizen scheme or welfare request with explicit Karnataka administrative jurisdiction.",
        )

        leaf_gemini_open_domain = DecisionNode(
            name="Leaf: Open Domain / General Knowledge",
            leaf_target=RoutingTarget.GEMINI,
            leaf_category="Open Domain & World Knowledge",
            leaf_confidence=0.95,
            explanation="Query is outside Karnataka Government scope (e.g., science, technology, world geography, history, general reasoning).",
        )

        leaf_gemini_greeting = DecisionNode(
            name="Leaf: Conversational Greeting / Chitchat",
            leaf_target=RoutingTarget.GEMINI,
            leaf_category="Conversational Greeting",
            leaf_confidence=0.90,
            explanation="Query is a conversational greeting or general assistant inquiry best handled by conversational Gemini.",
        )

        leaf_gemini_default = DecisionNode(
            name="Leaf: Default External Knowledge",
            leaf_target=RoutingTarget.GEMINI,
            leaf_category="General Knowledge",
            leaf_confidence=0.80,
            explanation="Query does not contain verified Karnataka Government citizen service entities; routing to Google Gemini.",
        )

        # --- Intermediate Decision Nodes (constructed bottom-up) ---

        # Node 6: Check Greetings
        node_greetings = DecisionNode(
            name="Node 6: Is Greeting or General Assistant Query?",
            condition_fn=lambda f: f["is_greeting"],
            true_node=leaf_gemini_greeting,
            false_node=leaf_gemini_default,
        )

        # Node 5: Check Open Domain Patterns
        node_open_domain = DecisionNode(
            name="Node 5: Has Open Domain / Global Topic Pattern?",
            condition_fn=lambda f: f["is_open_domain"],
            true_node=leaf_gemini_open_domain,
            false_node=node_greetings,
        )

        # Node 4: Check Generic Scheme + Karnataka Geo Context
        node_geo_scheme = DecisionNode(
            name="Node 4: Has Welfare/Scheme Request with Karnataka Context?",
            condition_fn=lambda f: f["has_generic_scheme_query"] and (f["has_geo_term"] or not f["is_open_domain"]),
            true_node=leaf_rag_geo_scheme,
            false_node=node_open_domain,
        )

        # Node 3: Check Specific Welfare Intents
        node_welfare = DecisionNode(
            name="Node 3: Matches Karnataka Welfare Intent Signals?",
            condition_fn=lambda f: f["has_welfare_intent"],
            true_node=leaf_rag_welfare,
            false_node=node_geo_scheme,
        )

        # Node 2: Check Land & Revenue Terms
        node_land = DecisionNode(
            name="Node 2: Inquires About Karnataka Land/Revenue (RTC/Pahani/e-Swathu)?",
            condition_fn=lambda f: f["has_land_term"],
            true_node=leaf_rag_land,
            false_node=node_welfare,
        )

        # Root / Node 1: Check Explicit Karnataka Scheme / Portal
        root_node = DecisionNode(
            name="Node 1: Mentions Explicit Karnataka Scheme or Portal?",
            condition_fn=lambda f: f["has_scheme_entity"] or f["has_portal_entity"],
            true_node=leaf_rag_scheme,
            false_node=node_land,
        )

        return root_node

    def evaluate(self, query: str) -> DecisionTrace:
        """
        Executes the Decision Tree on the user query and returns a structured DecisionTrace.
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return DecisionTrace(
                target=RoutingTarget.GEMINI,
                confidence=0.5,
                category="Empty Input",
                matched_rules=[],
                decision_path=["Root -> Empty Query Detected"],
                explanation="Input query was empty or whitespace.",
            )

        features = FeatureExtractor.extract_features(clean_q)
        trace = self.root.evaluate(features)

        logger.info(
            "Decision Tree evaluated query: target=%s, category='%s', confidence=%.2f, rules=%s",
            trace.target.value,
            trace.category,
            trace.confidence,
            trace.matched_rules,
        )
        return trace

    def get_ascii_tree(self) -> str:
        """Returns a human-readable ASCII representation of the Decision Tree."""
        return """
================================================================================
                    AWAAZ SETU DECISION TREE ROUTER
================================================================================
[Root: Evaluate Inbound Query]
  |
  +-- [Node 1: Explicit Karnataka Scheme or Portal?]
  |     |-- YES --> [TARGET: RAG] (Karnataka Guarantee Schemes & Portals)
  |     +-- NO
  |          |
  |          +-- [Node 2: Land/Revenue Records (RTC, Pahani, Mutation, e-Swathu)?]
  |                |-- YES --> [TARGET: RAG] (Karnataka Land & Revenue Admin)
  |                +-- NO
  |                     |
  |                     +-- [Node 3: Welfare Signals (₹2000, 200 units, borewell, etc.)?]
  |                           |-- YES --> [TARGET: RAG] (Citizen Welfare & Subsidies)
  |                           +-- NO
  |                                |
  |                                +-- [Node 4: Scheme Query with Karnataka Context?]
  |                                      |-- YES --> [TARGET: RAG] (General GOK Services)
  |                                      +-- NO
  |                                           |
  |                                           +-- [Node 5: Open Domain / Non-State Question?]
  |                                                 |-- YES --> [TARGET: GEMINI] (Open Domain)
  |                                                 +-- NO
  |                                                      |
  |                                                      +-- [Node 6: Conversational Greeting?]
  |                                                            |-- YES --> [TARGET: GEMINI] (Greeting)
  |                                                            +-- NO  --> [TARGET: GEMINI] (Default)
================================================================================
        """

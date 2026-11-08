"""
Decision Tree Node & Data Structures for Awaaz Setu.

Architectural Context:
- Represents formal Decision Tree nodes, rules, and branching evaluations.
- Takes queries and resolves whether they belong to:
    1. Karnataka Government RAG (state schemes, welfare, land records, citizen portals)
    2. Google Gemini (open domain, general reasoning, global knowledge, non-Karnataka questions)
- Generates transparent, audit-ready decision paths for telemetry, judges, and developers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RoutingTarget(str, Enum):
    RAG = "RAG"
    GEMINI = "GEMINI"


@dataclass
class DecisionTrace:
    target: RoutingTarget
    confidence: float
    category: str
    matched_rules: List[str]
    decision_path: List[str]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.value,
            "confidence": self.confidence,
            "category": self.category,
            "matched_rules": self.matched_rules,
            "decision_path": self.decision_path,
            "explanation": self.explanation,
        }


class DecisionNode:
    """
    A single node within the hierarchical Decision Tree.
    Evaluates a condition and branches to left/right child nodes or produces a leaf DecisionTrace.
    """

    def __init__(
        self,
        name: str,
        condition_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        true_node: Optional["DecisionNode"] = None,
        false_node: Optional["DecisionNode"] = None,
        leaf_target: Optional[RoutingTarget] = None,
        leaf_category: str = "",
        leaf_confidence: float = 1.0,
        explanation: str = "",
    ):
        self.name = name
        self.condition_fn = condition_fn
        self.true_node = true_node
        self.false_node = false_node
        self.leaf_target = leaf_target
        self.leaf_category = leaf_category
        self.leaf_confidence = leaf_confidence
        self.explanation = explanation

    @property
    def is_leaf(self) -> bool:
        return self.leaf_target is not None

    def evaluate(self, features: Dict[str, Any], path: Optional[List[str]] = None) -> DecisionTrace:
        """Recursively traverses the tree based on extracted features."""
        if path is None:
            path = []

        path.append(self.name)

        if self.is_leaf:
            matched_keywords = features.get("matched_keywords", [])
            return DecisionTrace(
                target=self.leaf_target,  # type: ignore
                confidence=self.leaf_confidence,
                category=self.leaf_category,
                matched_rules=matched_keywords,
                decision_path=path,
                explanation=self.explanation,
            )

        if self.condition_fn and self.condition_fn(features):
            path.append(f"-> True ({self.name})")
            if self.true_node:
                return self.true_node.evaluate(features, path)
        else:
            path.append(f"-> False ({self.name})")
            if self.false_node:
                return self.false_node.evaluate(features, path)

        # Fallback leaf
        return DecisionTrace(
            target=RoutingTarget.GEMINI,
            confidence=0.5,
            category="Default External",
            matched_rules=[],
            decision_path=path,
            explanation="Tree evaluated to fallback terminal node.",
        )

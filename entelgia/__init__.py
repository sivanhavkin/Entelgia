#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Enhanced Dialogue Package
Provides improved dialogue quality through dynamic speaker selection, rich personas, and intelligent context management.

Version Note: Pronoun support feature added for v2.2.0
Latest official release: v2.9.0
"""

from .dialogue_engine import DialogueEngine, SeedGenerator
from .enhanced_personas import (
    SOCRATES_PERSONA,
    ATHENA_PERSONA,
    FIXY_PERSONA,
    format_persona_for_prompt,
    get_persona,
    get_typical_opening,
    is_global_show_pronouns,
)
from .context_manager import ContextManager, EnhancedMemoryIntegration
from .fixy_interactive import (
    InteractiveFixy,
    FixyMode,
    FixyGuidance,
    MOVE_TYPES,
    validate_force_choice,
)
from .energy_regulation import FixyRegulator, EntelgiaAgent
from .long_term_memory import DefenseMechanism, FreudianSlip, SelfReplication
from .dialogue_metrics import (
    circularity_rate,
    circularity_per_turn,
    progress_rate,
    intervention_utility,
    compute_all_metrics,
)
from .ablation_study import (
    AblationCondition,
    run_condition,
    run_ablation,
    print_results_table,
    plot_circularity,
)
from .loop_guard import (
    DialogueLoopDetector,
    PhraseBanList,
    DialogueRewriter,
    TOPIC_CLUSTERS,
)
from .dialogue_engine import AgentMode
from .topic_style import (
    TOPIC_STYLE,
    TOPIC_TONE_POLICY,
    DEFAULT_TOPIC_CLUSTER,
    get_style_for_cluster,
    get_style_for_topic,
    build_style_instruction,
    scrub_rhetorical_openers,
)
from .circularity_guard import (
    CircularityResult,
    detect_semantic_repetition,
    detect_structural_templates,
    detect_cross_topic_contamination,
    compute_circularity_score,
    get_dynamic_threshold,
    add_to_history as circularity_add_to_history,
    get_agent_history as circularity_get_agent_history,
    clear_history as circularity_clear_history,
    get_new_angle_instruction,
)
from .topic_enforcer import (
    compute_topic_compliance_score,
    build_soft_reanchor_instruction,
    topic_pipeline_enabled,
    ACCEPT_THRESHOLD,
    SOFT_REANCHOR_THRESHOLD,
)
from .fixy_semantic_control import (
    ValidationResult,
    LoopCheckResult,
    FixySemanticController,
    VALIDATED_MOVE_TYPES,
    LOOP_BREAKING_MOVES,
    quick_example_hint,
    quick_test_hint,
    apply_validation_to_progress,
    apply_loop_to_progress,
)
from .integration_core import (
    IntegrationCore,
    IntegrationMode,
    IntegrationState,
    ControlDecision,
    EscalationLevel,
    detect_pseudo_compliance,
    make_integration_state,
)

__all__ = [
    "DialogueEngine",
    "SeedGenerator",
    "AgentMode",
    "SOCRATES_PERSONA",
    "ATHENA_PERSONA",
    "FIXY_PERSONA",
    "format_persona_for_prompt",
    "get_persona",
    "get_typical_opening",
    "ContextManager",
    "EnhancedMemoryIntegration",
    "InteractiveFixy",
    "FixyMode",
    "FixyGuidance",
    "MOVE_TYPES",
    "validate_force_choice",
    "is_global_show_pronouns",
    "FixyRegulator",
    "EntelgiaAgent",
    "DefenseMechanism",
    "FreudianSlip",
    "SelfReplication",
    "circularity_rate",
    "circularity_per_turn",
    "progress_rate",
    "intervention_utility",
    "compute_all_metrics",
    "AblationCondition",
    "run_condition",
    "run_ablation",
    "print_results_table",
    "plot_circularity",
    "DialogueLoopDetector",
    "PhraseBanList",
    "DialogueRewriter",
    "TOPIC_CLUSTERS",
    "TOPIC_STYLE",
    "TOPIC_TONE_POLICY",
    "DEFAULT_TOPIC_CLUSTER",
    "get_style_for_cluster",
    "get_style_for_topic",
    "build_style_instruction",
    "scrub_rhetorical_openers",
    "CircularityResult",
    "detect_semantic_repetition",
    "detect_structural_templates",
    "detect_cross_topic_contamination",
    "compute_circularity_score",
    "get_dynamic_threshold",
    "circularity_add_to_history",
    "circularity_get_agent_history",
    "circularity_clear_history",
    "get_new_angle_instruction",
    "compute_topic_compliance_score",
    "build_soft_reanchor_instruction",
    "topic_pipeline_enabled",
    "ACCEPT_THRESHOLD",
    "SOFT_REANCHOR_THRESHOLD",
    "ValidationResult",
    "LoopCheckResult",
    "FixySemanticController",
    "VALIDATED_MOVE_TYPES",
    "LOOP_BREAKING_MOVES",
    "quick_example_hint",
    "quick_test_hint",
    "apply_validation_to_progress",
    "apply_loop_to_progress",
    "IntegrationCore",
    "IntegrationMode",
    "IntegrationState",
    "ControlDecision",
    "EscalationLevel",
    "detect_pseudo_compliance",
    "make_integration_state",
]

__version__ = "5.0.0"

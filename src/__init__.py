"""talon-rig-core - Shared core library for device rigs

Re-exports all public symbols for convenient access via:
    core = actions.user.rig_core()
    core.Vec2, core.BaseRigState, core.PropertyKind, etc.
"""

# Vec2 and math
from .vec2 import Vec2, is_vec2, EPSILON
from .math_utils import lerp, clamp, normalize_vector

# Easing
from .easing import (
    get_easing_function,
    EASING_FUNCTIONS,
    ease_linear, ease_in, ease_out, ease_in_out,
    ease_in2, ease_out2, ease_in_out2,
    ease_in3, ease_out3, ease_in_out3,
    ease_in4, ease_out4, ease_in_out4,
)

# Property kind system
from .property_kind import PropertyKind, PropertySchema, zero_value_for_kind, identity_value_for_kind

# Contracts and validation
from .contracts import (
    BaseBuilderConfig,
    LifecyclePhase,
    LayerType,
    ConfigError,
    RigAttributeError,
    RigUsageError,
    validate_timing,
    validate_has_operation,
    find_closest_match,
    suggest_correction,
    format_validation_error,
    VALID_MODES,
    VALID_EASINGS,
    VALID_INTERPOLATIONS,
    VALID_BEHAVIORS,
    METHOD_SIGNATURES,
    PARAMETER_SUGGESTIONS,
)

# Lifecycle
from .lifecycle import Lifecycle

# Property animator
from .property_animator import (
    PropertyAnimator,
    calculate_vector_transition,
)

# Rate utilities
from . import rate_utils

# Mode operations
from . import mode_operations

# Queue system
from .queue import BuilderQueue, QueueManager

# Layer group
from .layer_group import BaseLayerGroup

# Base classes (ABCs)
from .state import BaseRigState
from .builder import BaseActiveBuilder

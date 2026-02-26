"""Type contracts, validation infrastructure, and base configuration

Shared between all device rigs. Device rigs subclass BaseBuilderConfig
to add device-specific fields.
"""

from typing import Callable, Any, Optional


# ============================================================================
# LAYER CLASSIFICATION
# ============================================================================

class LifecyclePhase:
    """Represents a phase in the lifecycle (over/hold/revert)"""
    OVER = "over"
    HOLD = "hold"
    REVERT = "revert"


class LayerType:
    """Layer type classification"""
    BASE = "base"                           # base.{property} - transient, auto-bakes
    AUTO_NAMED_MODIFIER = "auto_modifier"   # {property}.{mode} - persistent, auto-named
    USER_NAMED_MODIFIER = "user_modifier"   # custom name + mode - persistent, user-named


# ============================================================================
# VALID OPTIONS
# ============================================================================

VALID_MODES = ['offset', 'override', 'scale']

VALID_EASINGS = [
    'linear',
    'ease_in', 'ease_out', 'ease_in_out',
    'ease_in2', 'ease_out2', 'ease_in_out2',
    'ease_in3', 'ease_out3', 'ease_in_out3',
    'ease_in4', 'ease_out4', 'ease_in_out4',
]

VALID_INTERPOLATIONS = ['lerp', 'slerp', 'linear']

VALID_BEHAVIORS = ['stack', 'replace', 'queue', 'throttle', 'debounce']

METHOD_SIGNATURES = {
    'over': {
        'params': ['ms', 'easing', 'rate', 'interpolation'],
        'signature': "over(ms=None, easing='linear', *, rate=None, interpolation='lerp')",
        'validations': {
            'easing': ('easing', VALID_EASINGS),
            'interpolation': ('interpolation', VALID_INTERPOLATIONS)
        }
    },
    'revert': {
        'params': ['ms', 'easing', 'rate', 'interpolation'],
        'signature': "revert(ms=None, easing='linear', *, rate=None, interpolation='lerp')",
        'validations': {
            'easing': ('easing', VALID_EASINGS),
            'interpolation': ('interpolation', VALID_INTERPOLATIONS)
        }
    },
    'hold': {
        'params': ['ms'],
        'signature': 'hold(ms)',
        'validations': {}
    },
    'then': {
        'params': ['callback'],
        'signature': 'then(callback)',
        'validations': {}
    },
    'stop': {
        'params': ['transition_ms', 'easing'],
        'signature': "stop(transition_ms=None, easing='linear')",
        'validations': {
            'easing': ('easing', VALID_EASINGS)
        }
    },
    'bake': {
        'params': ['value'],
        'signature': 'bake(value=True)',
        'validations': {}
    },
    'max': {
        'params': ['value'],
        'signature': 'max(value)',
        'validations': {}
    },
    'min': {
        'params': ['value'],
        'signature': 'min(value)',
        'validations': {}
    }
}

# Add behavior methods
for _behavior in VALID_BEHAVIORS:
    if _behavior in ('throttle', 'debounce'):
        METHOD_SIGNATURES[_behavior] = {
            'params': ['ms'],
            'signature': f'{_behavior}(ms=None)',
            'validations': {}
        }
    elif _behavior == 'stack':
        METHOD_SIGNATURES[_behavior] = {
            'params': ['max'],
            'signature': f'{_behavior}(max=None)',
            'validations': {}
        }
    else:
        METHOD_SIGNATURES[_behavior] = {
            'params': [],
            'signature': f'{_behavior}()',
            'validations': {}
        }

# Common typos and their corrections
PARAMETER_SUGGESTIONS = {
    'ease': 'easing',
    'duration': 'ms',
    'time': 'ms',
    'milliseconds': 'ms',
    'millis': 'ms',
    'transition': 'ms',
}


# ============================================================================
# VALIDATION ERROR HANDLING
# ============================================================================

class ConfigError(TypeError):
    """Configuration validation error with rich formatting"""
    pass


class RigAttributeError(AttributeError):
    """Attribute error with helpful suggestions"""
    pass


class RigUsageError(Exception):
    """Error for incorrect API usage"""
    pass


def find_closest_match(name: str, valid_options: list[str], max_distance: int = 2) -> Optional[str]:
    """Find closest match using simple edit distance"""
    name_lower = name.lower()
    best_match = None
    best_distance = max_distance + 1

    for option in valid_options:
        option_lower = option.lower()
        if name_lower in option_lower or option_lower in name_lower:
            return option
        distance = _levenshtein(name_lower, option_lower)
        if distance < best_distance:
            best_distance = distance
            best_match = option

    return best_match if best_distance <= max_distance else None


def _levenshtein(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def suggest_correction(provided: str, valid_options: list[str]) -> Optional[str]:
    """Find close match for typos using simple heuristics"""
    provided_lower = provided.lower()
    if provided_lower in PARAMETER_SUGGESTIONS:
        return PARAMETER_SUGGESTIONS[provided_lower]
    for option in valid_options:
        if provided_lower in option.lower() or option.lower() in provided_lower:
            return option
    return None


def format_validation_error(
    method: str,
    unknown_params: Optional[list[str]] = None,
    invalid_values: Optional[dict[str, tuple[Any, list]]] = None,
    provided_kwargs: Optional[dict] = None
) -> str:
    """Format a comprehensive validation error message"""
    schema = METHOD_SIGNATURES.get(method, {})
    signature = schema.get('signature', f'{method}(...)')

    msg = f"{method}() validation failed\n"
    msg += f"\nSignature: {signature}\n"

    if provided_kwargs:
        provided_str = ', '.join(f"{k}={repr(v)}" for k, v in provided_kwargs.items())
        msg += f"You provided: {provided_str}\n"

    if unknown_params:
        msg += f"\nUnknown parameter(s): {', '.join(repr(p) for p in unknown_params)}\n"
        suggestions = []
        valid_params = schema.get('params', [])
        for param in unknown_params:
            suggestion = suggest_correction(param, valid_params)
            if suggestion:
                suggestions.append(f"  - '{param}' -> '{suggestion}'")
        if suggestions:
            msg += "\nDid you mean:\n" + "\n".join(suggestions) + "\n"

    if invalid_values:
        msg += "\nInvalid value(s):\n"
        for param, (value, valid_options) in invalid_values.items():
            msg += f"  - {param}={repr(value)}\n"
            msg += f"    Valid options: {', '.join(repr(v) for v in valid_options)}\n"
            if isinstance(value, str):
                suggestion = suggest_correction(value, valid_options)
                if suggestion:
                    msg += f"    Did you mean: {repr(suggestion)}?\n"

    return msg


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_timing(value: Any, param_name: str, method: str = None, mark_invalid: Optional[Callable[[], None]] = None) -> Optional[float]:
    """Validate timing parameters (ms, rate, etc.)"""
    if value is None:
        return None

    method_str = f".{method}({param_name}=...)" if method else f"'{param_name}'"

    if not isinstance(value, (int, float)):
        if mark_invalid:
            mark_invalid()
        raise TypeError(
            f"Invalid type for {method_str}\n\n"
            f"Expected: number (int or float)\n"
            f"Got: {type(value).__name__} = {repr(value)}\n\n"
            f"Timing parameters must be numeric values."
        )

    float_value = float(value)

    if float_value < 0:
        if mark_invalid:
            mark_invalid()
        raise ConfigError(
            f"Negative duration not allowed: {method_str}\n\n"
            f"Got: {value}\n\n"
            f"Duration values must be >= 0."
        )

    return float_value


def validate_has_operation(config: 'BaseBuilderConfig', method_name: str, mark_invalid: Optional[Callable[[], None]] = None) -> None:
    """Validate that a timing method has a prior operation to apply to"""
    if config.property is None or config.operator is None:
        if mark_invalid:
            mark_invalid()
        raise RigUsageError(
            f"Cannot call .{method_name}() without a prior operation. "
            f"You must set a property (e.g., .speed.to(5), .direction.by(90)) before calling .{method_name}()."
        )


# ============================================================================
# BASE BUILDER CONFIG
# ============================================================================

class BaseBuilderConfig:
    """Configuration collected by builder during fluent API calls.

    Contains all shared fields. Device rigs subclass to add their own:
    - Mouse adds: input_type, movement_type, api_override, max_value, min_value, is_synchronous, by_lines
    - Gamepad adds: subproperty
    """
    def __init__(self):
        # Property and operator
        self.property: Optional[str] = None  # pos, speed, direction, etc.
        self.operator: Optional[str] = None  # to, by, add, sub, mul, div
        self.value: Any = None
        self.mode: Optional[str] = None  # 'offset', 'override', or 'scale'
        self.order: Optional[int] = None  # Explicit layer ordering

        # Identity
        self.layer_name: Optional[str] = None
        self.layer_type: str = LayerType.BASE
        self.is_user_named: bool = False

        # Behavior
        self.behavior: Optional[str] = None  # stack, replace, queue, throttle
        self.behavior_args: tuple = ()

        # Lifecycle timing
        self.over_ms: Optional[float] = None
        self.over_easing: str = "linear"
        self.over_rate: Optional[float] = None
        self.over_interpolation: str = "lerp"

        self.hold_ms: Optional[float] = None

        self.revert_ms: Optional[float] = None
        self.revert_easing: str = "linear"
        self.revert_rate: Optional[float] = None
        self.revert_interpolation: str = "lerp"

        # Callbacks (stage -> callback)
        self.then_callbacks: list[tuple[str, Callable]] = []

        # Persistence
        self.bake_value: Optional[bool] = None

        # Constraints
        self.max_value: Optional[float] = None
        self.min_value: Optional[float] = None

    # ========================================================================
    # LAYER CLASSIFICATION
    # ========================================================================

    def is_base_layer(self) -> bool:
        return self.layer_type == LayerType.BASE

    def is_modifier_layer(self) -> bool:
        return self.layer_type in (LayerType.AUTO_NAMED_MODIFIER, LayerType.USER_NAMED_MODIFIER)

    def is_auto_named_modifier(self) -> bool:
        return self.layer_type == LayerType.AUTO_NAMED_MODIFIER

    def is_user_named_modifier(self) -> bool:
        return self.layer_type == LayerType.USER_NAMED_MODIFIER

    def get_effective_behavior(self) -> str:
        """Get behavior with defaults applied"""
        if self.behavior is not None:
            return self.behavior
        if self.operator == "to":
            return "replace"
        else:
            return "stack"

    def get_effective_bake(self) -> bool:
        """Get bake setting with defaults applied"""
        if self.bake_value is not None:
            return self.bake_value
        return self.is_base_layer()

    def validate_method_kwargs(self, method: str, mark_invalid: Optional[Callable[[], None]] = None, **kwargs) -> None:
        """Validate kwargs for a method call"""
        if not kwargs:
            return

        schema = METHOD_SIGNATURES.get(method)
        if not schema:
            return

        valid_params = schema['params']
        validations = schema.get('validations', {})

        unknown = [k for k in kwargs.keys() if k not in valid_params]

        invalid_values = {}
        for param, value in kwargs.items():
            if param in validations:
                param_name, valid_options = validations[param]
                if value is not None and value not in valid_options:
                    invalid_values[param] = (value, valid_options)

        if unknown or invalid_values:
            if mark_invalid:
                mark_invalid()
            raise ConfigError(format_validation_error(
                method=method,
                unknown_params=unknown if unknown else None,
                invalid_values=invalid_values if invalid_values else None,
                provided_kwargs=kwargs
            ))

    def validate_easing(self, easing: str, context: str = "easing", mark_invalid: Optional[Callable[[], None]] = None) -> None:
        """Validate an easing value"""
        if easing not in VALID_EASINGS:
            if mark_invalid:
                mark_invalid()
            valid_str = ', '.join(repr(e) for e in VALID_EASINGS)
            suggestion = suggest_correction(easing, VALID_EASINGS)
            msg = f"Invalid {context}: {repr(easing)}\n"
            msg += f"Valid options: {valid_str}"
            if suggestion:
                msg += f"\nDid you mean: {repr(suggestion)}?"
            raise ConfigError(msg)

    def validate_mode(self, mark_invalid: Optional[Callable[[], None]] = None) -> None:
        """Validate that mode is set for layer operations"""
        if not self.is_user_named:
            return

        if self.mode is None:
            if mark_invalid:
                mark_invalid()
            raise ConfigError(
                f"Layer operations require an explicit mode.\n\n"
                f"Available modes (modify the incoming value):\n"
                f"  - .offset   - offset the incoming value\n"
                f"  - .override - replace the incoming value\n"
                f"  - .scale    - multiply the incoming value"
            )

        if self.mode not in VALID_MODES:
            if mark_invalid:
                mark_invalid()
            valid_str = ', '.join(repr(m) for m in VALID_MODES)
            raise ConfigError(
                f"Invalid mode: {repr(self.mode)}\n"
                f"Valid modes: {valid_str}"
            )

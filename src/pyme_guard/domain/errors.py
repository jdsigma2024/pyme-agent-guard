class LLMUnavailableError(Exception):
    """El proveedor de LLM falló, expiró o devolvió una respuesta inválida."""


class SourceUnavailableError(Exception):
    """Un sistema externo (central de riesgo, RADIAN, listas) no respondió."""


class InvalidNitError(ValueError):
    """El NIT no tiene formato válido o su dígito de verificación no coincide."""


class ApplicationNotFoundError(LookupError):
    """La solicitud no existe."""


class InvalidTransitionError(Exception):
    """La acción no es válida en el estado actual de la solicitud (máquina de estados)."""

class FakeLLM:
    """Proveedor determinista para demos y desarrollo sin modelo."""

    def generate(self, system_prompt: str, user_message: str) -> str:
        return (
            "Te oriento con gusto. Para evaluar una línea de financiación suelen pedirse estados "
            "financieros recientes, información de ventas y documentos de la empresa. "
            "Un asesor confirmará las condiciones aplicables a tu caso."
        )

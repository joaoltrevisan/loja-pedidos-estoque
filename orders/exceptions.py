class OrderConflict(Exception):
    """Conflito de negocio esperado; nunca uma falha generica do banco."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class OrderIntegrityConflict(OrderConflict):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(
            "order_integrity_conflict",
            "Historico do pedido inconsistente; nenhuma alteracao aplicada.",
        )

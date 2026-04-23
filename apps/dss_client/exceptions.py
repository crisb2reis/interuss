class DSSException(Exception):
    """Exceção base para erros do DSS."""
    pass


class DSSConnectionError(DSSException):
    """Erro de conexão com o DSS (rede, timeout)."""
    pass


class DSSAuthenticationError(DSSException):
    """Erro de autenticação — token inválido ou expirado (HTTP 401)."""
    pass


class DSSAuthorizationError(DSSException):
    """Sem permissão para o recurso solicitado (HTTP 403)."""
    pass


class DSSNotFoundError(DSSException):
    """Recurso não encontrado no DSS (HTTP 404)."""
    pass


class DSSConflictError(DSSException):
    """Conflito espaço-temporal com outra OIR (HTTP 409)."""

    def __init__(self, message: str, conflicting_references=None):
        super().__init__(message)
        self.conflicting_references = conflicting_references or []


class DSSValidationError(DSSException):
    """Payload inválido enviado ao DSS (HTTP 400)."""
    pass


class DSSServerError(DSSException):
    """Erro interno do servidor DSS (HTTP 5xx)."""
    pass

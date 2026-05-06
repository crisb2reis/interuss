"""
ICEAAuthenticator — Gerencia obtenção e cache de tokens JWT
para comunicação com o DSS do sandbox BR-UTM.

Fluxo:
  USS → GET /token?intended_audience=...&scope=...&apikey=...
      → Recebe JWT (access_token)
      → Armazena em cache Django (TTL = exp - now - 5min)
      → Reutiliza em requisições subsequentes

Auth URL sandbox: https://api.sandbox.br-utm.org/token
"""

import logging
from datetime import datetime, timedelta

import jwt
import requests
from django.conf import settings
from django.core.cache import cache

from .exceptions import DSSAuthenticationError, DSSConnectionError

logger = logging.getLogger(__name__)


class UTMAuthority:
    """
    Constantes de escopo compatíveis com ASTM F3548-22 / BR-UTM sandbox.

    Uso nos scripts de auth:
        from apps.dss_client.auth import UTMAuthority
        token = authenticator.get_token("core-service", UTMAuthority.STRATEGIC_COORDINATION)

    ─── Escopos disponíveis no sandbox (apikey=brutm) ───────────────
    ✅ STRATEGIC_COORDINATION    → utm.strategic_coordination
    ✅ CONSTRAINT_MANAGEMENT     → utm.constraint_management
    ✅ CONSTRAINT_PROCESSING     → utm.constraint_processing
    ✅ CONFORMANCE_MONITORING_SA → utm.conformance_monitoring_sa
    ❌ AVIATION_AUTHORITY        → 403 (não permitido para brutm)
    ❌ AVAILABILITY_ARBITRATION  → 403 (não permitido para brutm)
    """

    # ✅ Coordenação estratégica de intenções operacionais (OIR)
    STRATEGIC_COORDINATION = "utm.strategic_coordination"

    # ❌ Autoridade de aviação — não disponível no sandbox para brutm
    AVIATION_AUTHORITY = "utm.aviation_authority"

    # ✅ Gerenciamento de constraints (restrições de espaço aéreo)
    CONSTRAINT_MANAGEMENT = "utm.constraint_management"

    # ✅ Processamento de constraints por outros USSs
    CONSTRAINT_PROCESSING = "utm.constraint_processing"

    # ✅ Monitoramento de conformidade (SA = Situational Awareness)
    CONFORMANCE_MONITORING_SA = "utm.conformance_monitoring_sa"

    # ❌ Arbitragem de disponibilidade — não disponível no sandbox para brutm
    AVAILABILITY_ARBITRATION = "utm.availability_arbitration"

    # ✅ Alias para strategic_coordination (coordenação entre USSs)
    COORDINATION = "utm.strategic_coordination"

    @classmethod
    def sandbox_allowed_scopes(cls) -> list:
        """Escopos permitidos no sandbox BR-UTM com apikey=brutm."""
        return [
            cls.STRATEGIC_COORDINATION,
            cls.CONSTRAINT_MANAGEMENT,
            cls.CONSTRAINT_PROCESSING,
            cls.CONFORMANCE_MONITORING_SA,
        ]

    @classmethod
    def all_scopes(cls) -> list:
        """Todos os escopos definidos (incluindo os restritos no sandbox)."""
        return [
            cls.STRATEGIC_COORDINATION,
            cls.AVIATION_AUTHORITY,
            cls.CONSTRAINT_MANAGEMENT,
            cls.CONSTRAINT_PROCESSING,
            cls.CONFORMANCE_MONITORING_SA,
            cls.AVAILABILITY_ARBITRATION,
        ]



class ICEAAuthenticator:
    """
    Gerenciador de autenticação JWT contra o servidor ICEA (BR-UTM).

    Attributes:
        CACHE_KEY_PREFIX (str): Prefixo da chave de cache.
        TOKEN_REFRESH_MARGIN (int): Segundos antes do vencimento para renovar.
    """

    CACHE_KEY_PREFIX = "dss_token"
    TOKEN_REFRESH_MARGIN = 300  # 5 minutos antes de expirar

    def __init__(self, auth_url: str = None, api_key: str = None):
        self.auth_url = auth_url or getattr(
            settings, "ICEA_AUTH_URL", "https://api.sandbox.br-utm.org/token"
        )
        self.api_key = api_key or getattr(settings, "ICEA_API_KEY", "")

    # ─── Interface pública ────────────────────────────────────────

    def get_token(self, intended_audience: str, scope: str) -> str:
        """
        Retorna um JWT válido (do cache ou renovando via requisição).

        Args:
            intended_audience: Audience do token (ex: "utm.decea.mil.br").
            scope: Escopo de permissão (ex: "utm.strategic_coordination").

        Returns:
            String do JWT (access_token).

        Raises:
            DSSAuthenticationError: Se a autenticação falhar.
            DSSConnectionError: Se não conseguir conectar ao AUTH.
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}:{intended_audience}:{scope}"

        cached_token = cache.get(cache_key)
        if cached_token and self._is_token_valid(cached_token):
            logger.debug("Token obtido do cache para audience=%s", intended_audience)
            return cached_token

        logger.info(
            "Obtendo novo token do AUTH | audience=%s scope=%s",
            intended_audience,
            scope,
        )
        token = self._authenticate(intended_audience, scope)
        ttl = self._get_token_ttl(token)
        cache.set(cache_key, token, ttl)
        logger.info("Token obtido e cacheado por %ds", ttl)

        return token

    # ─── Métodos internos ─────────────────────────────────────────

    def _authenticate(self, intended_audience: str, scope: str) -> str:
        """Faz a requisição GET /token ao AUTH do ICEA e retorna o access_token."""
        if not intended_audience:
            raise ValueError("intended_audience é obrigatório")
        if not scope:
            raise ValueError("scope é obrigatório")

        params = {
            "intended_audience": intended_audience,
            "scope": scope,
            "apikey": self.api_key,
        }

        try:
            # Envia a chave tanto no params quanto no header para máxima compatibilidade com o Gateway
            headers = {"x-api-key": self.api_key}
            response = requests.get(self.auth_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            access_token = data.get("access_token")

            if not access_token:
                raise DSSAuthenticationError(
                    f"Resposta de autenticação sem access_token. Resposta: {data}"
                )

            return access_token

        except requests.exceptions.ConnectionError as exc:
            raise DSSConnectionError(
                f"Não foi possível conectar ao AUTH: {self.auth_url}. Erro: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise DSSConnectionError(
                f"Timeout ao conectar ao AUTH: {self.auth_url}"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise DSSAuthenticationError(
                f"Falha de autenticação HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise DSSAuthenticationError(f"Erro ao autenticar: {exc}") from exc

    def _is_token_valid(self, token: str) -> bool:
        """Verifica se o token ainda é válido (não expirará nos próximos 5 min)."""
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get("exp")
            if not exp:
                return False

            expiry = datetime.fromtimestamp(exp)
            margin = timedelta(seconds=self.TOKEN_REFRESH_MARGIN)
            return datetime.now() + margin < expiry

        except jwt.DecodeError:
            return False

    def _get_token_ttl(self, token: str) -> int:
        """Calcula o TTL (segundos) para armazenar o token no cache."""
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get("exp")
            if exp:
                ttl = exp - datetime.now().timestamp() - self.TOKEN_REFRESH_MARGIN
                return max(int(ttl), 60)
        except Exception:
            pass
        # Default: 55 minutos se não conseguir decodificar
        return 3300

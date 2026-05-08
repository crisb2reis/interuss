"""
DSSClient — Cliente HTTP para o Discovery and Synchronization Service (DSS)
do sandbox BR-UTM, compatível com ASTM F3548-22.

Uso básico:
    client = DSSClient(
        intended_audience="utm.decea.mil.br",
        scope="utm.strategic_coordination",
    )
    result = client.submit_operational_intent_reference(
        oir_id=str(uuid.uuid4()),
        extents=[{...}],
        uss_base_url="https://meu-uss.ngrok.io",
    )
"""

import json
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

from .auth import ICEAAuthenticator
from .exceptions import (
    DSSAuthenticationError,
    DSSAuthorizationError,
    DSSConflictError,
    DSSConnectionError,
    DSSNotFoundError,
    DSSServerError,
    DSSValidationError,
)

logger = logging.getLogger(__name__)


class DSSClient:
    """
    Cliente robusto para o DSS (Discovery and Synchronization Service).

    Args:
        base_url: URL base do DSS. Default: settings.DSS_BASE_URL.
        token: JWT já disponível (opcional, bypassa autenticação automática).
        intended_audience: Audience para obtenção automática do token.
        scope: Scope para obtenção automática do token.
        auto_authenticate: Se True (default), autentica automaticamente.
    """

    VALID_STATES = ("Accepted", "Activated", "Nonconforming", "Contingent")

    def __init__(
        self,
        base_url: str = None,
        token: str = None,
        intended_audience: str = None,
        scope: str = None,
        auto_authenticate: bool = True,
    ):
        self.base_url = (base_url or getattr(
            settings, "DSS_BASE_URL", "https://api.sandbox.br-utm.org"
        )).rstrip("/")

        self.token = token
        self.authenticator = ICEAAuthenticator()

        if auto_authenticate and not token:
            if not intended_audience or not scope:
                raise ValueError(
                    "intended_audience e scope são obrigatórios para auto_authenticate=True"
                )
            self.token = self.authenticator.get_token(intended_audience, scope)
            logger.debug("DSSClient autenticado com sucesso.")

    # ─── Método central de requisição ────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        json: Dict = None,
        params: Dict = None,
    ) -> Dict[str, Any]:
        """
        Executa uma requisição HTTP ao DSS com Bearer token.

        Raises:
            DSSAuthenticationError: 401
            DSSAuthorizationError: 403
            DSSNotFoundError: 404
            DSSConflictError: 409
            DSSValidationError: 400
            DSSServerError: 5xx
            DSSConnectionError: erros de rede
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        url = f"{self.base_url}{path}"
        logger.info("%s %s", method, url)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params,
                timeout=30,
            )
        except requests.exceptions.ConnectionError as exc:
            raise DSSConnectionError(f"Falha de conexão com o DSS: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise DSSConnectionError("Timeout ao acessar o DSS.") from exc
        except requests.exceptions.RequestException as exc:
            raise DSSConnectionError(f"Erro de rede: {exc}") from exc

        # Tratamento por código HTTP
        if response.status_code == 401:
            raise DSSAuthenticationError(
                f"Token inválido ou expirado [401]: {response.text}"
            )
        if response.status_code == 403:
            raise DSSAuthorizationError(
                f"Acesso negado [403]: {response.text}"
            )
        if response.status_code == 404:
            raise DSSNotFoundError(
                f"Recurso não encontrado [404]: {response.text}"
            )
        if response.status_code == 409:
            try:
                error_data = response.json()
                # O DSS pode retornar conflitos como OIRs ou Constraints ausentes.
                # É preciso coletar AMBOS para poder passar os OVNs corretos no retry.
                missing_oirs = error_data.get("missing_operational_intents", []) \
                    or error_data.get("operational_intent_references", [])
                missing_constraints = error_data.get("missing_constraints", [])
                conflicting = missing_oirs + missing_constraints
                raise DSSConflictError(
                    f"Conflito detectado [409]: {response.text}",
                    conflicting_references=conflicting,
                )
            except DSSConflictError:
                raise
            except Exception:
                raise DSSConflictError(f"Conflito [409]: {response.text}")
        if response.status_code == 400:
            raise DSSValidationError(
                f"Dados inválidos [400]: {response.text}"
            )
        if response.status_code >= 500:
            raise DSSServerError(
                f"Erro interno do DSS [{response.status_code}]: {response.text}"
            )
        if response.status_code >= 400:
            raise DSSConnectionError(
                f"Erro HTTP [{response.status_code}]: {response.text}"
            )

        logger.debug("Resposta %d de %s", response.status_code, url)
        return response.json() if response.text.strip() else {}

    # ─── Constraints ─────────────────────────────────────────────

    # ─── Constraints (Constraint References) ─────────────────────

    def query_constraint_references(self, area: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta constraint references filtradas por área.
        POST /dss/v1/constraint_references/query

        Args:
            area: Dicionário com volume 4D (outline_polygon + altitudes + tempo).
        """
        if not area or not isinstance(area, dict):
            raise DSSValidationError("área deve ser um dicionário não vazio.")

        return self._request(
            "POST",
            "/dss/v1/constraint_references/query",
            json={"area_of_interest": area},
        )

    def get_constraint_reference(self, constraint_id: str) -> Dict[str, Any]:
        """
        Obtém detalhes de uma constraint específica no DSS.
        GET /dss/v1/constraint_references/{entityid}
        """
        if not constraint_id:
            raise DSSValidationError("constraint_id é obrigatório.")
        return self._request("GET", f"/dss/v1/constraint_references/{constraint_id}")

    def get_constraint_details_from_provider(
        self,
        constraint_id: str,
        cp_uss_base_url: str,
    ) -> Dict[str, Any]:
        """
        Busca os detalhes completos de uma Constraint diretamente no
        Constraint Provider (CP), conforme fluxo ASTM F3548-21.

        Fluxo:
            USS → AUTH: GET /token?aud=<domínio do CP>&scope=utm.constraint_processing
            USS → CP:   GET {cp_uss_base_url}/uss/v1/constraints/{constraint_id}

        Args:
            constraint_id: ID da constraint conforme retornado pelo DSS.
            cp_uss_base_url: URL base do Constraint Provider (campo uss_base_url
                             retornado na constraint reference do DSS).

        Returns:
            Dicionário com os detalhes completos da constraint.

        Raises:
            DSSValidationError: Se os argumentos forem inválidos.
            DSSAuthenticationError: Se o token para o CP não puder ser obtido.
            DSSConnectionError: Se a chamada ao CP falhar.
        """
        if not constraint_id:
            raise DSSValidationError("constraint_id é obrigatório.")
        if not cp_uss_base_url:
            raise DSSValidationError("cp_uss_base_url é obrigatório.")

        cp_base = cp_uss_base_url.rstrip("/")

        # Extrai o domínio da URL do CP para usar como audience do JWT
        parsed = urllib.parse.urlparse(cp_base)
        cp_audience = parsed.netloc  # ex: "cp.sandbox.br-utm.org"

        logger.info(
            "Obtendo token para Constraint Provider | audience=%s scope=utm.constraint_processing",
            cp_audience,
        )

        # Autenticar com audience do CP e escopo de processamento de constraints
        cp_token = self.authenticator.get_token(
            intended_audience=cp_audience,
            scope="utm.constraint_processing",
        )

        # Fazer GET no endpoint USS do Constraint Provider
        cp_url = f"{cp_base}/uss/v1/constraints/{constraint_id}"
        logger.info("GET %s", cp_url)

        headers = {
            "Authorization": f"Bearer {cp_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.get(cp_url, headers=headers, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise DSSConnectionError(
                f"Falha de conexão com o Constraint Provider {cp_base}: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise DSSConnectionError(
                f"Timeout ao acessar o Constraint Provider {cp_base}."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise DSSConnectionError(f"Erro de rede ao acessar CP: {exc}") from exc

        if response.status_code == 401:
            raise DSSAuthenticationError(
                f"Token inválido para o Constraint Provider [401]: {response.text}"
            )
        if response.status_code == 403:
            raise DSSAuthorizationError(
                f"Acesso negado ao Constraint Provider [403]: {response.text}"
            )
        if response.status_code == 404:
            raise DSSNotFoundError(
                f"Constraint {constraint_id} não encontrada no CP [404]: {response.text}"
            )
        if response.status_code >= 400:
            raise DSSConnectionError(
                f"Erro HTTP [{response.status_code}] ao acessar CP: {response.text}"
            )

        logger.info(
            "Detalhes da constraint %s obtidos do CP %s", constraint_id, cp_base
        )
        return response.json() if response.text.strip() else {}

    # ─── Operational Intent References (OIR) ─────────────────────

    def create_operational_intent_reference(
        self,
        oir_id: str,
        extents: List[Dict[str, Any]],
        uss_base_url: str,
        state: str = "Accepted",
        subscription_id: Optional[str] = None,
        key: Optional[List[str]] = None,
        new_subscription: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Cria uma nova OIR no DSS.
        PUT /dss/v1/operational_intent_references/{entityid}
        """
        payload = self._build_oir_payload(extents, uss_base_url, state, subscription_id, key, new_subscription)
        path = f"/dss/v1/operational_intent_references/{oir_id}"
        return self._handle_oir_response(self._request("PUT", path, json=payload), oir_id)

    def update_operational_intent_reference(
        self,
        oir_id: str,
        ovn: str,
        extents: List[Dict[str, Any]],
        uss_base_url: str,
        state: str = "Accepted",
        subscription_id: Optional[str] = None,
        key: Optional[List[str]] = None,
        new_subscription: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Atualiza uma OIR existente no DSS.
        PUT /dss/v1/operational_intent_references/{entityid}/{ovn}
        """
        if not ovn:
            raise DSSValidationError("ovn é obrigatório para atualizar uma OIR.")
        
        payload = self._build_oir_payload(extents, uss_base_url, state, subscription_id, key, new_subscription)
        
        print(f"\n[DSS-CLIENT DEBUG] ENVIANDO UPDATE PARA OIR: {oir_id}")
        print(json.dumps(payload, indent=2))
        print("-" * 40 + "\n")

        path = f"/dss/v1/operational_intent_references/{oir_id}/{ovn}"
        return self._handle_oir_response(self._request("PUT", path, json=payload), oir_id)

    def submit_operational_intent_reference(
        self,
        oir_id: str,
        extents: List[Dict[str, Any]],
        uss_base_url: str,
        state: str = "Accepted",
        ovn: Optional[str] = None,
        subscription_id: Optional[str] = None,
        key: Optional[List[str]] = None,
        new_subscription: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Método de conveniência (facade) que decide entre create ou update.
        Se 'ovn' for fornecido, chama update; caso contrário, chama create.
        """
        if ovn:
            return self.update_operational_intent_reference(
                oir_id, ovn, extents, uss_base_url, state, subscription_id, key, new_subscription
            )
        else:
            return self.create_operational_intent_reference(
                oir_id, extents, uss_base_url, state, subscription_id, key, new_subscription
            )

    def _build_oir_payload(self, extents, uss_base_url, state, subscription_id, key, new_subscription) -> Dict:
        """Helper para construir o payload da OIR."""
        if not extents:
            raise DSSValidationError("extents é obrigatório.")
        if state not in self.VALID_STATES:
            raise DSSValidationError(f"state inválido '{state}'. Use um de: {self.VALID_STATES}")

        payload = {
            "extents": extents,
            "uss_base_url": uss_base_url,
            "state": state,
        }
        if subscription_id: payload["subscription_id"] = subscription_id
        if key: payload["key"] = key
        if new_subscription: payload["new_subscription"] = new_subscription
        return payload

    def _handle_oir_response(self, response: Dict, oir_id: str) -> Dict:
        """Helper para processar a resposta do DSS para OIRs."""
        neighbors = response.get("operational_intent_references", [])
        conflicting = [o for o in neighbors if o.get("id") != oir_id]

        return {
            "operational_intent_reference": response.get("operational_intent_reference", {}),
            "subscribers": response.get("subscribers", []),
            "conflicting_oirs": conflicting,
        }

    def get_operational_intent_reference(self, oir_id: str) -> Dict[str, Any]:
        """
        Obtém detalhes de uma OIR específica.
        GET /dss/v1/operational_intent_references/{id}
        """
        if not oir_id:
            raise DSSValidationError("oir_id é obrigatório.")
        return self._request("GET", f"/dss/v1/operational_intent_references/{oir_id}")

    def delete_operational_intent_reference(
        self,
        oir_id: str,
        ovn: str,
    ) -> Dict[str, Any]:
        """
        Remove uma OIR do DSS.
        DELETE /dss/v1/operational_intent_references/{id}/{ovn}

        Args:
            oir_id: ID da OIR.
            ovn: OVN atual da OIR (Obrigatório na spec ASTM).
        """
        if not oir_id or not ovn:
            raise DSSValidationError("oir_id e ovn são obrigatórios para deletar.")

        path = f"/dss/v1/operational_intent_references/{oir_id}/{ovn}"
        return self._request("DELETE", path)

    def query_operational_intent_references(
        self,
        area: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Consulta OIRs por área geográfica/temporal.
        POST /dss/v1/operational_intent_references/query
        """
        return self._request(
            "POST",
            "/dss/v1/operational_intent_references/query",
            json={"area_of_interest": area},
        )

    def get_oir_details_from_peer_uss(
        self,
        oir_id: str,
        peer_uss_base_url: str,
    ) -> Dict[str, Any]:
        """
        Busca os detalhes completos de uma OIR diretamente em outro USS,
        conforme fluxo ASTM F3548-21 para resolução de conflitos.

        Fluxo:
            USS → AUTH: GET /token?aud=<domínio do USS-2>
            USS → USS-2: GET {peer_uss_base_url}/uss/v1/operational_intents/{oir_id}
        """
        if not oir_id:
            raise DSSValidationError("oir_id é obrigatório.")
        if not peer_uss_base_url:
            raise DSSValidationError("peer_uss_base_url é obrigatório.")

        peer_base = peer_uss_base_url.rstrip("/")

        # Extrai o domínio da URL do USS para usar como audience do JWT
        parsed = urllib.parse.urlparse(peer_base)
        peer_audience = parsed.netloc

        logger.info(
            "Obtendo token para Peer USS | audience=%s scope=utm.strategic_coordination",
            peer_audience,
        )

        # Autenticar com audience do peer e escopo estratégico
        peer_token = self.authenticator.get_token(
            intended_audience=peer_audience,
            scope="utm.strategic_coordination",
        )

        # Fazer GET no endpoint peer-to-peer do USS
        peer_url = f"{peer_base}/uss/v1/operational_intents/{oir_id}"
        logger.info("GET %s", peer_url)

        headers = {
            "Authorization": f"Bearer {peer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.get(peer_url, headers=headers, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise DSSConnectionError(
                f"Falha de conexão com o Peer USS {peer_base}: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise DSSConnectionError(
                f"Timeout ao acessar o Peer USS {peer_base}."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise DSSConnectionError(f"Erro de rede ao acessar Peer USS: {exc}") from exc

        if response.status_code == 401:
            raise DSSAuthenticationError(
                f"Token inválido para o Peer USS [401]: {response.text}"
            )
        if response.status_code == 403:
            raise DSSAuthorizationError(
                f"Acesso negado ao Peer USS [403]: {response.text}"
            )
        if response.status_code == 404:
            raise DSSNotFoundError(
                f"OIR {oir_id} não encontrada no Peer USS [404]: {response.text}"
            )
        if response.status_code >= 400:
            raise DSSConnectionError(
                f"Erro HTTP [{response.status_code}] ao acessar Peer USS: {response.text}"
            )

        logger.info(
            "Detalhes da OIR %s obtidos do Peer USS %s", oir_id, peer_base
        )
        return response.json() if response.text.strip() else {}

    # ─── Identification Service Areas (ASTM F3411) ────────────────

    def query_identification_service_areas(
        self,
        area: str,
        earliest_time: str,
        latest_time: str,
    ) -> Dict[str, Any]:
        """
        Busca ISAs no DSS por área e janela de tempo.
        GET /rid/v2/identification_service_areas
          ?area=lat1,lng1,lat2,lng2
          &earliest_time=<RFC3339>
          &latest_time=<RFC3339>
        Escopo: rid.display_provider
        """
        return self._request(
            "GET",
            "/rid/v2/dss/identification_service_areas",
            params={
                "area": area,
                "earliest_time": earliest_time,
                "latest_time": latest_time,
            },
        )

    def create_identification_service_area(
        self,
        isa_id: str,
        extents: Dict[str, Any],
        uss_base_url: str,
    ) -> Dict[str, Any]:
        """
        Registra um novo ISA no DSS.
        PUT /rid/v2/identification_service_areas/{id}
        Escopo: rid.service_provider
        """
        payload = {
            "extents": extents,
            "uss_base_url": uss_base_url,
        }
        return self._request(
            "PUT",
            f"/rid/v2/dss/identification_service_areas/{isa_id}",
            json=payload,
        )

    def delete_identification_service_area(
        self,
        isa_id: str,
        version: str,
    ) -> Dict[str, Any]:
        """
        Remove um ISA do DSS.
        DELETE /rid/v2/identification_service_areas/{id}/{version}
        Escopo: rid.service_provider
        """
        return self._request(
            "DELETE",
            f"/rid/v2/dss/identification_service_areas/{isa_id}/{version}",
        )

    def get_identification_service_area(
        self,
        isa_id: str,
    ) -> Dict[str, Any]:
        """
        Obtém detalhes de um ISA específico no DSS.
        GET /rid/v2/identification_service_areas/{id}
        Escopo: rid.display_provider
        """
        if not isa_id:
            raise DSSValidationError("isa_id é obrigatório.")
        return self._request(
            "GET",
            f"/rid/v2/dss/identification_service_areas/{isa_id}",
        )

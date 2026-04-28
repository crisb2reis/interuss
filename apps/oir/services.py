"""
OIRConstraintService — Orquestra o fluxo ASTM F3548-21:
"OIR próxima a Constraint"

Sequência implementada:
  1. USS → AUTH: GET /token?aud=core-service          (token para o DSS)
  2. USS → DSS:  POST /constraint_references/query     (constraints na área)
  3. USS → AUTH: GET /token?aud=<domínio do CP>        (token para cada CP)
  4. USS → CP:   GET /uss/v1/constraints/{id}          (detalhes da constraint)
  5. USS → DSS:  POST /operational_intent_references/query  (OIRs existentes)
  6. USS → DSS:  PUT  /operational_intent_references/{id}   (criar nova OIR)
  7. Salva OIR localmente no modelo OperationalIntent
"""

import logging
import urllib.parse
import uuid

from django.conf import settings

from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import DSSConnectionError, DSSNotFoundError, DSSConflictError

from .models import OperationalIntent

logger = logging.getLogger(__name__)


class OIRConstraintService:
    """
    Orquestra o fluxo completo de criação de OIR em proximidade a Constraints.

    Uso:
        service = OIRConstraintService()
        result = service.create_oir_near_constraint(area_of_interest, oir_payload)
    """

    # Audience e scope para comunicação com o DSS
    DSS_AUDIENCE = "core-service"
    DSS_SCOPE = "utm.strategic_coordination"

    def create_oir_near_constraint(
        self,
        area_of_interest: dict,
        oir_payload: dict,
    ) -> dict:
        """
        Executa o fluxo completo: consulta constraints, coleta detalhes do CP,
        verifica OIRs existentes e cria a nova OIR no DSS.

        Args:
            area_of_interest: Volume 4D (outline_polygon + altitudes + tempo)
                              usado tanto para consulta de constraints quanto de OIRs.
            oir_payload: Dicionário com os dados da OIR a ser criada:
                - extents (list[dict]): Lista de volumes 4D da OIR
                - state (str): "Accepted" | "Activated" | "Nonconforming" | "Contingent"
                - uss_base_url (str, opcional): URL base do USS (default: settings.USS_BASE_URL)

        Returns:
            Dicionário com:
                - constraints_found: lista de constraint references encontradas
                - constraint_details: lista de detalhes coletados dos CPs
                - existing_oirs_in_area: lista de OIRs já registradas na área
                - oir_created: dados da OIR criada (dss_id, dss_ovn, subscribers)
        """
        uss_base_url = oir_payload.get(
            "uss_base_url", getattr(settings, "USS_BASE_URL", "")
        )
        state = oir_payload.get("state", "Accepted")
        extents = oir_payload["extents"]

        # ── ETAPA 1 & 2: Obter token para Constraints e consultar no DSS ─────
        # O USS precisa primeiro saber quais restrições (Constraints) existem na área.
        logger.info("[OIR-Constraint] Etapa 2/6: Consultando constraints no DSS...")
        # Para consultar constraints, o escopo deve ser utm.constraint_processing
        dss_client_constraints = self._build_dss_client(scope="utm.constraint_processing")
        
        # O DSS retorna apenas referências (IDs e URLs), não os detalhes das constraints.
        constraint_result = dss_client_constraints.query_constraint_references(area_of_interest)
        constraint_refs = constraint_result.get("constraint_references", [])

        logger.info(
            "[OIR-Constraint] %d constraint(s) encontrada(s) na área.",
            len(constraint_refs),
        )

        # ── ETAPAS 3 & 4: Para cada constraint, buscar detalhes no CP ───────
        # Conforme ASTM F3548-21:
        #   Etapa 3: USS → AUTH: GET /token?aud=<domínio do CP>
        #   Etapa 4: USS → CP:   GET /uss/v1/constraints/{id}
        constraint_details = []
        for ref in constraint_refs:
            constraint_id = ref.get("id", "")
            cp_uss_base_url = ref.get("uss_base_url", "")

            if not constraint_id or not cp_uss_base_url:
                continue

            # Extrai o domínio do CP para uso como audience no token JWT
            cp_audience = urllib.parse.urlparse(cp_uss_base_url).netloc or cp_uss_base_url

            logger.info(
                "[OIR-Constraint] [Etapa 3] Solicitando token | audience=%s scope=utm.constraint_processing",
                cp_audience,
            )
            logger.info(
                "[OIR-Constraint] [Etapa 4] GET detalhes da constraint %s no CP %s",
                constraint_id,
                cp_uss_base_url,
            )

            try:
                # get_constraint_details_from_provider faz internamente:
                #   1. Extrai netloc do cp_uss_base_url → usa como audience
                #   2. Chama self.authenticator.get_token(audience=netloc, scope=utm.constraint_processing)
                #   3. Faz GET {cp_uss_base_url}/uss/v1/constraints/{id} com o token
                details = dss_client_constraints.get_constraint_details_from_provider(
                    constraint_id=constraint_id,
                    cp_uss_base_url=cp_uss_base_url,
                )
                constraint_details.append({
                    "id": constraint_id,
                    "uss_base_url": cp_uss_base_url,
                    "cp_audience": cp_audience,
                    "details": details,
                })
                logger.info(
                    "[OIR-Constraint] Detalhes da constraint %s obtidos com sucesso do CP.",
                    constraint_id,
                )
            except DSSNotFoundError:
                logger.warning(
                    "[OIR-Constraint] Constraint %s não encontrada no CP %s.",
                    constraint_id,
                    cp_uss_base_url,
                )
                constraint_details.append({
                    "id": constraint_id,
                    "uss_base_url": cp_uss_base_url,
                    "cp_audience": cp_audience,
                    "details": None,
                    "error": "não encontrada no CP",
                })
            except Exception as exc:
                # Se falhar em um CP, logamos e continuamos para não travar o fluxo todo.
                logger.error("[OIR-Constraint] Erro ao buscar constraint no CP: %s", exc)
                constraint_details.append({
                    "id": constraint_id,
                    "uss_base_url": cp_uss_base_url,
                    "cp_audience": cp_audience,
                    "details": None,
                    "error": str(exc),
                })

        # ── ETAPA 5: Consultar OIRs existentes na área ──────────────────────
        # Além de constraints, precisamos saber se há outros voos (OIRs) na mesma área.
        logger.info("[OIR-Constraint] Etapa 5/6: Consultando OIRs existentes na área...")
        # Para operações de OIR, o escopo deve ser utm.strategic_coordination
        dss_client_oir = self._build_dss_client(scope="utm.strategic_coordination")
        oir_query_result = dss_client_oir.query_operational_intent_references(area_of_interest)
        existing_oirs = oir_query_result.get("operational_intent_references", [])

        logger.info("[OIR-Constraint] %d OIR(s) encontrada(s).", len(existing_oirs))

        # ── COLETAR OVNs (Necessário para conformidade ASTM) ────────────────
        # O DSS exige que enviemos os OVNs (versões) de TODAS as entidades que 
        # sobrepõem nossa área. Isso prova que "vimos" os conflitos e os aceitamos.
        ovns = []
        for ref in constraint_refs:
            if ref.get("ovn"):
                ovns.append(ref["ovn"])
        for ref in existing_oirs:
            if ref.get("ovn"):
                ovns.append(ref["ovn"])
        
        if ovns:
            logger.info("[OIR-Constraint] Enviando %d OVNs no campo 'key' para reconhecimento.", len(ovns))

        # ── ETAPA 6: Criar nova OIR no DSS ─────────────────────────────────
        new_oir_id = str(uuid.uuid4())
        logger.info("[OIR-Constraint] Etapa 6/6: Criando OIR %s...", new_oir_id)

        try:
            # Tenta a criação inicial com as chaves (OVNs) que encontramos.
            dss_result = dss_client_oir.create_operational_intent_reference(
                oir_id=new_oir_id,
                extents=extents,
                uss_base_url=uss_base_url,
                state=state,
                key=ovns if ovns else None,
                new_subscription={
                    "uss_base_url": uss_base_url,
                    "notify_for_operational_intents": True,
                    "notify_for_constraints": True,
                },
            )
        except DSSConflictError as exc:
            # RETRY LOGIC (ASTM F3548-21):
            # Se o DSS retornar 409 (Conflict), significa que existem entidades 
            # que não incluímos no campo 'key'. O DSS gentilmente nos envia quais 
            # faltaram na resposta de erro.
            logger.warning("[OIR-Constraint] Conflito (409)! Coletando referências faltantes...")
            
            missing_refs = getattr(exc, "conflicting_references", [])
            for ref in missing_refs:
                m_ovn = ref.get("ovn")
                if m_ovn and m_ovn not in ovns:
                    ovns.append(m_ovn)

                # ── PASSOS 3 & 4 DO DIAGRAMA (executados aqui quando a query inicial falhou) ──
                # O DSS nos fornece id e uss_base_url das constraints ausentes.
                # Aproveitamos para buscar os detalhes no CP conforme exige o diagrama ASTM.
                m_id = ref.get("id", "")
                m_cp_url = ref.get("uss_base_url", "")
                already_fetched = any(d["id"] == m_id for d in constraint_details)

                if m_id and m_cp_url and not already_fetched:
                    logger.info("[OIR-Constraint] Buscando detalhes de constraint faltante %s", m_id)
                    try:
                        details = dss_client_constraints.get_constraint_details_from_provider(
                            constraint_id=m_id,
                            cp_uss_base_url=m_cp_url,
                        )
                        constraint_details.append({
                            "id": m_id,
                            "uss_base_url": m_cp_url,
                            "details": details,
                            "source": "409_conflict",
                        })
                        logger.info(
                            "[OIR-Constraint] Detalhes da constraint %s obtidos via 409.", m_id
                        )
                    except DSSNotFoundError:
                        logger.warning(
                            "[OIR-Constraint] Constraint %s não encontrada no CP %s.", m_id, m_cp_url
                        )
                        constraint_details.append({
                            "id": m_id,
                            "uss_base_url": m_cp_url,
                            "details": None,
                            "error": "não encontrada no CP",
                            "source": "409_conflict",
                        })
                    except Exception as cp_exc:
                        logger.error(
                            "[OIR-Constraint] Erro ao buscar constraint %s no CP: %s", m_id, cp_exc
                        )
                        constraint_details.append({
                            "id": m_id,
                            "uss_base_url": m_cp_url,
                            "details": None,
                            "error": str(cp_exc),
                            "source": "409_conflict",
                        })

                # Também adicionar à lista de constraint_refs para o resultado final
                if m_id and not any(r.get("id") == m_id for r in constraint_refs):
                    constraint_refs.append(ref)

            if not ovns:
                raise exc

            logger.info("[OIR-Constraint] Re-tentando criação com chaves atualizadas...")
            # Segunda tentativa com o conjunto completo de OVNs.
            dss_result = dss_client_oir.create_operational_intent_reference(
                oir_id=new_oir_id,
                extents=extents,
                uss_base_url=uss_base_url,
                state=state,
                key=ovns,
                new_subscription={
                    "uss_base_url": uss_base_url,
                    "notify_for_operational_intents": True,
                    "notify_for_constraints": True,
                },
            )
        
        ref = dss_result.get("operational_intent_reference", {})

        # ── ETAPA 7: Salvar OIR localmente ──────────────────────────────────
        oir = OperationalIntent.objects.create(
            id=new_oir_id,
            state=state,
            uss_base_url=uss_base_url,
            extents=extents,
            dss_id=ref.get("id", new_oir_id),
            dss_ovn=ref.get("ovn", ""),
            dss_response=dss_result,
        )
        logger.info(
            "[OIR-Constraint] OIR %s salva localmente com dss_id=%s ovn=%s.",
            oir.id,
            oir.dss_id,
            oir.dss_ovn,
        )

        return {
            "constraints_found": constraint_refs,
            "constraint_details": constraint_details,
            "existing_oirs_in_area": existing_oirs,
            "oir_created": {
                "local_id": str(oir.id),
                "dss_id": oir.dss_id,
                "dss_ovn": oir.dss_ovn,
                "state": oir.state,
                "uss_base_url": oir.uss_base_url,
                "subscribers": dss_result.get("subscribers", []),
                "conflicting_oirs": dss_result.get("conflicting_oirs", []),
            },
        }

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _build_dss_client(self, scope: str = None) -> DSSClient:
        """Instancia o DSSClient autenticado para o DSS."""
        return DSSClient(
            intended_audience=self.DSS_AUDIENCE,
            scope=scope or self.DSS_SCOPE,
            auto_authenticate=True,
        )

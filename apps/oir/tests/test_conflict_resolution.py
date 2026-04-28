from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.oir.conflict_resolution import OIRConflictResolutionService
from apps.dss_client.exceptions import DSSConflictError


class TestOIRConflictResolution(TestCase):

    def setUp(self):
        self.service = OIRConflictResolutionService()
        self.area_of_interest = {"mock": "area"}
        self.oir_payload = {"extents": [{"mock": "ext"}], "state": "Accepted", "uss_base_url": "http://test"}

    @patch("apps.oir.conflict_resolution.OIRConflictResolutionService._build_dss_client")
    def test_no_conflicts_creates_normally(self, mock_build_client):
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Sem constraints ou OIRs existentes
        mock_client.query_constraint_references.return_value = {}
        mock_client.query_operational_intent_references.return_value = {}
        mock_client.create_operational_intent_reference.return_value = {
            "operational_intent_reference": {"id": "123", "ovn": "abc"}
        }

        result = self.service.resolve_and_create(self.area_of_interest, self.oir_payload, our_priority=5)

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["oir_created"]["dss_ovn"], "abc")
        # Certifica-se que create_operational_intent_reference foi chamado com key None ou vazio
        mock_client.create_operational_intent_reference.assert_called_once()
        _, kwargs = mock_client.create_operational_intent_reference.call_args
        self.assertFalse(kwargs.get("key"))

    @patch("apps.oir.conflict_resolution.OIRConflictResolutionService._build_dss_client")
    def test_rejects_when_higher_priority_exists(self, mock_build_client):
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        mock_client.query_constraint_references.return_value = {}
        mock_client.query_operational_intent_references.return_value = {
            "operational_intent_references": [
                {"id": "oir-2", "uss_base_url": "http://uss2", "ovn": "ovn-2"}
            ]
        }
        
        # Simula resposta P2P com prioridade MAIOR que a nossa (nossa é 5, deles é 10)
        mock_client.get_oir_details_from_peer_uss.return_value = {
            "operational_intent": {"priority": 10}
        }

        result = self.service.resolve_and_create(self.area_of_interest, self.oir_payload, our_priority=5)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("prioridade maior ou igual", result["reason"])
        mock_client.create_operational_intent_reference.assert_not_called()

    @patch("apps.oir.conflict_resolution.OIRConflictResolutionService._build_dss_client")
    def test_proceeds_when_lower_priority_exists(self, mock_build_client):
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        mock_client.query_constraint_references.return_value = {}
        mock_client.query_operational_intent_references.return_value = {
            "operational_intent_references": [
                {"id": "oir-2", "uss_base_url": "http://uss2", "ovn": "ovn-2"}
            ]
        }
        
        # Simula resposta P2P com prioridade MENOR que a nossa (nossa é 5, deles é 2)
        mock_client.get_oir_details_from_peer_uss.return_value = {
            "operational_intent": {"priority": 2}
        }

        mock_client.create_operational_intent_reference.return_value = {
            "operational_intent_reference": {"id": "123", "ovn": "abc"}
        }

        result = self.service.resolve_and_create(self.area_of_interest, self.oir_payload, our_priority=5)

        self.assertEqual(result["status"], "created")
        mock_client.create_operational_intent_reference.assert_called_once()
        _, kwargs = mock_client.create_operational_intent_reference.call_args
        
        # Certifica-se que enviamos o OVN da OIR concorrente na chave 'key' para o DSS
        self.assertEqual(kwargs.get("key"), ["ovn-2"])

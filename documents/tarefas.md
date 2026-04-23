# Tarefas — Implementação do USS (UAS Service Supplier)

## Planejamento
- [x] Criar planoUSS.md com arquitetura completa e todas as 8 fases
- [/] Apresentar plano ao usuário para revisão

## Fase 1 — Modelagem do Domínio
- [ ] Inicializar projeto Django com PostGIS
- [ ] Criar model `FlightPlan` (UUID, estado, prioridade, tempo, volume geoespacial)
- [ ] Criar model `OperationalIntent` (OneToOne com FlightPlan, referência DSS, versionamento)
- [ ] Criar migrations e validar persistência

## Fase 2 — API ASTM F3548
- [ ] Implementar `PUT /flight_plans/{id}` (fluxo completo: validar → conflito local → DSS → decidir → publicar)
- [ ] Implementar `GET /flight_plans/{id}`
- [ ] Implementar `DELETE /flight_plans/{id}`
- [ ] Validar payload e formato de resposta (compatível InterUSS)

## Fase 3 — Motor de Conflito
- [ ] Implementar detecção de conflito espacial (`ST_Intersects`)
- [ ] Implementar detecção de conflito temporal (sobreposição de janelas)
- [ ] Integrar consulta DSS para OIRs remotos
- [ ] Lógica de decisão (accept/reject)

## Fase 4 — Cliente DSS
- [ ] Implementar `create_operational_intent_reference`
- [ ] Implementar `update_operational_intent_reference`
- [ ] Implementar `query_operational_intent_references`
- [ ] Implementar `delete_operational_intent_reference`
- [ ] Controle de versão com retry em conflito

## Fase 5 — Interface de Teste (InterUSS)
- [ ] Implementar `POST /inject_flight`
- [ ] Implementar `DELETE /clear_state`
- [ ] Implementar `GET /status`

## Fase 6 — Sincronização e Consistência
- [ ] Retry com backoff exponencial para falhas DSS
- [ ] Cache local de OIRs
- [ ] Sistema de auditoria de estado

## Fase 7 — Suíte de Testes InterUSS
- [ ] Configurar ambiente de testes com DSS sandbox
- [ ] Executar cenários: conflito entre USSs, prioridade, sincronização
- [ ] 100% dos testes passando

## Fase 8 — Produção
- [ ] Configurar HTTPS e autenticação OAuth2
- [ ] Alta disponibilidade (Docker / Kubernetes)
- [ ] Monitoramento e alertas

# InterUSS - UAS Service Supplier (USS)

Este projeto implementa um **UAS Service Supplier (USS)** em conformidade com as especificações **ASTM F3548-21** (Interoperabilidade de UTM) e **ED-269**. Ele fornece uma interface para gestão de intenções operacionais, planos de voo e integração com o ecossistema **BR-UTM**.

## 🚀 Como Subir a Aplicação

A aplicação foi configurada para rodar preferencialmente via Docker para garantir que todas as dependências espaciais (PostGIS/GDAL) funcionem corretamente.

### 1. Pré-requisitos
- Docker e Docker Compose instalados.
- Rede Docker `uss_default` criada. Caso não exista, crie com:
  ```bash
  docker network create uss_default
  ```

### 2. Configuração de Ambiente
Crie um arquivo `.env` na raiz do projeto. O arquivo `.env` deve conter as credenciais de acesso ao DSS e configurações do banco de dados. 


> [!NOTE]
> O arquivo `docker-compose.yml` deste projeto já possui sobrescritas automáticas para que, **dentro do container**, a aplicação consiga achar os serviços usando os nomes de host do Docker (`db` e `redis`). O `.env` acima é otimizado para quando você estiver rodando comandos diretamente no seu terminal (como `python manage.py migrate`).

### 3. Subindo com Docker
Para subir a aplicação e seus serviços de suporte:

```bash
# Sobe a aplicação em modo background e reconstrói se necessário
docker compose up -d --build
```

O comando acima irá:
1. Construir a imagem Docker (`Dockerfile`).
2. Executar as migrações do banco de dados automaticamente.
3. Iniciar o servidor de desenvolvimento na porta `8001`.

Verifique se está rodando acessando: [http://localhost:8001/](http://localhost:8001/)

---

## 🛠️ Desenvolvimento Local (Sem Docker)

Para rodar localmente sem Docker, é necessário ter o **PostgreSQL com PostGIS** e as bibliotecas **GDAL/GEOS** instaladas no sistema operacional.

1. **Criar Ambiente Virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Instalar Dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar Variáveis:**
   Exporte as variáveis do `.env` ou crie o arquivo na raiz.

4. **Rodar Migrações:**
   ```bash
   python3 manage.py migrate
   ```

5. **Iniciar Servidor:**
   > [!IMPORTANT]
   > Se o Docker estiver rodando, a porta `8001` estará ocupada. Pare o container com `docker compose stop web` ou use uma porta diferente (ex: `8002`).

   ```bash
   python3 manage.py runserver 0.0.0.0:8001
   ```

---

## 📁 Estrutura de Apps
- `apps.oir`: Gestão de Operational Intent References (OIR).
- `apps.flight_plans`: Gestão e validação de planos de voo seguindo ASTM F3548-21.
- `apps.dss_client`: Cliente para integração com o Discovery and Synchronization Service (DSS).
- `apps.validators`: Esquemas de validação Pydantic para payloads ASTM e ED-269.

---

## 📡 Endpoints Principais
- `GET /`: Health check e listagem de endpoints.
- `GET /api/oir/`: Lista intenções operacionais locais.
- `GET /api/oir/search_dss/`: Busca intenções operacionais no DSS.
- `PUT /api/flight_plans/`: Cria ou atualiza um plano de voo.

---

## 📝 Logs e Debug
Para visualizar os logs em tempo real:
```bash
docker compose logs -f web
```

Para acessar o shell do container:
```bash
docker exec -it uss-web-app bash
```

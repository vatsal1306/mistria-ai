ENV_FILE ?= .env
COMPOSE_PROJECT_NAME ?= mistria-ai
IMAGE_TAG ?= latest
BACKEND_PORT ?= 8080
FRONTEND_PORT ?= 8501

COMPOSE := ENV_FILE=$(ENV_FILE) COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) IMAGE_TAG=$(IMAGE_TAG) MISTRIA_BACKEND_PORT=$(BACKEND_PORT) MISTRIA_FRONTEND_PORT=$(FRONTEND_PORT) docker compose --env-file $(ENV_FILE)

.PHONY: build up down restart ps logs backend-logs frontend-logs health smoke clean

build:
	$(COMPOSE) build --pull

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

be-logs:
	$(COMPOSE) logs -f backend

fe-logs:
	$(COMPOSE) logs -f frontend

health:
	$(COMPOSE) exec -T backend python scripts/http_probe.py --url http://127.0.0.1:8080/health --expect-json status=ok --expect-json engine_ready=true
	$(COMPOSE) exec -T frontend python scripts/http_probe.py --url http://127.0.0.1:8501/ --expected-status 200

smoke:
	$(COMPOSE) exec -T backend python scripts/smoke_stack.py --frontend-url http://frontend:8501/ --backend-health-url http://127.0.0.1:8080/health --websocket-url ws://127.0.0.1:8080/ws/chat

clean:
	$(COMPOSE) down -v --remove-orphans

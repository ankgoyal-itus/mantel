# Mantel — dev | check | build | serve | demo | smoke | service | docker
API_DIR := services/api
KIOSK_DIR := apps/kiosk
VENV := $(API_DIR)/.venv
# Whichever interface carries the default route, so the printed URL is the one
# the iPads can actually reach (Wi-Fi, Ethernet or a dock).
LAN_IF := $(shell route -n get default 2>/dev/null | awk '/interface:/{print $$2}')
LAN_IP := $(shell ipconfig getifaddr $(LAN_IF) 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)

.PHONY: dev serve check check-port build smoke live idle photos install install-service uninstall-service \
        install-photos-service uninstall-photos-service up down switch-service render-service demo screenshots

## dev: API on :8000 and the kiosk on :5173, with /api proxied. Ctrl-C stops both.
dev: check-port install
	@echo "Kiosk: http://$(LAN_IP):5173/"
	@echo "Diag:  http://$(LAN_IP):5173/diag"
	@echo "API:   http://$(LAN_IP):8000/api/health  (reloads when mantel_api changes)"
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd $(API_DIR) && MANTEL_RELOAD=1 .venv/bin/python -m mantel_api ) & \
	  ( cd $(KIOSK_DIR) && npm run dev ) & \
	  wait

## check-port: refuse to start when something else already holds :8000.
check-port:
	@./deploy/port-check.sh 8000

## check: everything that must be green before a prompt is finished.
##
## The build comes first because the design suite measures services/api/static,
## not the source: without it `make check` happily passes against whatever was
## last bundled, and writes screenshots of code that no longer exists.
check: install build
	cd $(API_DIR) && .venv/bin/ruff check .
	$(VENV)/bin/ruff check tests/smoke tests/design scripts
	$(VENV)/bin/python tests/design/serve.py
	$(VENV)/bin/python tests/smoke/live.py
	$(VENV)/bin/python tests/smoke/idle.py
	$(VENV)/bin/python tests/smoke/usability.py
	cd $(API_DIR) && .venv/bin/mypy
	cd $(API_DIR) && .venv/bin/pytest -q
	cd $(KIOSK_DIR) && npx tsc --noEmit
	cd $(KIOSK_DIR) && npx eslint .
	cd $(KIOSK_DIR) && npx vitest run

## build: bundle the kiosk into services/api/static/ for the API to serve.
build: install
	cd $(KIOSK_DIR) && npm run build

## serve: one process on :8000 serving the built kiosk and the API. Ctrl-C stops it.
serve: check-port build
	@echo "Mantel: http://$(LAN_IP):8000/"
	cd $(API_DIR) && .venv/bin/python -m mantel_api

## demo: the sample family on a throwaway home at http://localhost:8140/
## (MANTEL_DEMO_PORT). Seeded history, local calendars, no network.
demo: build
	$(VENV)/bin/python scripts/demo.py

## design: the design language, checked at both iPad sizes. Screenshots in docs/screens/.
design: build $(VENV)/bin/playwright
	$(VENV)/bin/python tests/design/serve.py

## screenshots: the design suite, then the ten published pictures into
## screenshots/ (optimised, 1x, the sample family). See screenshots/CAPTIONS.md.
screenshots: build $(VENV)/bin/playwright
	$(VENV)/bin/python tests/design/serve.py
	$(VENV)/bin/python scripts/screenshots.py

## live: an approval on a phone reaches the wall, on the real API, under 2s.
live: build $(VENV)/bin/playwright
	$(VENV)/bin/python tests/smoke/live.py

## idle: the photo frame arrives on time with the live stream connected.
idle: build $(VENV)/bin/playwright
	$(VENV)/bin/python tests/smoke/idle.py

## smoke: drive the built app in a real browser at 1024x768. Screenshots in docs/screens/.
smoke: build $(VENV)/bin/playwright
	$(VENV)/bin/python tests/smoke/smoke.py

## photos: send the Photos album "Mantel" and anything in inbox/ to the frame.
photos:
	./deploy/photos-sync.sh

## install-service: run the API at login as the launchd agent com.mantel.api.
install-service: build
	./deploy/service.sh install
	@echo
	@echo "The rule, once this is installed:"
	@echo "  while you work   launchctl bootout gui/$$(id -u)/com.mantel.api"
	@echo "  then             make dev"
	@echo "  done for the day make build && launchctl bootstrap gui/$$(id -u) ~/Library/LaunchAgents/com.mantel.api.plist"

## install-photos-service: sync photos nightly at 21:00 (com.mantel.photos).
install-photos-service:
	./deploy/service.sh install-photos

## uninstall-photos-service: stop the nightly photo sync.
uninstall-photos-service:
	./deploy/service.sh uninstall-photos

## switch-service: from an older install to this one. Stops its agents, moves
## its family state into home/, starts com.mantel.* and prints the URL to
## check. The old install is described in .env (MANTEL_SWITCH_*; see service.sh).
switch-service: build
	./deploy/service.sh switch

## render-service: write the two com.mantel.* plists to .local/launchd/ for review.
render-service:
	./deploy/service.sh render

## uninstall-service: stop that agent and remove its plist. Logs are kept.
uninstall-service:
	./deploy/service.sh uninstall

## up: the same thing in Docker, on :8000. The image is rebuilt if it is stale.
up:
	docker compose up --build -d
	@echo "Mantel: http://$(LAN_IP):8000/"

## down: stop the Docker container.
down:
	docker compose down

install: $(VENV)/bin/python $(KIOSK_DIR)/node_modules

$(VENV)/bin/python:
	uv venv --python 3.11 $(VENV)
	uv pip install --python $(VENV)/bin/python -e "./$(API_DIR)[dev]"

$(VENV)/bin/playwright: $(VENV)/bin/python
	uv pip install --python $(VENV)/bin/python -e "./$(API_DIR)[smoke]"
	$(VENV)/bin/playwright install chromium

$(KIOSK_DIR)/node_modules: $(KIOSK_DIR)/package.json
	cd $(KIOSK_DIR) && npm install --no-fund --no-audit
	touch $(KIOSK_DIR)/node_modules

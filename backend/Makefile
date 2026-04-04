.PHONY: help db-init db-migrate rss-add rss-check test-tg test-dingtalk test-feishu test-push trigger-summary cleanup

PYTHON = python
MANAGE = src/omnidigest/manage.py

help:
	@echo "OmniDigest Makefile Commands:"
	@echo "--------------------------------------------------------"
	@echo "  make db-init         : Initialize the database schema"
	@echo "  make db-migrate      : Run all pending database migrations"
	@echo "  make rss-add URL=... : Add a new RSS feed"
	@echo "  make rss-check       : Check and list disabled RSS feeds"
	@echo "  make test-tg         : Send manual breaking news push to Telegram only"
	@echo "  make test-dingtalk   : Send manual breaking news push to DingTalk only"
	@echo "  make test-feishu     : Send manual breaking news push to Feishu only"
	@echo "  make test-push       : Send manual breaking news push to ALL platforms"
	@echo "  make trigger-summary : Trigger the daily summary LLM job"
	@echo "  make cleanup         : Run the low-quality article cleanup job"
	@echo "--------------------------------------------------------"

# --- Database ---
db-init:
	$(PYTHON) $(MANAGE) db init

db-migrate:
	@echo "Running all migrations sequentially..."
	$(PYTHON) $(MANAGE) db migrate-v2
	$(PYTHON) $(MANAGE) db migrate-v3-apikeys
	$(PYTHON) $(MANAGE) db migrate-v4-rss-failures

# --- RSS ---
rss-add:
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL is required. Usage: make rss-add URL=https://... [NAME=...]"; \
	else \
		if [ -z "$(NAME)" ]; then \
			$(PYTHON) $(MANAGE) rss add "$(URL)"; \
		else \
			$(PYTHON) $(MANAGE) rss add "$(URL)" --name "$(NAME)"; \
		fi \
	fi

rss-check:
	$(PYTHON) $(MANAGE) rss check-failures

# --- Jobs & Testing ---
test-tg:
	$(PYTHON) $(MANAGE) jobs test-breaking-push --platform tg

test-dingtalk:
	$(PYTHON) $(MANAGE) jobs test-breaking-push --platform dingtalk

test-feishu:
	$(PYTHON) $(MANAGE) jobs test-breaking-push --platform feishu

test-push:
	$(PYTHON) $(MANAGE) jobs test-breaking-push

trigger-summary:
	$(PYTHON) $(MANAGE) jobs trigger-summary

cleanup:
	$(PYTHON) $(MANAGE) jobs cleanup

lint:
	$(PYTHON) $(MANAGE) lint comments

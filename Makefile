# Local automation — from repo root: `make help`, `make full`, etc.
# Apify: set APIFY_TOKEN once in `.env` (gitignored). CLI loads it on every run.

PY        ?= .venv/bin/python
# Local SQLite (override Docker DATABASE_URL in .env for these targets)
SQLITE    ?= sqlite:///jobs.db
SLEEP     ?= 0.4
# Default scrape: all sources including linkedin_posts (workbook LinkedIn URLs).
# For combined runs, leave unset: LINKEDIN_POSTS_STANDALONE, LINKEDIN_POSTS_TARGET_URLS,
# LINKEDIN_POSTS_TARGET_URLS_FILE — otherwise use `make posts` for posts-only.
SOURCES   ?= ats career playwright linkedin linkedin_posts

.PHONY: help venv install playwright init scrape posts full clean \
	scrape-sequential scrape-step-ats scrape-step-career scrape-step-playwright \
	scrape-step-linkedin scrape-step-linkedin-posts

help:
	@echo "Targets:"
	@echo "  make venv        Create .venv"
	@echo "  make install     venv + pip install -r requirements.txt"
	@echo "  make playwright  Install Chromium (for playwright / LinkedIn page harvest)"
	@echo "  make init        Load companies: DATABASE_URL=$(SQLITE) job_scraper init-db"
	@echo "  make scrape      Run pipeline (default: all sources incl. linkedin_posts)"
	@echo "  make scrape SOURCES='ats career'   Override which sources to run"
	@echo "  make posts       linkedin_posts only (standalone URL list in .env)"
	@echo "  make full        install + init + scrape (default includes linkedin_posts)"
	@echo "  make scrape-sequential   Run each --source separately (for n8n: one node per step)"
	@echo "  make scrape-step-ats (and …-career, …-playwright, …-linkedin, …-linkedin-posts)"
	@echo ""
	@echo "Apify token: add once to repo-root .env → APIFY_TOKEN=apify_api_..."
	@echo "Do not pass the token on the command line; python-dotenv loads .env automatically."

venv:
	test -d .venv || python3 -m venv .venv

install: venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt

playwright:
	$(PY) -m playwright install chromium

init:
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper init-db

scrape:
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source $(SOURCES) --sleep $(SLEEP)

posts:
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source linkedin_posts --sleep $(SLEEP)

# One command per source — use from n8n “Execute Command” so the canvas shows which step is running.
scrape-sequential: scrape-step-ats scrape-step-career scrape-step-playwright scrape-step-linkedin scrape-step-linkedin-posts

scrape-step-ats:
	@echo ">>> scraper step: ats"
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source ats --sleep $(SLEEP)

scrape-step-career:
	@echo ">>> scraper step: career"
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source career --sleep $(SLEEP)

scrape-step-playwright:
	@echo ">>> scraper step: playwright"
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source playwright --sleep $(SLEEP)

scrape-step-linkedin:
	@echo ">>> scraper step: linkedin"
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source linkedin --sleep $(SLEEP)

scrape-step-linkedin-posts:
	@echo ">>> scraper step: linkedin_posts"
	DATABASE_URL=$(SQLITE) $(PY) -m job_scraper -v scrape --source linkedin_posts --sleep $(SLEEP)

# One-time / refresh setup then full pipeline (posts use workbook URLs unless standalone env is set)
full: install init scrape
	@echo "Done."

clean:
	rm -rf .venv

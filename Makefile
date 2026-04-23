# ShopMate-R — development & ops shortcuts
#
# Usage:
#   make help        list targets
#   make install     pip install -r requirements.txt
#   make run         launch the full app (main.py)
#   make dashboard   run just the Flask dashboard
#   make demo        run the scripted demo (no mic/keyboard required)
#   make preview     render tablet screens to ./preview/*.html
#   make gesture     open the interactive gesture tester
#   make health      run the pre-flight diagnostic
#   make inventory   show the inventory table
#   make test        run the pytest suite
#   make lint        python -m py_compile on every module
#   make clean       remove caches and temp files
#   make zip         bundle the project into ShopMate-R.zip

PYTHON ?= python3
PIP    ?= pip

.PHONY: help install run dashboard demo preview gesture health inventory \
        test lint clean zip

help:
	@echo "ShopMate-R — available targets:"
	@echo ""
	@echo "  make install    Install Python dependencies"
	@echo "  make run        Launch the full multi-robot app (main.py)"
	@echo "  make dashboard  Launch just the Flask dashboard"
	@echo "  make demo       Run the scripted customer-flow demo"
	@echo "  make preview    Render all tablet screens to ./preview/"
	@echo "  make gesture    Interactive Pepper gesture tester"
	@echo "  make health     Pre-flight diagnostic (Pepper/Temi/dashboard)"
	@echo "  make inventory  Show the inventory as a table"
	@echo "  make test       Run pytest"
	@echo "  make lint       Byte-compile every Python file"
	@echo "  make clean      Remove __pycache__, preview/, tmp audio"
	@echo "  make zip        Bundle the project into ShopMate-R.zip"

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) main.py

dashboard:
	$(PYTHON) mock_dashboard.py

demo:
	$(PYTHON) demo.py

preview:
	$(PYTHON) tablet_preview.py

gesture:
	$(PYTHON) gesture_tester.py

health:
	$(PYTHON) health_check.py

inventory:
	$(PYTHON) db_inspector.py

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	@for f in $$(ls *.py tests/*.py); do \
	  $(PYTHON) -m py_compile $$f && echo "  ✅ $$f"; \
	done

clean:
	rm -rf __pycache__ tests/__pycache__ preview/ *.pyc tmp_*.wav

zip:
	@rm -f ShopMate-R.zip
	@cd .. && zip -r ShopMate-R/ShopMate-R.zip ShopMate-R/ \
	  -x '*/__pycache__/*' '*.pyc' '*/preview/*' '*/tmp_*.wav' \
	  '*/ShopMate-R.zip' > /dev/null
	@ls -la ShopMate-R.zip

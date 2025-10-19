.PHONY: backend frontend install

VENV = .venv
PYTHON = $(VENV)/Scripts/python
PIP = $(VENV)/Scripts/pip
UVICORN = $(VENV)/Scripts/uvicorn

install:
	python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	cd client && npm install

# Run FastAPI backend 
backend:
	$(UVICORN) api:app --host 0.0.0.0 --port 8000

# Run React frontend 
frontend:
	cd client && npm run dev

# pdf-autofillr — Makefile

.PHONY: help install-all test clean

help:
	@echo ""
	@echo "pdf-autofillr"
	@echo "============="
	@echo "install-mapper    install-chatbot    install-doc-upload    install-rag"
	@echo "test-mapper       test-chatbot       test-doc-upload       test-rag"
	@echo "dev-mapper        dev-chatbot        dev-doc-upload        dev-rag"
	@echo "docker-mapper     docker-chatbot     docker-doc-upload     docker-rag"
	@echo "install-all       test               clean"
	@echo ""

install-mapper:
	cd packages/mapper    && pip install -e ".[dev,api]"

install-chatbot:
	cd packages/chatbot   && pip install -e ".[dev,server]"

install-doc-upload:
	cd packages/doc_upload && pip install -e ".[dev,server]"

install-rag:
	cd packages/rag       && pip install -e ".[dev,server]"

install-plugins:
	cd plugins/core         && pip install -e ".[dev]"
	cd plugins/pdf_autofillr && pip install -e ".[dev]"

install-all: install-mapper install-chatbot install-doc-upload install-rag
	cd packages/pdf_autofillr && pip install -e .

dev-mapper:
	cd packages/mapper    && pdf-mapper-server

dev-chatbot:
	cd packages/chatbot   && chatbot-server

dev-doc-upload:
	cd packages/doc_upload && doc-upload-server

dev-rag:
	cd packages/rag       && ragpdf-server

test-mapper:
	cd packages/mapper    && pytest tests/ --tb=short -q

test-chatbot:
	cd packages/chatbot   && pytest tests/ --tb=short -q

test-doc-upload:
	cd packages/doc_upload && python run_all_tests.py

test-rag:
	cd packages/rag       && python run_all_tests.py

test: test-mapper test-chatbot test-doc-upload test-rag

docker-mapper:
	docker build -f deployment/docker/mapper/Dockerfile    -t pdf-autofillr-mapper:latest .

docker-chatbot:
	docker build -f deployment/docker/chatbot/Dockerfile   -t pdf-autofillr-chatbot:latest .

docker-doc-upload:
	docker build -f deployment/docker/doc_upload/Dockerfile -t pdf-autofillr-doc-upload:latest .

docker-rag:
	docker build -f deployment/docker/rag/Dockerfile       -t pdf-autofillr-rag:latest .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -not -path "*/java_utils/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

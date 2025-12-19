# Makefile for thesis smart contract security project

.PHONY: help setup activate clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup     - Create virtual environment and install dependencies"
	@echo "  make activate  - Show how to activate virtual environment"
	@echo "  make clean     - Remove virtual environment"

# Setup virtual environment
setup-venv:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo "Setup complete! Run 'make activate' to see how to activate"

# Show activation command
activate:
	@echo "To activate the virtual environment, run:"
	@echo "  source venv/bin/activate"

# Clean up
clean:
	rm -rf venv
	@echo "Virtual environment removed"
	@echo "Remember to deactivate the virtual environment using:"
	@echo "  deactivate"
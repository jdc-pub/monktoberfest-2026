.PHONY: build serve release typecheck clean

build:
	asciidoctor-revealjs presentation.adoc -o dist/presentation.html

serve:
	@echo "http://localhost:8080/dist/presentation.html"
	python3 tools/serve.py

typecheck:
	mypy --strict tools

release:
	asciidoctor-revealjs -a data-uri presentation.adoc -o dist/presentation.html
	python3 tools/inline.py

clean:
	rm -rf dist

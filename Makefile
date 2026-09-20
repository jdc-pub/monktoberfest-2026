.PHONY: build serve release typecheck lint clean

build:
	asciidoctor-revealjs presentation.adoc -o dist/presentation.html

serve:
	@echo "http://localhost:8080/dist/presentation.html"
	python3 tools/serve.py

typecheck:
	mypy --strict tools

lint:
	acdc lint -A all -D one-sentence-per-line essay.adoc presentation.adoc

release:
	asciidoctor-revealjs -a data-uri presentation.adoc -o dist/presentation.html
	python3 tools/inline.py

clean:
	rm -rf dist

.PHONY: build serve typecheck lint clean fallback

build:
	asciidoctor-revealjs -I tools -r og-macro.rb -r bsky-macro.rb -a data-uri -a imagesdir=img presentation.adoc -o dist/presentation.html
	python3 tools/inline.py

serve:
	@echo "http://localhost:8080/dist/presentation.html"
	python3 tools/serve.py

typecheck:
	mypy --strict tools

lint:
	acdc lint -A all -D one-sentence-per-line essay.adoc presentation.adoc



fallback:
	python3 tools/make-bsky-fallback.py

clean:
	rm -rf dist

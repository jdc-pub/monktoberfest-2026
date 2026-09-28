.PHONY: build serve release typecheck lint clean fallback

build:
	asciidoctor-revealjs -I tools -r og-macro.rb -r bsky-macro.rb presentation.adoc -o dist/presentation.html

serve:
	@echo "http://localhost:8080/dist/presentation.html"
	python3 tools/serve.py

typecheck:
	mypy --strict tools

og-data:
	python3 tools/make-og-data.py $(URLS)

lint:
	acdc lint -A all -D one-sentence-per-line essay.adoc presentation.adoc

release:
	asciidoctor-revealjs -I tools -r og-macro.rb -r bsky-macro.rb -a data-uri -a imagesdir=img presentation.adoc -o dist/presentation.html
	python3 tools/inline.py

fallback:
	python3 tools/make-bsky-fallback.py

clean:
	rm -rf dist

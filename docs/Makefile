SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"

clean:
	rm -rf "$(BUILDDIR)" "$(SOURCEDIR)/_autosummary"

livehtml:
	sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)/html" \
		--watch ../grid \
		--open-browser
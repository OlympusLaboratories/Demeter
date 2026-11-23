ifeq ($(strip $(TOOL)),)
$(error TOOL is unset: set it in the tool's own Makefile before including extension.mk)
endif

CODE ?= $(shell command -v code 2>/dev/null \
	|| command -v codium 2>/dev/null \
	|| ([ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ] \
	    && echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code") \
	|| echo code)
EXT_DIR ?= $(HOME)/.vscode/extensions/$(TOOL)
HERE := $(patsubst %/,%,$(dir $(abspath $(firstword $(MAKEFILE_LIST)))))
DEPS := node_modules/.package-lock.json
REPO_URL ?= https://github.com/OlympusLaboratories/Demeter
RAW_URL ?= https://raw.githubusercontent.com/OlympusLaboratories/Demeter
VSIX := $(TOOL).vsix
MAX_VSIX_KB ?= 120

.PHONY: setup build watch test typecheck check link unlink lean package install clean

$(DEPS): package.json package-lock.json
	npm install
	@touch $(DEPS)

setup: $(DEPS)

build: $(DEPS)
	npm run build

watch: $(DEPS)
	npm run watch

test: $(DEPS)
	npm run test

typecheck: $(DEPS)
	npm run typecheck

check: typecheck test build

link: build
	rm -rf "$(EXT_DIR)"
	ln -s "$(HERE)" "$(EXT_DIR)"
	@echo "Linked $(EXT_DIR) -> $(HERE). Reload VS Code (Developer: Reload Window)."

unlink:
	rm -rf "$(EXT_DIR)"
	@echo "Removed $(EXT_DIR). Reload VS Code."

lean:
	@[ -f .vscodeignore ] || { \
		echo "$(TOOL): no .vscodeignore, refusing to package."; \
		echo "  Without one, vsce ships src/, every *.test.ts, the source maps and any"; \
		echo "  production dependency esbuild already bundled into dist/extension.js."; \
		echo "  Copy tools/claude-usage/.vscodeignore and add anything $(TOOL) alone carries."; \
		exit 1; }

package: lean check
	npx --yes @vscode/vsce package --allow-missing-repository --skip-license \
		--baseContentUrl $(REPO_URL)/blob/main/tools/$(TOOL) \
		--baseImagesUrl $(RAW_URL)/main/tools/$(TOOL) \
		-o $(VSIX)
	@kb=$$(( $$(wc -c < "$(VSIX)") / 1024 )); \
	if [ "$$kb" -gt "$(MAX_VSIX_KB)" ]; then \
		echo "$(TOOL): $(VSIX) is $${kb}KB, over the $(MAX_VSIX_KB)KB ceiling."; \
		echo "  Something unwanted is in the package. List what went in with:"; \
		echo "    cd tools/$(TOOL) && npx --yes @vscode/vsce ls"; \
		echo "  Add it to .vscodeignore, or raise MAX_VSIX_KB in this tool's Makefile"; \
		echo "  if the growth is genuinely wanted."; \
		exit 1; \
	fi; \
	echo "$(TOOL): $(VSIX) is $${kb}KB, within the $(MAX_VSIX_KB)KB ceiling."

install: package
	@command -v "$(CODE)" >/dev/null 2>&1 || [ -x "$(CODE)" ] || { \
		echo "VS Code CLI not found. Install it, or pass CODE=/path/to/code"; exit 1; }
	"$(CODE)" --install-extension $(VSIX) --force
	@echo "Installed. Reload VS Code (Developer: Reload Window)."

clean:
	rm -rf dist node_modules $(VSIX)

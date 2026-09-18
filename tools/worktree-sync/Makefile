CODE ?= $(shell command -v code 2>/dev/null \
	|| command -v codium 2>/dev/null \
	|| ([ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ] \
	    && echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code") \
	|| echo code)
EXT_DIR := $(HOME)/.vscode/extensions/worktree-sync
HERE := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
DEPS := node_modules/.package-lock.json

.PHONY: setup build watch test typecheck check link unlink package install clean

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

package: check
	npx --yes @vscode/vsce package --allow-missing-repository --skip-license -o worktree-sync.vsix

install: package
	@command -v "$(CODE)" >/dev/null 2>&1 || [ -x "$(CODE)" ] || { \
		echo "VS Code CLI not found. Install it, or pass CODE=/path/to/code"; exit 1; }
	"$(CODE)" --install-extension worktree-sync.vsix --force
	@echo "Installed. Reload VS Code (Developer: Reload Window)."

clean:
	rm -rf dist node_modules worktree-sync.vsix

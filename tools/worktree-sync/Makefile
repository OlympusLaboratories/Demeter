CODE ?= $(shell command -v code 2>/dev/null || echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
EXT_DIR := $(HOME)/.vscode/extensions/worktree-sync
HERE := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

.PHONY: setup build watch test typecheck check link unlink package install clean

setup:
	npm install

build:
	npm run build

watch:
	npm run watch

test:
	npm run test

typecheck:
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
	"$(CODE)" --install-extension worktree-sync.vsix --force
	@echo "Installed. Reload VS Code (Developer: Reload Window)."

clean:
	rm -rf dist node_modules worktree-sync.vsix

.PHONY: help test standup lint format check link unlink links

RUFF := uvx ruff@0.16.1

SKILLS_DIR := $(HOME)/.claude/skills
SKILLS := $(patsubst %/SKILL.md,%,$(wildcard */SKILL.md))

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"
	@echo "lint     - ruff check + format check, no writes"
	@echo "format   - apply safe lint fixes, then reformat"
	@echo "check    - lint + test, the full gate"
	@echo "link     - symlink this repo's skills into ~/.claude/skills"
	@echo "unlink   - remove this repo's symlinks from ~/.claude/skills"
	@echo "links    - show the current link state of each skill"

test:
	uv run --with pytest pytest standup-digest/scripts laurels/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py

lint:
	$(RUFF) check .
	$(RUFF) format --check .

# check --fix runs before format: autofixes delete imports and rewrite
# annotations, which can leave a file needing reformatting.
#
# --exit-zero because `check --fix` exits non-zero whenever any finding remains
# unfixed, which would abort the recipe before `format` ever runs. This target
# fixes what it can; `make lint` is the gate that reports what's left.
format:
	$(RUFF) check --fix --exit-zero .
	$(RUFF) format .

check: lint test

# These skills are developed in place and symlinked into ~/.claude/skills rather
# than consumed as a plugin. A plugin install snapshots the repo at a commit, so
# edits here wouldn't take effect until committed and the plugin updated —
# useless while actively working on a skill. Symlinks are live.
#
# `link` refuses to replace a real directory: that would mean deleting a skill
# that came from somewhere else, which is not this target's call to make.
#
# It first prunes links that point into this repo at a path that no longer
# exists. Renaming a skill orphans its old link, and `unlink` can't help because
# the old name is gone from SKILLS by then.
link:
	@mkdir -p "$(SKILLS_DIR)"
	@for dest in "$(SKILLS_DIR)"/*; do \
	  [ -L "$$dest" ] || continue; \
	  target="`readlink "$$dest"`"; \
	  case "$$target" in "$(CURDIR)/"*) ;; *) continue ;; esac; \
	  [ -e "$$target" ] || { rm "$$dest" && echo "  prune `basename "$$dest"` (was -> $$target)"; }; \
	done
	@for s in $(SKILLS); do \
	  dest="$(SKILLS_DIR)/$$s"; \
	  if [ -e "$$dest" ] && [ ! -L "$$dest" ]; then \
	    echo "  skip  $$s (real directory at $$dest - remove it first)"; \
	  elif [ -L "$$dest" ] && [ "`readlink "$$dest"`" = "$(CURDIR)/$$s" ]; then \
	    echo "  ok    $$s"; \
	  else \
	    ln -sfn "$(CURDIR)/$$s" "$$dest" && echo "  link  $$s"; \
	  fi; \
	done

# Only removes links that point back at this repo, so a same-named skill from
# another source is left alone.
unlink:
	@for s in $(SKILLS); do \
	  dest="$(SKILLS_DIR)/$$s"; \
	  if [ -L "$$dest" ] && [ "`readlink "$$dest"`" = "$(CURDIR)/$$s" ]; then \
	    rm "$$dest" && echo "  unlink  $$s"; \
	  fi; \
	done

links:
	@for s in $(SKILLS); do \
	  dest="$(SKILLS_DIR)/$$s"; \
	  if [ ! -e "$$dest" ] && [ ! -L "$$dest" ]; then printf '  %-26s missing\n' "$$s"; \
	  elif [ ! -L "$$dest" ]; then printf '  %-26s REAL DIRECTORY\n' "$$s"; \
	  elif [ "`readlink "$$dest"`" = "$(CURDIR)/$$s" ]; then printf '  %-26s linked\n' "$$s"; \
	  else printf '  %-26s links elsewhere -> %s\n' "$$s" "`readlink "$$dest"`"; \
	  fi; \
	done

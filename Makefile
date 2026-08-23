.PHONY: help test standup lint format check link unlink links

RUFF := uvx ruff@0.16.1

SKILLS_DIR := $(HOME)/.claude/skills
SKILLS := $(patsubst %/SKILL.md,%,$(wildcard */SKILL.md))

STYLES_DIR := $(HOME)/.claude/output-styles
STYLES := $(notdir $(wildcard output-styles/*.md))

# One list covering both link kinds, so link/unlink/links each keep a single
# copy of the safety logic. Each entry is <kind>:<name>. Skill names are
# directories, style names are .md files; neither contains a colon or a space.
LINKS := $(foreach s,$(SKILLS),skill:$(s)) $(foreach f,$(STYLES),style:$(f))

# Expands one $$pair entry into $$name, $$dest, $$src, and the nouns used in
# messages. Defined once here rather than repeated in all three recipes.
#
# The \# is required: an unescaped # opens a comment in a variable assignment,
# which silently truncates the value mid-expansion.
resolve = kind="$${pair%%:*}"; name="$${pair\#*:}"; \
	  if [ "$$kind" = skill ]; then \
	    dest="$(SKILLS_DIR)/$$name"; src="$(CURDIR)/$$name"; \
	    noun="directory"; real="REAL DIRECTORY"; \
	  else \
	    dest="$(STYLES_DIR)/$$name"; src="$(CURDIR)/output-styles/$$name"; \
	    noun="file"; real="REAL FILE"; \
	  fi

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"
	@echo "lint     - ruff check + format check, no writes"
	@echo "format   - apply safe lint fixes, then reformat"
	@echo "check    - lint + test, the full gate"
	@echo "link     - symlink this repo's skills and output styles into ~/.claude"
	@echo "unlink   - remove this repo's symlinks from ~/.claude"
	@echo "links    - show the current link state of each skill and style"

test:
	uv run --with pytest pytest standup-digest/scripts laurels/scripts someday-triage/scripts -q

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

# These skills and output styles are developed in place and symlinked into
# ~/.claude rather than consumed as a plugin. A plugin install snapshots the
# repo at a commit, so edits here wouldn't take effect until committed and the
# plugin updated - useless while actively working on one. Symlinks are live.
#
# Skills land in ~/.claude/skills, output styles in ~/.claude/output-styles.
# Both are load paths Claude Code scans at startup.
#
# `link` refuses to replace a real directory or file: that would mean deleting
# something that came from somewhere else, which is not this target's call.
#
# It first prunes links that point into this repo at a path that no longer
# exists. Renaming a skill orphans its old link, and `unlink` can't help because
# the old name is gone from LINKS by then.
link:
	@mkdir -p "$(SKILLS_DIR)" "$(STYLES_DIR)"
	@for d in "$(SKILLS_DIR)" "$(STYLES_DIR)"; do \
	  for dest in "$$d"/*; do \
	    [ -L "$$dest" ] || continue; \
	    target="`readlink "$$dest"`"; \
	    case "$$target" in "$(CURDIR)/"*) ;; *) continue ;; esac; \
	    [ -e "$$target" ] || { rm "$$dest" && echo "  prune `basename "$$dest"` (was -> $$target)"; }; \
	  done; \
	done
	@for pair in $(LINKS); do \
	  $(resolve); \
	  if [ -e "$$dest" ] && [ ! -L "$$dest" ]; then \
	    echo "  skip  $$name (real $$noun at $$dest - remove it first)"; \
	  elif [ -L "$$dest" ] && [ "`readlink "$$dest"`" = "$$src" ]; then \
	    echo "  ok    $$name to $$dest"; \
	  else \
	    ln -sfn "$$src" "$$dest" && echo "  link  $$name to $$dest"; \
	  fi; \
	done

# Only removes links that point back at this repo, so a same-named skill or
# style from another source is left alone.
unlink:
	@for pair in $(LINKS); do \
	  $(resolve); \
	  if [ -L "$$dest" ] && [ "`readlink "$$dest"`" = "$$src" ]; then \
	    rm "$$dest" && echo "  unlink  $$name"; \
	  fi; \
	done

links:
	@for pair in $(LINKS); do \
	  $(resolve); \
	  if [ ! -e "$$dest" ] && [ ! -L "$$dest" ]; then printf '  %-26s missing\n' "$$name"; \
	  elif [ ! -L "$$dest" ]; then printf '  %-26s %s\n' "$$name" "$$real"; \
	  elif [ "`readlink "$$dest"`" = "$$src" ]; then printf '  %-26s linked\n' "$$name"; \
	  else printf '  %-26s links elsewhere -> %s\n' "$$name" "`readlink "$$dest"`"; \
	  fi; \
	done

#!/usr/bin/env python3
import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude", "environment.json")

DEFAULTS = {
    "forge": "github",
    "api_script": "~/.claude/scripts/github-api.sh",
    "change_request": "pull request",
    "change_request_short": "PR",
    "change_request_url_re": r"/pull/(\d+)",
    "review_bots": [],
    "review_job": "",
    "operational_bots": [],
    "iac_bot": "",
    "iac_plan_marker": "",
    "iac_apply_marker": "",
    "artifact_store": "auto",
    "default_remote": "origin",
    "require_human_approval": False,
    "fix_autopilot": True,
    "fix_branch": "new",
    "fix_quick_description": True,
    "fix_diagram": False,
    "fix_review": False,
    "fix_merge": True,
    "fix_max_rounds": 3,
}

LIST_KEYS = ("review_bots", "operational_bots")


def load():
    merged = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as handle:
            raw = json.load(handle)
    except OSError:
        return merged, None
    except ValueError as error:
        return merged, "%s is not valid JSON: %s" % (CONFIG_PATH, error)
    if not isinstance(raw, dict):
        return merged, "%s is not a JSON object" % CONFIG_PATH
    for key, value in raw.items():
        if key not in DEFAULTS:
            continue
        if isinstance(value, str) and ("REPLACE_ME" in value or not value.strip()):
            continue
        if value is None:
            continue
        merged[key] = value
    return merged, None


def render(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "json"
    config, problem = load()
    if problem:
        print(problem, file=sys.stderr)
    if action == "json":
        print(json.dumps(config, indent=2))
        return 0
    if action == "get":
        if len(sys.argv) < 3:
            print("usage: skill-env.sh get <key>", file=sys.stderr)
            return 2
        key = sys.argv[2]
        if key not in config:
            print("unknown key %s; known keys: %s"
                  % (key, ", ".join(sorted(DEFAULTS))), file=sys.stderr)
            return 2
        value = config[key]
        if key in LIST_KEYS and not isinstance(value, list):
            value = [value]
        print(render(value))
        return 0
    if action == "check":
        source = CONFIG_PATH if os.path.exists(CONFIG_PATH) else "built-in defaults only"
        print("config: %s" % source)
        for key in sorted(config):
            print("  %-22s %s" % (key, render(config[key]).replace("\n", ", ")))
        api = os.path.expanduser(config["api_script"])
        print("api script: %s" % ("found" if os.access(api, os.X_OK) else "MISSING at " + api))
        return 0
    print("usage: skill-env.sh [json | get <key> | check]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

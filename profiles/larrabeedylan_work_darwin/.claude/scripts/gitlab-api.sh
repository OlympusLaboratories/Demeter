#!/usr/bin/env bash
# GitLab API helper for eng-snippet command.
# Reads token from .mcp.json so it never passes through Claude's context.
set -euo pipefail

TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.claude/.mcp.json'))['mcpServers']['gitlab']['env']['GITLAB_PERSONAL_ACCESS_TOKEN'])")
GITLAB_URL="https://gitlab.com/api/v4"

case "${1:-}" in
  current-user)
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/user" | python3 -c "
import sys, json
u = json.load(sys.stdin)
print(json.dumps({'username': u['username'], 'id': u['id'], 'name': u['name']}))
"
    ;;
  merged-mrs)
    # Args: username, updated_after
    USERNAME="${2:?Usage: gitlab-api.sh merged-mrs <username> <updated_after>}"
    UPDATED_AFTER="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/merge_requests?author_username=$USERNAME&state=merged&updated_after=$UPDATED_AFTER&scope=all&per_page=50" | python3 -c "
import sys, json
mrs = json.load(sys.stdin)
for mr in mrs:
    proj = mr.get('references', {}).get('full', mr.get('web_url', '')).split('!')[0].rstrip('/-')
    print(json.dumps({
        'title': mr['title'],
        'project': proj,
        'web_url': mr['web_url'],
        'merged_at': mr.get('merged_at', ''),
        'description': (mr.get('description') or '')[:200]
    }))
"
    ;;
  open-mrs)
    # Args: username
    USERNAME="${2:?Usage: gitlab-api.sh open-mrs <username>}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/merge_requests?author_username=$USERNAME&state=opened&scope=all&per_page=50" | python3 -c "
import sys, json
mrs = json.load(sys.stdin)
for mr in mrs:
    proj = mr.get('references', {}).get('full', mr.get('web_url', '')).split('!')[0].rstrip('/-')
    print(json.dumps({
        'title': mr['title'],
        'project': proj,
        'web_url': mr['web_url'],
        'draft': mr.get('work_in_progress', False) or mr.get('draft', False),
        'has_conflicts': mr.get('has_conflicts', False),
        'description': (mr.get('description') or '')[:200]
    }))
"
    ;;
  mr-info)
    # Args: project_path (URL-encoded), mr_iid
    PROJECT="${2:?Usage: gitlab-api.sh mr-info <project_path_urlencoded> <mr_iid>}"
    MR_IID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID" | python3 -c "
import sys, json
mr = json.load(sys.stdin)
print(json.dumps({
    'title': mr['title'],
    'description': mr.get('description', ''),
    'state': mr['state'],
    'author': mr.get('author', {}).get('username', ''),
    'web_url': mr['web_url'],
    'source_branch': mr.get('source_branch', ''),
    'target_branch': mr.get('target_branch', ''),
}))
"
    ;;
  mr-discussions)
    # Args: project_path (URL-encoded), mr_iid
    PROJECT="${2:?Usage: gitlab-api.sh mr-discussions <project_path_urlencoded> <mr_iid>}"
    MR_IID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID/discussions?per_page=100" | python3 -c "
import sys, json
discussions = json.load(sys.stdin)
for d in discussions:
    notes = d.get('notes', [])
    if not notes:
        continue
    first = notes[0]
    # Skip system notes
    if first.get('system', False):
        continue
    thread = {
        'id': d['id'],
        'resolved': first.get('resolved', None),
        'resolvable': first.get('resolvable', False),
        'author': first.get('author', {}).get('username', ''),
        'body': first.get('body', ''),
        'created_at': first.get('created_at', ''),
        'position': None,
        'replies': [],
    }
    pos = first.get('position')
    if pos:
        thread['position'] = {
            'new_path': pos.get('new_path', ''),
            'old_path': pos.get('old_path', ''),
            'new_line': pos.get('new_line'),
            'old_line': pos.get('old_line'),
        }
    for note in notes[1:]:
        if note.get('system', False):
            continue
        thread['replies'].append({
            'author': note.get('author', {}).get('username', ''),
            'body': note.get('body', ''),
            'created_at': note.get('created_at', ''),
        })
    print(json.dumps(thread))
"
    ;;
  mr-changes)
    # Args: project_path (URL-encoded), mr_iid
    PROJECT="${2:?Usage: gitlab-api.sh mr-changes <project_path_urlencoded> <mr_iid>}"
    MR_IID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID/changes" | python3 -c "
import sys, json
data = json.load(sys.stdin)
changes = data.get('changes', [])
for c in changes:
    print(json.dumps({
        'old_path': c.get('old_path', ''),
        'new_path': c.get('new_path', ''),
        'diff': c.get('diff', ''),
    }))
"
    ;;
  reply-to-thread)
    # Args: project_path (URL-encoded), mr_iid, discussion_id, body
    PROJECT="${2:?Usage: gitlab-api.sh reply-to-thread <project_path_urlencoded> <mr_iid> <discussion_id> <body>}"
    MR_IID="${3:?}"
    DISCUSSION_ID="${4:?}"
    BODY="${5:?}"
    curl -sf -X POST -H "PRIVATE-TOKEN: $TOKEN" \
      --data-urlencode "body=$BODY" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID/discussions/$DISCUSSION_ID/notes" | python3 -c "
import sys, json
note = json.load(sys.stdin)
print(json.dumps({
    'id': note['id'],
    'author': note.get('author', {}).get('username', ''),
    'body': note.get('body', ''),
    'created_at': note.get('created_at', ''),
}))
"
    ;;
  mr-commits)
    # Args: project_path (URL-encoded), mr_iid
    PROJECT="${2:?Usage: gitlab-api.sh mr-commits <project_path_urlencoded> <mr_iid>}"
    MR_IID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID/commits?per_page=100" | python3 -c "
import sys, json
commits = json.load(sys.stdin)
for c in commits:
    print(json.dumps({
        'id': c.get('id', ''),
        'short_id': c.get('short_id', ''),
        'title': c.get('title', ''),
        'message': c.get('message', ''),
        'author_name': c.get('author_name', ''),
        'created_at': c.get('created_at', ''),
    }))
"
    ;;
  mr-pipelines)
    # Args: project_path (URL-encoded), mr_iid
    PROJECT="${2:?Usage: gitlab-api.sh mr-pipelines <project_path_urlencoded> <mr_iid>}"
    MR_IID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID/pipelines?per_page=10" | python3 -c "
import sys, json
pipelines = json.load(sys.stdin)
for p in pipelines:
    print(json.dumps({
        'id': p.get('id'),
        'iid': p.get('iid'),
        'status': p.get('status', ''),
        'ref': p.get('ref', ''),
        'sha': p.get('sha', ''),
        'source': p.get('source', ''),
        'web_url': p.get('web_url', ''),
        'created_at': p.get('created_at', ''),
        'updated_at': p.get('updated_at', ''),
    }))
"
    ;;
  pipeline-jobs)
    # Args: project_path (URL-encoded), pipeline_id
    PROJECT="${2:?Usage: gitlab-api.sh pipeline-jobs <project_path_urlencoded> <pipeline_id>}"
    PIPELINE_ID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/pipelines/$PIPELINE_ID/jobs?per_page=100" | python3 -c "
import sys, json
jobs = json.load(sys.stdin)
for j in jobs:
    print(json.dumps({
        'id': j.get('id'),
        'name': j.get('name', ''),
        'stage': j.get('stage', ''),
        'status': j.get('status', ''),
        'allow_failure': j.get('allow_failure', False),
        'web_url': j.get('web_url', ''),
        'failure_reason': j.get('failure_reason', ''),
    }))
"
    ;;
  pipeline-bridges)
    # Args: project_path (URL-encoded), pipeline_id
    # Lists child-pipeline trigger jobs (bridges) and their downstream pipelines.
    PROJECT="${2:?Usage: gitlab-api.sh pipeline-bridges <project_path_urlencoded> <pipeline_id>}"
    PIPELINE_ID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/pipelines/$PIPELINE_ID/bridges?per_page=100" | python3 -c "
import sys, json
bridges = json.load(sys.stdin)
for b in bridges:
    dp = b.get('downstream_pipeline') or {}
    print(json.dumps({
        'name': b.get('name', ''),
        'stage': b.get('stage', ''),
        'status': b.get('status', ''),
        'downstream_id': dp.get('id'),
        'downstream_status': dp.get('status', ''),
        'downstream_web_url': dp.get('web_url', ''),
    }))
"
    ;;
  job-log)
    # Args: project_path (URL-encoded), job_id
    PROJECT="${2:?Usage: gitlab-api.sh job-log <project_path_urlencoded> <job_id>}"
    JOB_ID="${3:?}"
    curl -sf -H "PRIVATE-TOKEN: $TOKEN" \
      "$GITLAB_URL/projects/$PROJECT/jobs/$JOB_ID/trace"
    ;;
  create-mr)
    # Args: project_path (URL-encoded), source_branch, target_branch, title, [description_file]
    # description_file: path to a file with the MR description, or "-" for stdin, or omitted for none.
    # To open as a Draft, prefix the title with "Draft: ".
    PROJECT="${2:?Usage: gitlab-api.sh create-mr <project_path_urlencoded> <source_branch> <target_branch> <title> [description_file]}"
    SOURCE_BRANCH="${3:?}"
    TARGET_BRANCH="${4:?}"
    TITLE="${5:?}"
    DESC_FILE="${6:-}"
    DESC_ARGS=()
    if [[ -n "$DESC_FILE" ]]; then
      if [[ "$DESC_FILE" == "-" ]]; then DESC_FILE=/dev/stdin; fi
      DESC_ARGS=(--data-urlencode "description@$DESC_FILE")
    fi
    curl -sf -X POST -H "PRIVATE-TOKEN: $TOKEN" \
      --data-urlencode "source_branch=$SOURCE_BRANCH" \
      --data-urlencode "target_branch=$TARGET_BRANCH" \
      --data-urlencode "title=$TITLE" \
      --data-urlencode "remove_source_branch=true" \
      "${DESC_ARGS[@]}" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests" | python3 -c "
import sys, json
mr = json.load(sys.stdin)
print(json.dumps({
    'iid': mr.get('iid'),
    'web_url': mr.get('web_url', ''),
    'title': mr.get('title', ''),
    'draft': mr.get('work_in_progress', False) or mr.get('draft', False),
    'source_branch': mr.get('source_branch', ''),
    'target_branch': mr.get('target_branch', ''),
}))
"
    ;;
  update-mr-description)
    # Args: project_path (URL-encoded), mr_iid, description_file
    # description_file: path to a file with the new description, or "-" for stdin.
    PROJECT="${2:?Usage: gitlab-api.sh update-mr-description <project_path_urlencoded> <mr_iid> <description_file>}"
    MR_IID="${3:?}"
    DESC_FILE="${4:?}"
    if [[ "$DESC_FILE" == "-" ]]; then DESC_FILE=/dev/stdin; fi
    curl -sf -X PUT -H "PRIVATE-TOKEN: $TOKEN" \
      --data-urlencode "description@$DESC_FILE" \
      "$GITLAB_URL/projects/$PROJECT/merge_requests/$MR_IID" | python3 -c "
import sys, json
mr = json.load(sys.stdin)
print(json.dumps({
    'iid': mr.get('iid'),
    'web_url': mr.get('web_url', ''),
    'title': mr.get('title', ''),
    'description_len': len(mr.get('description') or ''),
}))
"
    ;;
  *)
    echo "Usage: gitlab-api.sh {current-user|merged-mrs|open-mrs|mr-info|mr-discussions|mr-changes|mr-commits|reply-to-thread|create-mr|update-mr-description}" >&2
    exit 1
    ;;
esac

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
  *)
    echo "Usage: gitlab-api.sh {current-user|merged-mrs|open-mrs|mr-info|mr-discussions|mr-changes|mr-commits|reply-to-thread}" >&2
    exit 1
    ;;
esac

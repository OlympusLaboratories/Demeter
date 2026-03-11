#!/usr/bin/env python3
"""GitHub API helper for Claude skills.
Token read from GITHUB_PERSONAL_ACCESS_TOKEN environment variable.

Usage: github_api.py <command> [args...]
Commands: current-user | open-prs | merged-prs | pr-info | pr-reviews | pr-changes | pr-commits
"""

import json
import os
import sys
import urllib.request
import urllib.parse


def load_token():
    token = os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN')
    if not token:
        sys.exit('Error: GITHUB_PERSONAL_ACCESS_TOKEN is not set in the environment')
    return token


def api_get(token, path, params=None):
    url = 'https://api.github.com' + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def graphql_post(token, query, variables=None):
    payload = json.dumps({'query': query, 'variables': variables or {}}).encode()
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=payload,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if 'errors' in result:
        sys.exit(f'GraphQL error: {result["errors"]}')
    return result['data']


def emit(obj):
    print(json.dumps(obj))


def cmd_current_user(token, args):
    u = api_get(token, '/user')
    emit({'username': u['login'], 'id': u['id'], 'name': u.get('name', u['login'])})


def cmd_open_prs(token, args):
    if not args:
        sys.exit('Usage: github_api.py open-prs <username>')
    username = args[0]
    data = api_get(token, '/search/issues', {'q': f'type:pr author:{username} state:open', 'per_page': 50})
    for pr in data.get('items', []):
        emit({
            'title': pr['title'],
            'web_url': pr['html_url'],
            'draft': pr.get('draft', False),
            'description': (pr.get('body') or '')[:200],
        })


def cmd_merged_prs(token, args):
    if len(args) < 2:
        sys.exit('Usage: github_api.py merged-prs <username> <updated_after>')
    username, updated_after = args[0], args[1]
    data = api_get(token, '/search/issues', {
        'q': f'type:pr author:{username} is:merged updated:>={updated_after}',
        'per_page': 50,
    })
    for pr in data.get('items', []):
        emit({
            'title': pr['title'],
            'web_url': pr['html_url'],
            'merged_at': pr.get('pull_request', {}).get('merged_at', ''),
            'description': (pr.get('body') or '')[:200],
        })


def cmd_pr_info(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-info <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    pr = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}')
    emit({
        'title': pr['title'],
        'description': pr.get('body', ''),
        'state': pr['state'],
        'author': pr.get('user', {}).get('login', ''),
        'web_url': pr['html_url'],
        'source_branch': pr.get('head', {}).get('ref', ''),
        'target_branch': pr.get('base', {}).get('ref', ''),
        'number': pr['number'],
        'draft': pr.get('draft', False),
    })


_PR_REVIEWS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 50) {
            nodes {
              id
              author { login }
              body
              createdAt
              replyTo { id }
            }
          }
        }
      }
      reviews(first: 50) {
        nodes {
          id
          author { login }
          body
          state
          submittedAt
        }
      }
      comments(first: 100) {
        nodes {
          id
          author { login }
          body
          createdAt
        }
      }
    }
  }
}
"""


def cmd_pr_reviews(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-reviews <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]

    data = graphql_post(token, _PR_REVIEWS_QUERY, {
        'owner': owner,
        'repo': repo,
        'number': int(number),
    })
    pr = data['repository']['pullRequest']

    # Inline review threads — isResolved comes directly from GraphQL
    for thread in pr['reviewThreads']['nodes']:
        comments = thread['comments']['nodes']
        root = comments[0] if comments else {}
        replies = comments[1:]
        emit({
            'id': thread['id'],
            'type': 'inline',
            'resolved': thread['isResolved'],
            'resolvable': True,
            'author': (root.get('author') or {}).get('login', ''),
            'body': root.get('body', ''),
            'created_at': root.get('createdAt', ''),
            'position': {
                'new_path': thread.get('path', ''),
                'old_path': thread.get('path', ''),
                'new_line': thread.get('line') or thread.get('originalLine'),
                'old_line': thread.get('originalLine'),
            },
            'replies': [
                {
                    'author': (r.get('author') or {}).get('login', ''),
                    'body': r.get('body', ''),
                    'created_at': r.get('createdAt', ''),
                }
                for r in replies
            ],
        })

    # Non-empty review summary comments (approval/request-changes bodies)
    for r in pr['reviews']['nodes']:
        body = (r.get('body') or '').strip()
        if not body:
            continue
        emit({
            'id': f'review-{r["id"]}',
            'type': 'review',
            'resolved': None,
            'resolvable': False,
            'author': (r.get('author') or {}).get('login', ''),
            'body': body,
            'created_at': r.get('submittedAt', ''),
            'position': None,
            'replies': [],
            'review_state': r.get('state', ''),
        })

    # General PR comments (not attached to a line)
    for c in pr['comments']['nodes']:
        emit({
            'id': f'issue-{c["id"]}',
            'type': 'general',
            'resolved': None,
            'resolvable': False,
            'author': (c.get('author') or {}).get('login', ''),
            'body': c.get('body', ''),
            'created_at': c.get('createdAt', ''),
            'position': None,
            'replies': [],
        })


def cmd_pr_changes(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-changes <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    files = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}/files', {'per_page': 100})
    for f in files:
        emit({
            'old_path': f.get('previous_filename', f.get('filename', '')),
            'new_path': f.get('filename', ''),
            'diff': f.get('patch', ''),
            'status': f.get('status', ''),
        })


def cmd_pr_commits(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-commits <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    commits = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}/commits', {'per_page': 100})
    for c in commits:
        commit = c.get('commit', {})
        emit({
            'id': c.get('sha', ''),
            'short_id': c.get('sha', '')[:7],
            'title': commit.get('message', '').split('\n')[0],
            'message': commit.get('message', ''),
            'author_name': commit.get('author', {}).get('name', ''),
            'created_at': commit.get('author', {}).get('date', ''),
        })


COMMANDS = {
    'current-user': cmd_current_user,
    'open-prs':     cmd_open_prs,
    'merged-prs':   cmd_merged_prs,
    'pr-info':      cmd_pr_info,
    'pr-reviews':   cmd_pr_reviews,
    'pr-changes':   cmd_pr_changes,
    'pr-commits':   cmd_pr_commits,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f'Usage: github_api.py {{{"| ".join(COMMANDS)}}}')
    token = load_token()
    COMMANDS[sys.argv[1]](token, sys.argv[2:])

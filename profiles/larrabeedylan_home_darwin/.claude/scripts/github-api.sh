#!/usr/bin/env python3
"""GitHub API helper for Claude skills.
Token read from GITHUB_PERSONAL_ACCESS_TOKEN environment variable.

Usage: github_api.py <command> [args...]
Commands: current-user | open-prs | merged-prs | pr-info | pr-reviews | pr-changes | pr-commits |
          pr-for-branch | reply-to-thread | create-diff-comment
"""

import json
import os
import subprocess
import sys
import urllib.error
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


def api_post(token, path, payload):
    req = urllib.request.Request(
        'https://api.github.com' + path,
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        },
    )
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


_REPLY_TO_THREAD_MUTATION = """
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
    comment {
      id
      body
      createdAt
    }
  }
}
"""


def cmd_reply_to_thread(token, args):
    if len(args) < 1:
        sys.exit('Usage: github_api.py reply-to-thread <thread_id> [body]\n'
                 '       If body is omitted, reads from stdin.')
    thread_id = args[0]
    body = args[1] if len(args) >= 2 else sys.stdin.read().strip()
    if not body:
        sys.exit('Error: empty reply body')
    data = graphql_post(token, _REPLY_TO_THREAD_MUTATION, {
        'threadId': thread_id,
        'body': body,
    })
    comment = data['addPullRequestReviewThreadReply']['comment']
    emit({
        'id': comment['id'],
        'body': comment['body'],
        'created_at': comment['createdAt'],
    })


def _git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True).stdout.strip()


def _repo_from_remote():
    url = _git('remote', 'get-url', 'origin')
    if not url:
        sys.exit('Error: no origin remote to derive owner/repo from')
    path = url
    for scheme in ('https://', 'http://', 'ssh://'):
        if path.startswith(scheme):
            path = path[len(scheme):]
            path = path.split('/', 1)[1] if '/' in path else path
            break
    else:
        path = path.split(':', 1)[1] if ':' in path else path
    if path.endswith('.git'):
        path = path[:-4]
    parts = path.strip('/').split('/')
    if len(parts) < 2:
        sys.exit(f'Error: cannot parse owner/repo out of {url}')
    return parts[-2], parts[-1]


def cmd_pr_for_branch(token, args):
    owner = args[0] if args else '-'
    repo = args[1] if len(args) > 1 else '-'
    branch = args[2] if len(args) > 2 else '-'
    if owner == '-' or repo == '-':
        owner, repo = _repo_from_remote()
    if branch == '-':
        branch = _git('rev-parse', '--abbrev-ref', 'HEAD')
    if not branch or branch == 'HEAD':
        sys.exit('Error: could not determine the current branch')
    prs = api_get(token, f'/repos/{owner}/{repo}/pulls',
                  {'head': f'{owner}:{branch}', 'state': 'open', 'per_page': 20})
    for pr in prs:
        emit({
            'number': pr['number'],
            'title': pr.get('title', ''),
            'web_url': pr.get('html_url', ''),
            'owner': owner,
            'repo': repo,
            'source_branch': pr.get('head', {}).get('ref', ''),
            'target_branch': pr.get('base', {}).get('ref', ''),
            'draft': pr.get('draft', False),
        })


def cmd_create_diff_comment(token, args):
    if len(args) < 4:
        sys.exit('Usage: github_api.py create-diff-comment <owner> <repo> <pr_number> <path> [line|-]\n'
                 '       The comment body is read from stdin.')
    owner, repo, number, path = args[0], args[1], args[2], args[3]
    raw_line = args[4] if len(args) > 4 else '-'
    line = None
    if raw_line not in ('', '-'):
        try:
            line = int(raw_line)
        except ValueError:
            line = None
    body = sys.stdin.read().strip()
    if not body:
        sys.exit('Error: empty comment body')

    pr = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}')
    head_sha = pr.get('head', {}).get('sha', '')
    anchored = False
    reason = 'no line given' if line is None else ''
    comment = None

    if line is not None and head_sha:
        try:
            comment = api_post(token, f'/repos/{owner}/{repo}/pulls/{number}/comments', {
                'body': body,
                'commit_id': head_sha,
                'path': path,
                'line': line,
                'side': 'RIGHT',
            })
            anchored = True
        except urllib.error.HTTPError as err:
            reason = f'GitHub rejected the line anchor ({err.code}): {err.read().decode()[:200]}'
    elif line is not None:
        reason = 'the PR has no head sha to anchor against'

    if comment is None and head_sha:
        try:
            comment = api_post(token, f'/repos/{owner}/{repo}/pulls/{number}/comments', {
                'body': body,
                'commit_id': head_sha,
                'path': path,
                'subject_type': 'file',
            })
        except urllib.error.HTTPError as err:
            reason = f'{reason}; file-level anchor also rejected ({err.code})'.lstrip('; ')

    if comment is None:
        where = f'`{path}`' if line is None else f'`{path}:{line}`'
        comment = api_post(token, f'/repos/{owner}/{repo}/issues/{number}/comments',
                           {'body': f'**{where}**\n\n{body}'})

    emit({
        'comment_id': comment.get('id'),
        'node_id': comment.get('node_id', ''),
        'anchored': anchored,
        'path': path,
        'line': line,
        'url': comment.get('html_url', ''),
        'fallback_reason': '' if anchored else reason,
    })


COMMANDS = {
    'current-user':    cmd_current_user,
    'open-prs':        cmd_open_prs,
    'merged-prs':      cmd_merged_prs,
    'pr-info':         cmd_pr_info,
    'pr-reviews':      cmd_pr_reviews,
    'pr-changes':      cmd_pr_changes,
    'pr-commits':      cmd_pr_commits,
    'pr-for-branch':   cmd_pr_for_branch,
    'reply-to-thread': cmd_reply_to_thread,
    'create-diff-comment': cmd_create_diff_comment,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f'Usage: github_api.py {{{"| ".join(COMMANDS)}}}')
    token = load_token()
    COMMANDS[sys.argv[1]](token, sys.argv[2:])

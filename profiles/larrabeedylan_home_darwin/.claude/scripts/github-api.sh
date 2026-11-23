#!/usr/bin/env python3
"""GitHub API helper for Claude skills.
Token read from GITHUB_PERSONAL_ACCESS_TOKEN environment variable.

Usage: github_api.py <command> [args...]
Run `github_api.py help` for every command and the arguments it takes.
"""

import inspect
import json
import os
import re
import subprocess
import sys
import time
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


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_get_text(token, path):
    opener = urllib.request.build_opener(_NoAutoRedirect)
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with opener.open(req) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        if err.code not in (301, 302, 303, 307, 308):
            raise
        with urllib.request.urlopen(err.headers['Location']) as resp:
            raw = resp.read()
    return raw.decode('utf-8', errors='replace').lstrip('\ufeff')


def api_get_all(token, path, params=None, key=None):
    results = []
    page = 1
    while True:
        query = dict(params or {})
        query.update({'per_page': 100, 'page': page})
        data = api_get(token, path, query)
        batch = data.get(key, []) if key else data
        results.extend(batch)
        if len(batch) < 100:
            return results
        page += 1


def api_post(token, path, payload, method='POST'):
    req = urllib.request.Request(
        'https://api.github.com' + path,
        data=json.dumps(payload).encode(),
        method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
    return json.loads(raw) if raw.strip() else {}


def http_error_message(err):
    raw = err.read().decode(errors='replace')
    try:
        body = json.loads(raw)
    except ValueError:
        return f'HTTP {err.code}: {raw[:300]}'
    detail = body.get('message') or raw[:300]
    if body.get('errors'):
        detail = f'{detail} ({json.dumps(body["errors"])})'
    return f'HTTP {err.code}: {detail}'


def graphql_request(token, query, variables=None):
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
        return json.loads(resp.read())


def graphql_error_message(result):
    errors = result.get('errors') or []
    messages = [e.get('message', '') for e in errors if e.get('message')]
    return '; '.join(messages) or json.dumps(errors)


def graphql_post(token, query, variables=None):
    result = graphql_request(token, query, variables)
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
    for f in api_get_all(token, f'/repos/{owner}/{repo}/pulls/{number}/files'):
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
    commits = api_get_all(token, f'/repos/{owner}/{repo}/pulls/{number}/commits')
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
    if len(args) > 3:
        sys.exit('Usage: github_api.py pr-for-branch [owner|-] [repo|-] [branch|-]\n'
                 '       "-" derives owner and repo from the origin remote, and the branch\n'
                 '       from HEAD. Every argument defaults to "-".')
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


def _read_body(path):
    if path == '-':
        return sys.stdin.read()
    try:
        with open(path) as handle:
            return handle.read()
    except OSError as err:
        sys.exit(f'Error: cannot read body file {path}: {err}')


def _merge_method(args, index):
    method = args[index] if len(args) > index and args[index] else 'squash'
    if method not in ('squash', 'merge', 'rebase'):
        sys.exit(f'Error: merge method must be squash, merge or rebase, got {method!r}')
    return method


def cmd_create_pr(token, args):
    if len(args) < 5:
        sys.exit('Usage: github_api.py create-pr <owner> <repo> <head_branch> <base_branch> <title> [body_file]\n'
                 '       body_file is a path, "-" for stdin, or omitted for no body.\n'
                 '       A title starting with "Draft: " opens the PR as a draft.')
    owner, repo, head, base, title = args[0], args[1], args[2], args[3], args[4]
    payload = {'head': head, 'base': base, 'title': title}
    if title.startswith('Draft: '):
        payload['title'] = title[len('Draft: '):]
        payload['draft'] = True
    if len(args) > 5 and args[5]:
        payload['body'] = _read_body(args[5])
    pr = api_post(token, f'/repos/{owner}/{repo}/pulls', payload)
    emit({
        'number': pr.get('number'),
        'html_url': pr.get('html_url', ''),
        'title': pr.get('title', ''),
        'draft': pr.get('draft', False),
        'head': pr.get('head', {}).get('ref', ''),
        'base': pr.get('base', {}).get('ref', ''),
    })


def cmd_update_pr_description(token, args):
    if len(args) < 4:
        sys.exit('Usage: github_api.py update-pr-description <owner> <repo> <pr_number> <body_file>\n'
                 '       body_file is a path, or "-" for stdin.')
    owner, repo, number = args[0], args[1], args[2]
    pr = api_post(token, f'/repos/{owner}/{repo}/pulls/{number}',
                  {'body': _read_body(args[3])}, method='PATCH')
    emit({
        'number': pr.get('number'),
        'html_url': pr.get('html_url', ''),
        'title': pr.get('title', ''),
        'body_len': len(pr.get('body') or ''),
    })


def cmd_pr_checks(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-checks <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    pr = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}')
    head_sha = pr.get('head', {}).get('sha', '')
    if not head_sha:
        sys.exit('Error: the PR has no head sha to resolve checks against')

    for run in api_get_all(token, f'/repos/{owner}/{repo}/commits/{head_sha}/check-runs',
                           key='check_runs'):
        emit({
            'id': run.get('id'),
            'name': run.get('name', ''),
            'status': run.get('status', ''),
            'conclusion': run.get('conclusion'),
            'html_url': run.get('html_url', ''),
            'source': 'check_run',
            'rerunnable': True,
        })

    for status in api_get_all(token, f'/repos/{owner}/{repo}/commits/{head_sha}/status',
                              key='statuses'):
        state = status.get('state', '')
        emit({
            'id': status.get('id'),
            'name': status.get('context', ''),
            'status': 'in_progress' if state == 'pending' else 'completed',
            'conclusion': None if state == 'pending' else state,
            'html_url': status.get('target_url') or '',
            'source': 'status',
            'rerunnable': False,
        })


def cmd_pr_merge(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-merge <owner> <repo> <pr_number> [squash|merge|rebase]')
    owner, repo, number = args[0], args[1], args[2]
    merge_method = _merge_method(args, 3)
    try:
        result = api_post(token, f'/repos/{owner}/{repo}/pulls/{number}/merge',
                          {'merge_method': merge_method}, method='PUT')
    except urllib.error.HTTPError as err:
        emit({'error': http_error_message(err)})
        sys.exit(1)
    emit({
        'merged': result.get('merged', False),
        'sha': result.get('sha', ''),
        'message': result.get('message', ''),
    })


_ENABLE_AUTO_MERGE_MUTATION = """
mutation($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
  enablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId, mergeMethod: $mergeMethod}) {
    pullRequest {
      number
      autoMergeRequest { enabledAt mergeMethod }
    }
  }
}
"""

_DISABLE_AUTO_MERGE_MUTATION = """
mutation($pullRequestId: ID!) {
  disablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId}) {
    pullRequest {
      number
      autoMergeRequest { enabledAt }
    }
  }
}
"""


def _pr_node_id(token, owner, repo, number):
    pr = api_get(token, f'/repos/{owner}/{repo}/pulls/{number}')
    node_id = pr.get('node_id', '')
    if not node_id:
        emit({'error': f'PR {owner}/{repo}#{number} has no GraphQL node id'})
        sys.exit(1)
    return node_id


def _graphql_mutation(token, query, variables):
    try:
        result = graphql_request(token, query, variables)
    except urllib.error.HTTPError as err:
        emit({'error': http_error_message(err)})
        sys.exit(1)
    if result.get('errors'):
        emit({'error': graphql_error_message(result)})
        sys.exit(1)
    return result['data']


def cmd_pr_auto_merge(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-auto-merge <owner> <repo> <pr_number> [squash|merge|rebase]\n'
                 '       Requires auto-merge enabled on the repository and at least one\n'
                 '       required check or review on the base branch.')
    owner, repo, number = args[0], args[1], args[2]
    merge_method = _merge_method(args, 3)
    node_id = _pr_node_id(token, owner, repo, number)
    data = _graphql_mutation(token, _ENABLE_AUTO_MERGE_MUTATION, {
        'pullRequestId': node_id,
        'mergeMethod': merge_method.upper(),
    })
    pr = (data.get('enablePullRequestAutoMerge') or {}).get('pullRequest') or {}
    emit({'enabled': True, 'number': pr.get('number', int(number))})


def cmd_pr_cancel_auto_merge(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-cancel-auto-merge <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    node_id = _pr_node_id(token, owner, repo, number)
    data = _graphql_mutation(token, _DISABLE_AUTO_MERGE_MUTATION, {'pullRequestId': node_id})
    pr = (data.get('disablePullRequestAutoMerge') or {}).get('pullRequest') or {}
    emit({'enabled': False, 'number': pr.get('number', int(number))})


_RESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""

_UNRESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  unresolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def _set_thread_resolution(token, args, query, field, resolved):
    thread_id = args[2]
    data = _graphql_mutation(token, query, {'threadId': thread_id})
    thread = (data.get(field) or {}).get('thread') or {}
    emit({'id': thread.get('id') or thread_id, 'resolved': thread.get('isResolved', resolved)})


def cmd_resolve_thread(token, args):
    if len(args) < 3 or not all(args[:3]):
        sys.exit('Usage: github_api.py resolve-thread <owner> <repo> <thread_id>\n'
                 '       thread_id is the GraphQL node id of a PullRequestReviewThread, as\n'
                 '       returned by pr-reviews. A REST comment id will not work.')
    _set_thread_resolution(token, args,
                           _RESOLVE_THREAD_MUTATION, 'resolveReviewThread', True)


def cmd_unresolve_thread(token, args):
    if len(args) < 3 or not all(args[:3]):
        sys.exit('Usage: github_api.py unresolve-thread <owner> <repo> <thread_id>\n'
                 '       thread_id is the GraphQL node id of a PullRequestReviewThread, as\n'
                 '       returned by pr-reviews. A REST comment id will not work.')
    _set_thread_resolution(token, args,
                           _UNRESOLVE_THREAD_MUTATION, 'unresolveReviewThread', False)


_PR_REVIEW_DECISION_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewDecision
    }
  }
}
"""


def cmd_pr_status(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-status <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    path = f'/repos/{owner}/{repo}/pulls/{number}'

    pr = api_get(token, path)
    if pr.get('mergeable') is None and pr.get('state') == 'open':
        time.sleep(2)
        pr = api_get(token, path)

    data = graphql_post(token, _PR_REVIEW_DECISION_QUERY, {
        'owner': owner,
        'repo': repo,
        'number': int(number),
    })
    emit({
        'number': pr.get('number'),
        'state': pr.get('state', ''),
        'draft': pr.get('draft', False),
        'mergeable': pr.get('mergeable'),
        'mergeable_state': pr.get('mergeable_state', 'unknown'),
        'rebaseable': pr.get('rebaseable'),
        'head_sha': pr.get('head', {}).get('sha', ''),
        'review_decision': data['repository']['pullRequest']['reviewDecision'],
        'merged': pr.get('merged', False),
    })


def cmd_pr_notes(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py pr-notes <owner> <repo> <pr_number>')
    owner, repo, number = args[0], args[1], args[2]
    for note in api_get_all(token, f'/repos/{owner}/{repo}/issues/{number}/comments'):
        emit({
            'id': note.get('id'),
            'author': (note.get('user') or {}).get('login', ''),
            'body': note.get('body', ''),
            'created_at': note.get('created_at', ''),
        })


def cmd_rerun_check(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py rerun-check <owner> <repo> <check_run_id>')
    owner, repo, check_run_id = args[0], args[1], args[2]
    try:
        api_post(token, f'/repos/{owner}/{repo}/check-runs/{check_run_id}/rerequest', {})
    except urllib.error.HTTPError as err:
        emit({'error': http_error_message(err)})
        sys.exit(1)
    emit({'ok': True})


def cmd_job_log(token, args):
    if len(args) < 3:
        sys.exit('Usage: github_api.py job-log <owner> <repo> <job_id> [lines|all]')
    owner, repo, job_id = args[0], args[1], args[2]
    budget = args[3] if len(args) > 3 else '400'
    if budget != 'all' and not budget.isdigit():
        sys.exit(f'job-log: line budget must be a number or "all", got "{budget}"')

    try:
        check = api_get(token, f'/repos/{owner}/{repo}/check-runs/{job_id}')
    except urllib.error.HTTPError as err:
        if err.code == 404:
            emit({'error': f'no check run {job_id} in {owner}/{repo}; a commit status has no '
                           'Actions job behind it and so has no log this helper can read'})
        else:
            emit({'error': http_error_message(err)})
        sys.exit(1)

    slug = (check.get('app') or {}).get('slug') or 'unknown'
    if slug != 'github-actions':
        emit({
            'error': f'check run {job_id} was produced by "{slug}", not GitHub Actions, '
                     'so there is no job log to read',
            'name': check.get('name', ''),
            'html_url': check.get('html_url', ''),
        })
        sys.exit(1)

    try:
        log = api_get_text(token, f'/repos/{owner}/{repo}/actions/jobs/{job_id}/logs')
    except urllib.error.HTTPError as err:
        emit({'error': http_error_message(err)})
        sys.exit(1)

    lines = log.rstrip('\n').split('\n') if log.strip() else []
    total = len(lines)
    if budget == 'all':
        kept = lines
        print(f'==> job-log: {total} lines, all shown')
    else:
        kept = lines[-int(budget):] if int(budget) else []
        print(f'==> job-log: {total} lines, showing last {len(kept)}, '
              f'{total - len(kept)} dropped from the head (pass "all" for the whole log)')
    for line in kept:
        print(line)


def _arguments_of(fn):
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return ''
    match = re.search(r"Usage: github_api\.py [a-z][a-z0-9-]* ?([^'\\]*)", source)
    return match.group(1).strip() if match else ''


def cmd_help(token, args):
    for name, fn in COMMANDS.items():
        arguments = _arguments_of(fn)
        print(f'{name:<24} {arguments}' if arguments else name)


COMMANDS = {
    'help':            cmd_help,
    'current-user':    cmd_current_user,
    'open-prs':        cmd_open_prs,
    'merged-prs':      cmd_merged_prs,
    'pr-info':         cmd_pr_info,
    'pr-reviews':      cmd_pr_reviews,
    'pr-changes':      cmd_pr_changes,
    'pr-commits':      cmd_pr_commits,
    'pr-for-branch':   cmd_pr_for_branch,
    'reply-to-thread': cmd_reply_to_thread,
    'resolve-thread':  cmd_resolve_thread,
    'unresolve-thread': cmd_unresolve_thread,
    'create-diff-comment': cmd_create_diff_comment,
    'create-pr':       cmd_create_pr,
    'update-pr-description': cmd_update_pr_description,
    'pr-checks':       cmd_pr_checks,
    'pr-merge':        cmd_pr_merge,
    'pr-auto-merge':   cmd_pr_auto_merge,
    'pr-cancel-auto-merge': cmd_pr_cancel_auto_merge,
    'pr-status':       cmd_pr_status,
    'pr-notes':        cmd_pr_notes,
    'rerun-check':     cmd_rerun_check,
    'job-log':         cmd_job_log,
}

if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command in ('--help', '-h'):
        command = 'help'
    if command not in COMMANDS:
        print(f'Usage: github_api.py {{{"|".join(COMMANDS)}}}', file=sys.stderr)
        print("Run 'github_api.py help' for each command's arguments.", file=sys.stderr)
        sys.exit(1)
    token = None if command == 'help' else load_token()
    COMMANDS[command](token, sys.argv[2:])

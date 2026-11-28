import re, sys
lines = open(sys.argv[1]).read().split('\n')
diff_lines, files = int(sys.argv[2]), int(sys.argv[3])
size = 'large' if diff_lines > 1200 or files > 12 else 'medium' if diff_lines > 300 or files > 4 else 'small'
total, summary_cap, bullet_cap, changes_cap = {
    'small': (170, 60, 4, 100), 'medium': (250, 80, 6, 150), 'large': (320, 80, 8, 200),
}[size]
count = lambda s: len([t for t in s.split() if not re.fullmatch(r'[—–*+\-:;,.]+', t)])
has = lambda n: any(l.strip().lower() == '## ' + n for l in lines)
def section(name):
    i = next((i for i, l in enumerate(lines) if l.strip().lower() == '## ' + name), -1)
    if i < 0: return []
    rest = lines[i + 1:]
    return rest[:next((j for j, l in enumerate(rest) if l.strip().startswith('## ')), len(rest))]
bullets = []
for l in section('changes'):
    if re.match(r'^\s*[-*]\s+', l): bullets.append(re.sub(r'^\s*[-*]\s+', '', l).strip())
    elif l.strip() and bullets: bullets[-1] += ' ' + l.strip()
summary = ' '.join(section('summary')).strip()
sentences = [s.strip() for s in re.split(r'[.!?]+(?:\s+|$)', summary) if s.strip()]
cap = total + (25 if has('testing') else 0) + (30 if has('rollout') else 0)
body = count('\n'.join(l for l in lines if not l.startswith('##')))
print('%s change · %d diff lines · %d files' % (size, diff_lines, files))
print('total    %d / %d' % (body, cap))
print('summary  %d / %d words, %d / 3 sentences' % (count(summary), summary_cap, len(sentences)))
print('changes  %d / %d bullets, %d / %d words' % (len(bullets), bullet_cap, sum(map(count, bullets)), changes_cap))
for i, s in enumerate(sentences):
    if count(s) > 30: print('OVER: summary sentence %d is %d words, cap 30' % (i + 1, count(s)))
for i, b in enumerate(bullets):
    if count(b) > 25: print('OVER: bullet %d is %d words, cap 25 — %s' % (i + 1, count(b), b[:60]))

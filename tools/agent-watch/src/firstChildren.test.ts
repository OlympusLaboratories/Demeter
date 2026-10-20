import { describe, expect, it } from 'vitest';
import { FirstChildrenWatch } from './firstChildren';

describe('FirstChildrenWatch', () => {
  it('claims nothing on a first look, however many children are already there', () => {
    const watch = new FirstChildrenWatch();
    expect(
      watch.claim([
        { id: 'a', childCount: 0 },
        { id: 'b', childCount: 9 },
        { id: 'c', childCount: 96 },
      ]),
    ).toEqual([]);
  });

  it('claims a node the moment it gains its first children', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'a', childCount: 0 }]);
    expect(watch.claim([{ id: 'a', childCount: 3 }])).toEqual(['a']);
  });

  it('never claims the same node twice, however many more children arrive', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'a', childCount: 0 }]);
    expect(watch.claim([{ id: 'a', childCount: 1 }])).toEqual(['a']);
    expect(watch.claim([{ id: 'a', childCount: 2 }])).toEqual([]);
    expect(watch.claim([{ id: 'a', childCount: 40 }])).toEqual([]);
  });

  it('does not claim a node that arrives already carrying children', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'a', childCount: 0 }]);
    expect(watch.claim([{ id: 'a', childCount: 0 }, { id: 'b', childCount: 4 }])).toEqual([]);
  });

  it('forgets an id that was not on screen last pass, so arriving counts as a first look', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'hidden', childCount: 0 }]);
    watch.claim([{ id: 'something-else', childCount: 0 }]);

    expect(watch.claim([{ id: 'hidden', childCount: 5 }])).toEqual([]);
  });

  it('still suppresses a second claim when children vanish and come back', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'a', childCount: 0 }]);
    expect(watch.claim([{ id: 'a', childCount: 2 }])).toEqual(['a']);
    watch.claim([{ id: 'a', childCount: 0 }]);
    expect(watch.claim([{ id: 'a', childCount: 2 }])).toEqual([]);
  });

  it('keeps no record of ids it has stopped being shown', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([...Array(500)].map((_, index) => ({ id: `gone-${index}`, childCount: 1 })));
    watch.claim([{ id: 'only', childCount: 0 }]);

    expect(watch.claim([{ id: 'gone-0', childCount: 3 }])).toEqual([]);
  });

  it('forgets everything when the scope changes', () => {
    const watch = new FirstChildrenWatch();
    watch.claim([{ id: 'a', childCount: 0 }]);
    watch.claim([{ id: 'a', childCount: 2 }]);
    watch.clear();
    expect(watch.claim([{ id: 'a', childCount: 2 }])).toEqual([]);
  });
});

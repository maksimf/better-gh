export type Stackable = {
  stack_id: string | null;
  stack_order: number | null;
};

export type StackGroup<T extends Stackable> = { stackId: string; cards: T[] };

/**
 * Pull every stacked item into a group keyed by ``stack_id`` (root first,
 * then children in pre-order). First-seen order across the incoming list
 * is preserved so a newly opened stack doesn't jump around on poll.
 */
export function groupStacks<T extends Stackable>(items: T[]): StackGroup<T>[] {
  const groups = new Map<string, T[]>();
  const order: string[] = [];
  for (const item of items) {
    if (!item.stack_id) continue;
    let bucket = groups.get(item.stack_id);
    if (!bucket) {
      bucket = [];
      groups.set(item.stack_id, bucket);
      order.push(item.stack_id);
    }
    bucket.push(item);
  }
  return order.map((stackId) => ({
    stackId,
    cards: (groups.get(stackId) ?? []).sort(
      (a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0),
    ),
  }));
}

/**
 * Walk a list in its existing order, emitting each stack once (at the
 * first member) and leaving standalone items in place. Used by the
 * Reviewing list so a stack doesn't jump to the end of the queue.
 */
export function interleaveStacks<T extends Stackable>(
  items: T[],
): Array<{ kind: "item"; item: T } | { kind: "stack"; group: StackGroup<T> }> {
  const groups = groupStacks(items);
  const byId = new Map(groups.map((group) => [group.stackId, group]));
  const seen = new Set<string>();
  const out: Array<
    { kind: "item"; item: T } | { kind: "stack"; group: StackGroup<T> }
  > = [];
  for (const item of items) {
    if (!item.stack_id) {
      out.push({ kind: "item", item });
      continue;
    }
    if (seen.has(item.stack_id)) continue;
    seen.add(item.stack_id);
    const group = byId.get(item.stack_id);
    if (group) out.push({ kind: "stack", group });
  }
  return out;
}

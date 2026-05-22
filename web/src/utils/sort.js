export function priorityScore(item) {
  return item.forget_count * 10 + item.exam_frequency * 3;
}

function byRecent(a, b) {
  return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
}

function byWord(a, b) {
  return a.word.localeCompare(b.word, "en");
}

export function sortVocab(items, sortKey = "priority") {
  return [...items].sort((a, b) => {
    if (sortKey === "forget") {
      return b.forget_count - a.forget_count || b.exam_frequency - a.exam_frequency || byRecent(a, b) || byWord(a, b);
    }
    if (sortKey === "frequency") {
      return b.exam_frequency - a.exam_frequency || b.forget_count - a.forget_count || byRecent(a, b) || byWord(a, b);
    }
    if (sortKey === "recent") {
      return byRecent(a, b) || b.forget_count - a.forget_count || byWord(a, b);
    }
    if (sortKey === "alphabetical") {
      return byWord(a, b);
    }

    return (
      priorityScore(b) - priorityScore(a) ||
      b.forget_count - a.forget_count ||
      b.exam_frequency - a.exam_frequency ||
      byRecent(a, b) ||
      byWord(a, b)
    );
  });
}

export function normalizeWord(word = "") {
  return word.toLowerCase().replace(/[^a-z'-]/g, "");
}

function examInfo(frequency, normalizedWord) {
  const item = frequency[normalizedWord];
  if (!item) {
    return { score: 0, label: "未标注" };
  }
  return {
    score: Number.isInteger(item.score) ? item.score : 0,
    label: item.label || "未标注",
  };
}

export function enrichVocab(vocab, frequency) {
  return vocab.map((item) => {
    const normalized = item.normalized_word || normalizeWord(item.word);
    const info = examInfo(frequency, normalized);
    return {
      ...item,
      normalized_word: normalized,
      exam_frequency: info.score,
      exam_frequency_label: info.label,
      sources: Array.isArray(item.sources) ? item.sources : [],
      similar_words: Array.isArray(item.similar_words) ? item.similar_words : [],
      examples: Array.isArray(item.examples) ? item.examples : [],
    };
  });
}

export function isMissingChinese(item) {
  return !item.chinese || !item.chinese.trim();
}

export function isHighFrequency(item) {
  return item.exam_frequency >= 4 || ["高频", "超高频"].includes(item.exam_frequency_label);
}

export function filterVocab(items, { query, filter }) {
  const normalizedQuery = normalizeWord(query);
  return items.filter((item) => {
    if (normalizedQuery && !item.normalized_word.includes(normalizedQuery)) {
      return false;
    }
    if (filter === "forget5") {
      return item.forget_count >= 5;
    }
    if (filter === "forget10") {
      return item.forget_count >= 10;
    }
    if (filter === "highFrequency") {
      return isHighFrequency(item);
    }
    if (filter === "missingChinese") {
      return isMissingChinese(item);
    }
    if (filter === "missingFrequency") {
      return item.exam_frequency === 0 || item.exam_frequency_label === "未标注";
    }
    return true;
  });
}

export function getStats(items) {
  return items.reduce(
    (stats, item) => {
      stats.totalWords += 1;
      stats.totalForgetCount += item.forget_count;
      if (item.forget_count >= 5) {
        stats.highForgetWords += 1;
      }
      if (isHighFrequency(item)) {
        stats.highFrequencyWords += 1;
      }
      if (isMissingChinese(item)) {
        stats.missingChinese += 1;
      }
      if (item.exam_frequency === 0 || item.exam_frequency_label === "未标注") {
        stats.missingFrequency += 1;
      }
      return stats;
    },
    {
      totalWords: 0,
      totalForgetCount: 0,
      highForgetWords: 0,
      highFrequencyWords: 0,
      missingChinese: 0,
      missingFrequency: 0,
    },
  );
}

function sourceLabel(item) {
  const count = item.sources?.length ?? 0;
  return `${count} 条`;
}

function countClass(count) {
  if (count >= 10) {
    return "count-badge severe";
  }
  if (count >= 5) {
    return "count-badge hot";
  }
  return "count-badge";
}

export function VocabTable({ items, selectedWord, onSelect }) {
  if (!items.length) {
    return <p className="empty-table">没有匹配的词条。</p>;
  }

  return (
    <div className="table-scroll">
      <table className="vocab-table">
        <thead>
          <tr>
            <th>Word</th>
            <th>Forget Count</th>
            <th>Exam Frequency</th>
            <th>Last Seen</th>
            <th>Sources</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isSelected = item.normalized_word === selectedWord;
            return (
              <tr
                key={item.normalized_word}
                className={isSelected ? "is-selected" : ""}
                tabIndex={0}
                onClick={() => onSelect(item)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(item);
                  }
                }}
              >
                <td className="word-cell">
                  <span>{item.word}</span>
                </td>
                <td>
                  <span className={countClass(item.forget_count)}>{item.forget_count}</span>
                </td>
                <td>
                  <span className={item.exam_frequency >= 4 ? "freq-pill high" : "freq-pill"}>
                    {item.exam_frequency_label} · {item.exam_frequency}
                  </span>
                </td>
                <td>{item.last_seen}</td>
                <td>{sourceLabel(item)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

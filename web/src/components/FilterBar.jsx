import { Search } from "lucide-react";

const filters = [
  { value: "all", label: "全部" },
  { value: "forget5", label: "忘记 >= 5" },
  { value: "forget10", label: "忘记 >= 10" },
  { value: "highFrequency", label: "高频考研词" },
  { value: "missingChinese", label: "未标注中文" },
  { value: "missingFrequency", label: "未标注考频" },
];

export function FilterBar({ query, onQueryChange, filter, onFilterChange, resultCount }) {
  return (
    <div className="filter-bar">
      <label className="search-box">
        <Search size={18} aria-hidden="true" />
        <span className="sr-only">搜索英文单词</span>
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索英文单词"
          type="search"
        />
      </label>
      <div className="segmented" aria-label="筛选条件">
        {filters.map((item) => (
          <button
            key={item.value}
            className={filter === item.value ? "is-active" : ""}
            type="button"
            onClick={() => onFilterChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <span className="result-count">{resultCount} 条</span>
    </div>
  );
}

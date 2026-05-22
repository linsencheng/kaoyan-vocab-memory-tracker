const options = [
  { value: "priority", label: "综合优先级" },
  { value: "forget", label: "忘记次数" },
  { value: "frequency", label: "考研考频" },
  { value: "recent", label: "最近出现" },
  { value: "alphabetical", label: "字母序" },
];

export function SortControls({ value, onChange }) {
  return (
    <label className="sort-control">
      <span>排序</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

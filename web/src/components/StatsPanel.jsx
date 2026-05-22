const stats = [
  { key: "totalWords", label: "总词数" },
  { key: "totalForgetCount", label: "总遗忘次数" },
  { key: "highForgetWords", label: "高遗忘词" },
  { key: "highFrequencyWords", label: "高频考研词" },
  { key: "missingChinese", label: "未标注中文" },
  { key: "missingFrequency", label: "未标注考频" },
];

export function StatsPanel({ stats: values }) {
  return (
    <section className="stats-grid" aria-label="词库统计">
      {stats.map((item) => (
        <article className="stat-card" key={item.key}>
          <span>{item.label}</span>
          <strong>{values[item.key] ?? 0}</strong>
        </article>
      ))}
    </section>
  );
}

import { BookOpen, CalendarDays, FileSearch } from "lucide-react";

function EmptyValue({ children = "未标注" }) {
  return <span className="empty-value">{children}</span>;
}

export function VocabCard({ item }) {
  if (!item) {
    return (
      <section className="detail-panel empty-detail">
        <h2>单词详情</h2>
        <p>选择左侧词条后查看中文释义、易混词、例句和来源记录。</p>
      </section>
    );
  }

  return (
    <section className="detail-panel" aria-label={`${item.word} 详情`}>
      <div className="word-heading">
        <div>
          <p className="detail-kicker">当前词条</p>
          <h2>{item.word}</h2>
        </div>
        <span className={item.exam_frequency >= 4 ? "freq-pill high" : "freq-pill"}>
          {item.exam_frequency_label}
        </span>
      </div>

      <dl className="detail-metrics">
        <div>
          <dt>忘记次数</dt>
          <dd>{item.forget_count}</dd>
        </div>
        <div>
          <dt>考频分</dt>
          <dd>{item.exam_frequency}</dd>
        </div>
        <div>
          <dt>最近出现</dt>
          <dd>{item.last_seen}</dd>
        </div>
      </dl>

      <section className="detail-section">
        <div className="mini-heading">
          <BookOpen size={18} aria-hidden="true" />
          <h3>中文释义</h3>
        </div>
        <p className="chinese-text">{item.chinese?.trim() ? item.chinese : <EmptyValue />}</p>
      </section>

      <section className="detail-section">
        <h3>易混词</h3>
        {item.similar_words?.length ? (
          <div className="similar-list">
            {item.similar_words.map((similar) => (
              <article key={`${item.normalized_word}-${similar.word}`} className="similar-item">
                <strong>{similar.word}</strong>
                <span>{similar.chinese}</span>
                <p>{similar.difference}</p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyValue />
        )}
      </section>

      <section className="detail-section">
        <h3>例句</h3>
        {item.examples?.length ? (
          <div className="examples">
            {item.examples.map((example) => (
              <figure key={example.sentence}>
                <blockquote>{example.sentence}</blockquote>
                <figcaption>{example.translation}</figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <EmptyValue />
        )}
      </section>

      <section className="detail-section">
        <div className="mini-heading">
          <FileSearch size={18} aria-hidden="true" />
          <h3>来源记录</h3>
        </div>
        <div className="source-list">
          {item.sources.map((source, index) => (
            <div className="source-row" key={`${source.file}-${source.page}-${source.line_index ?? index}`}>
              <span>{source.file}</span>
              <span>第 {source.page} 页</span>
              <span>校对 {source.corrected_count ?? "空"}</span>
              <span>置信度 {source.confidence ?? "未标注"}</span>
            </div>
          ))}
        </div>
      </section>

      <p className="seen-line">
        <CalendarDays size={16} aria-hidden="true" />
        首次 {item.first_seen}，最近 {item.last_seen}
      </p>
    </section>
  );
}

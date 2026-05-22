import { FileText } from "lucide-react";

export function ImportGuide() {
  return (
    <section className="import-guide" aria-label="导入流程">
      <div className="mini-heading">
        <FileText size={18} aria-hidden="true" />
        <h2>导入流程</h2>
      </div>
      <ol>
        <li>PDF 或图片放入 <code>raw_notes/</code></li>
        <li><code>python scripts/import_pdf.py</code></li>
        <li>校对 <code>extracted/ocr/review_template.csv</code></li>
        <li><code>python scripts/merge_vocab.py</code></li>
        <li><code>python scripts/validate_data.py</code></li>
      </ol>
    </section>
  );
}

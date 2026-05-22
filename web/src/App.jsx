import { useEffect, useMemo, useState } from "react";
import { ImportGuide } from "./components/ImportGuide.jsx";
import { FilterBar } from "./components/FilterBar.jsx";
import { SortControls } from "./components/SortControls.jsx";
import { StatsPanel } from "./components/StatsPanel.jsx";
import { ThemeToggle } from "./components/ThemeToggle.jsx";
import { VocabCard } from "./components/VocabCard.jsx";
import { VocabTable } from "./components/VocabTable.jsx";
import { applyTheme, getInitialTheme } from "./utils/theme.js";
import { enrichVocab, filterVocab, getStats } from "./utils/vocab.js";
import { sortVocab } from "./utils/sort.js";

const baseUrl = import.meta.env.BASE_URL.endsWith("/")
  ? import.meta.env.BASE_URL
  : `${import.meta.env.BASE_URL}/`;

function dataUrl(fileName) {
  return `${baseUrl}data/${fileName}`;
}

export default function App() {
  const [themeMode, setThemeMode] = useState(getInitialTheme);
  const [vocab, setVocab] = useState([]);
  const [frequency, setFrequency] = useState({});
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sortKey, setSortKey] = useState("priority");
  const [selectedWord, setSelectedWord] = useState("");

  useEffect(() => {
    applyTheme(themeMode);
    if (themeMode !== "system") {
      return undefined;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [themeMode]);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        const [vocabResponse, frequencyResponse] = await Promise.all([
          fetch(dataUrl("vocab.json")),
          fetch(dataUrl("exam_frequency.json")),
        ]);
        if (!vocabResponse.ok) {
          throw new Error(`vocab.json 加载失败：${vocabResponse.status}`);
        }
        if (!frequencyResponse.ok) {
          throw new Error(`exam_frequency.json 加载失败：${frequencyResponse.status}`);
        }
        const [vocabJson, frequencyJson] = await Promise.all([
          vocabResponse.json(),
          frequencyResponse.json(),
        ]);
        if (!cancelled) {
          setVocab(Array.isArray(vocabJson) ? vocabJson : []);
          setFrequency(frequencyJson && typeof frequencyJson === "object" ? frequencyJson : {});
          setStatus("ready");
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message);
          setStatus("error");
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  const enriched = useMemo(() => enrichVocab(vocab, frequency), [vocab, frequency]);
  const visible = useMemo(() => {
    const filtered = filterVocab(enriched, { query, filter });
    return sortVocab(filtered, sortKey);
  }, [enriched, query, filter, sortKey]);
  const stats = useMemo(() => getStats(enriched), [enriched]);
  const selected = useMemo(() => {
    if (!visible.length) {
      return null;
    }
    return visible.find((item) => item.normalized_word === selectedWord) ?? visible[0];
  }, [visible, selectedWord]);

  useEffect(() => {
    if (selected && selected.normalized_word !== selectedWord) {
      setSelectedWord(selected.normalized_word);
    }
  }, [selected, selectedWord]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Kaoyan Vocab Memory Tracker</p>
          <h1>考研英语遗忘词汇追踪器</h1>
          <p className="subtitle">基于手写笔记的考研英语遗忘词复习系统。</p>
        </div>
        <ThemeToggle value={themeMode} onChange={setThemeMode} />
      </header>

      <main>
        {status === "error" ? (
          <section className="message-panel" role="alert">
            <strong>数据加载失败</strong>
            <span>{error}</span>
          </section>
        ) : null}

        <StatsPanel stats={stats} />

        <section className="control-strip" aria-label="搜索、筛选和排序">
          <FilterBar
            query={query}
            onQueryChange={setQuery}
            filter={filter}
            onFilterChange={setFilter}
            resultCount={visible.length}
          />
          <SortControls value={sortKey} onChange={setSortKey} />
        </section>

        <section className="workbench">
          <div className="table-panel">
            <div className="panel-heading">
              <div>
                <h2>词汇表</h2>
                <p>{status === "loading" ? "正在加载数据..." : `当前显示 ${visible.length} 个词条`}</p>
              </div>
            </div>
            <VocabTable
              items={visible}
              selectedWord={selected?.normalized_word}
              onSelect={(item) => setSelectedWord(item.normalized_word)}
            />
          </div>

          <aside className="side-stack">
            <VocabCard item={selected} />
            <ImportGuide />
          </aside>
        </section>
      </main>
    </div>
  );
}

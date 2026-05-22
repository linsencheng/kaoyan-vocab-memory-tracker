import { Monitor, Moon, Sun } from "lucide-react";

const modes = [
  { value: "system", label: "系统", icon: Monitor },
  { value: "light", label: "日用", icon: Sun },
  { value: "dark", label: "夜用", icon: Moon },
];

export function ThemeToggle({ value, onChange }) {
  const currentIndex = modes.findIndex((mode) => mode.value === value);
  const current = modes[currentIndex] ?? modes[0];
  const Icon = current.icon;

  function cycleTheme() {
    const next = modes[(Math.max(currentIndex, 0) + 1) % modes.length];
    onChange(next.value);
  }

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={cycleTheme}
      title={`当前：${current.label}。点击切换主题。`}
      aria-label={`当前主题：${current.label}。点击切换。`}
    >
      <Icon size={18} aria-hidden="true" />
      <span>{current.label}</span>
    </button>
  );
}

import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const dataDir = path.resolve(projectRoot, "data");
const outDir = path.resolve(__dirname, "dist");
const defaultBasePath = "./";

function normalizeBasePath(value = defaultBasePath) {
  const rawValue = value.trim();
  if (!rawValue || rawValue === "." || rawValue === "./") {
    return "./";
  }
  const withLeadingSlash = rawValue.startsWith("/") ? rawValue : `/${rawValue}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
}

const basePath = normalizeBasePath(process.env.VITE_BASE_PATH);

function resolveDataFile(rawUrl = "/") {
  const pathname = new URL(rawUrl, "http://local").pathname;
  const basePrefix = basePath === "./" ? "" : basePath.replace(/\/$/, "");
  const pathnameWithoutBase = basePrefix && pathname.startsWith(basePrefix)
    ? pathname.slice(basePrefix.length)
    : pathname;
  const relativePath = pathnameWithoutBase.replace(/^\/data\//, "").replace(/^\//, "");
  if (!relativePath || !relativePath.endsWith(".json")) {
    return null;
  }
  const target = path.resolve(dataDir, relativePath);
  const relative = path.relative(dataDir, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    return null;
  }
  return target;
}

function dataFilesPlugin() {
  return {
    name: "kaoyan-data-files",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const target = resolveDataFile(req.url);
        if (!target || !fs.existsSync(target)) {
          next();
          return;
        }
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        fs.createReadStream(target).pipe(res);
      });
    },
    writeBundle() {
      const targetDir = path.join(outDir, "data");
      fs.mkdirSync(targetDir, { recursive: true });
      for (const fileName of fs.readdirSync(dataDir)) {
        if (fileName.endsWith(".json")) {
          fs.copyFileSync(path.join(dataDir, fileName), path.join(targetDir, fileName));
        }
      }
    },
  };
}

export default defineConfig({
  root: __dirname,
  base: basePath,
  plugins: [react(), dataFilesPlugin()],
  build: {
    outDir,
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    fs: {
      allow: [projectRoot],
    },
  },
});

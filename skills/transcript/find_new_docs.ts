#!/usr/bin/env bun
/**
 * find_new_docs.ts
 * Incremental mode: lists images and PDFs in projects/<project>/imported/ that do NOT yet have
 * a corresponding JSON file in projects/<project>/metadata/ (same name, .json).
 * Does not change anything — only reports what needs to be processed.
 *
 * Usage: bun find_new_docs.ts [/path/to/project]
 * Or:  bun find_new_docs.ts (from within a project directory)
 * Output: list of pending documents (one per line) + count on stderr.
 *
 * Supported formats: .jpg, .jpeg, .png (images), .pdf (PDF documents)
 */
import { readdirSync, existsSync } from "fs";
import { resolve, dirname, join, parse } from "path";

const SKILL_DIR = dirname(new URL(import.meta.url).pathname);

// Auto-detect project path
let projectPath = process.argv[2];
if (!projectPath) {
  // Try current directory
  const cwd = process.cwd();
  if (existsSync(join(cwd, "docs_logical_map.json"))) {
    projectPath = cwd;
  } else {
    // Try parent directories
    for (let i = 0; i < 3; i++) {
      const p = resolve(cwd, ...Array(i).fill(".."));
      if (existsSync(join(p, "docs_logical_map.json"))) {
        projectPath = p;
        break;
      }
    }
  }
}

if (!projectPath) {
  console.error("Usage: bun find_new_docs.ts [/path/to/project]");
  console.error("Or run from within a project directory with docs_logical_map.json");
  process.exit(1);
}

const IMPORTED = resolve(projectPath, "imported");
const METADATA = resolve(projectPath, "metadata");

if (!existsSync(IMPORTED)) {
  console.error(`Error: imported directory not found at ${IMPORTED}`);
  process.exit(1);
}

if (!existsSync(METADATA)) {
  console.error(`Creating metadata directory at ${METADATA}`);
  Bun.spawnSync(["mkdir", "-p", METADATA]);
}

const exts = new Set([".jpg", ".jpeg", ".png", ".pdf"]);
const docs = readdirSync(IMPORTED).filter((f) => exts.has(parse(f).ext.toLowerCase()));
const novas = docs.filter((f) => !existsSync(join(METADATA, parse(f).name + ".json")));

for (const f of novas.sort()) console.log(f);
console.error(`Project: ${projectPath}`);
console.error(`Imported: ${docs.length} | Transcribed: ${docs.length - novas.length} | PENDING: ${novas.length}`);

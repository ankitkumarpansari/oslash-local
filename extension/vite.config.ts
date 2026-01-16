import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { resolve } from "path";
import { writeFileSync, mkdirSync, existsSync, rmSync } from "fs";

export default defineConfig({
  plugins: [
    preact(),
    {
      name: "fix-popup-html",
      closeBundle() {
        // Fix the popup HTML with correct paths
        const destDir = resolve(__dirname, "dist/popup");
        const destHtml = resolve(destDir, "index.html");
        
        if (!existsSync(destDir)) {
          mkdirSync(destDir, { recursive: true });
        }
        
        // Write correct HTML
        const html = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OSlash Local</title>
    <link rel="stylesheet" href="popup.css">
    <style>
      body {
        margin: 0;
        padding: 0;
        min-width: 320px;
      }
    </style>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="popup.js"></script>
  </body>
</html>`;
        
        writeFileSync(destHtml, html);
        console.log("Created popup/index.html");
        
        // Remove the src folder
        const srcDir = resolve(__dirname, "dist/src");
        if (existsSync(srcDir)) {
          rmSync(srcDir, { recursive: true });
          console.log("Removed dist/src");
        }
      },
    },
  ],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/index.html"),
        content: resolve(__dirname, "src/content/index.ts"),
        background: resolve(__dirname, "src/background/index.ts"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "content" || chunkInfo.name === "background") {
            return "[name].js";
          }
          return "popup/[name].js";
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith(".css")) {
            return "popup/[name][extname]";
          }
          return "[name][extname]";
        },
      },
    },
    minify: false,
    sourcemap: true,
  },
  publicDir: "public",
});

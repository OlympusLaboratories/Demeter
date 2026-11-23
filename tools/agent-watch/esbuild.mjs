import * as esbuild from 'esbuild';
import { run, webview } from '../esbuild.base.mjs';

await run(esbuild, [webview('src/webview/main.ts', 'dist/webview.js')]);

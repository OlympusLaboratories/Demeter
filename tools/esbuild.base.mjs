export const shared = {
  bundle: true,
  sourcemap: true,
  logLevel: 'info',
};

export const nodeExtension = {
  ...shared,
  entryPoints: ['src/extension.ts'],
  outfile: 'dist/extension.js',
  external: ['vscode'],
  format: 'cjs',
  platform: 'node',
  target: 'node20',
};

export function webview(entry, outfile) {
  return {
    ...shared,
    entryPoints: [entry],
    outfile,
    format: 'iife',
    platform: 'browser',
    target: 'es2022',
  };
}

export async function run(esbuild, extra = []) {
  const builds = [nodeExtension, ...extra];
  if (process.argv.includes('--watch')) {
    for (const options of builds) {
      const ctx = await esbuild.context(options);
      await ctx.watch();
    }
    return;
  }
  await Promise.all(builds.map((options) => esbuild.build(options)));
}

import resolve from '@rollup/plugin-node-resolve';
import esbuild from 'rollup-plugin-esbuild';
import serve from 'rollup-plugin-serve';
import json from '@rollup/plugin-json';

const onwarn = (warning, warn) => {
  if (warning.code === 'THIS_IS_UNDEFINED' && warning.id?.includes('/node_modules/')) {
    return;
  }

  warn(warning);
};

const plugins = [resolve(), esbuild({ target: 'es2022' }), json()];

export default [
  {
    // The card itself: add http://<this-machine>:5050/mare-tide-card.js as a dashboard resource.
    input: 'src/mare-tide-card.ts',
    output: { file: './dist/mare-tide-card.js', format: 'es', inlineDynamicImports: true },
    plugins,
    onwarn,
  },
  {
    // Stand-alone harness with a mock `hass`: open http://localhost:5050/
    input: 'dev/harness.ts',
    output: { file: './dist/harness.js', format: 'es', inlineDynamicImports: true },
    plugins: [
      ...plugins,
      serve({
        contentBase: ['./dist', './dev'],
        host: '0.0.0.0',
        // Not 5000: macOS uses it for AirPlay Receiver.
        port: Number(process.env.PORT) || 5050,
        allowCrossOrigin: true,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
          Expires: '0',
        },
      }),
    ],
    onwarn,
  },
];

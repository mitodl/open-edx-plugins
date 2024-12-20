import typescript from '@rollup/plugin-typescript';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import replace from '@rollup/plugin-replace';
import json from '@rollup/plugin-json';
import { transform as intlTransform } from '@formatjs/ts-transformer';

export default {
  output: {
    dir: '../static',
    format: 'iife',
  },
  plugins: [
    json(),
    typescript({
      // Configure a transformer to automatically add message IDs to <FormattedMessage /> and other react-intl usages
      transformers: () => ({
        before: [intlTransform({ overrideIdFn: '[sha512:contenthash:base64:6]', ast: true })],
      }),
    }),
    replace({
      'process.env.NODE_ENV': JSON.stringify('production'),
      preventAssignment: true,
    }),
    commonjs(),
    nodeResolve(),
  ]
};

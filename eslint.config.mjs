// @ts-check

import angular from 'angular-eslint';
import oxlint from 'eslint-plugin-oxlint';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig(
  globalIgnores(['app/**', 'tests/unit/**', 'docs/**', 'local/**']),
  { linterOptions: { reportUnusedDisableDirectives: 'error' } },

  // Oxlint desativa regras duplicadas no ESLint
  oxlint.configs['flat/recommended'],

  // Regras de componentes Angular (.ts)
  {
    files: ['**/*.ts'],
    extends: [...angular.configs.tsRecommended],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: 'app', style: 'camelCase' },
      ],
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: 'app', style: 'kebab-case' },
      ],
      '@angular-eslint/prefer-standalone': 'error',
      '@angular-eslint/prefer-inject': 'error',
      '@angular-eslint/inject-at-top': 'error',
      '@angular-eslint/prefer-signals': 'error',
      '@angular-eslint/prefer-signal-model': 'error',
      '@angular-eslint/prefer-output-readonly': 'error',
      '@angular-eslint/no-uncalled-signals': 'error',
      '@angular-eslint/computed-must-return': 'error',
      '@angular-eslint/use-lifecycle-interface': 'error',
      '@angular-eslint/component-class-suffix': 'error',
      '@angular-eslint/directive-class-suffix': 'error',
      '@angular-eslint/prefer-on-push-component-change-detection': 'error',
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@angular/common',
              importNames: ['NgClass', 'NgStyle'],
              message: 'Use [class.x] and [style.x] bindings instead of NgClass and NgStyle.',
            },
          ],
        },
      ],
    },
  },

  // Regras de templates Angular (.html) - exclusividade do ESLint
  {
    files: ['**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
    rules: {
      '@angular-eslint/template/prefer-control-flow': 'error',
      '@angular-eslint/template/prefer-class-binding': 'error',
      '@angular-eslint/template/prefer-style-binding': 'error',
      '@angular-eslint/template/prefer-at-else': 'error',
      '@angular-eslint/template/prefer-at-empty': 'error',
      '@angular-eslint/template/prefer-self-closing-tags': 'error',
      '@angular-eslint/template/no-inline-styles': 'error',
    },
  },
);

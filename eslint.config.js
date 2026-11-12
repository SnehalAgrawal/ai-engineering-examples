// ESLint configuration for every JavaScript demo in this repository.
// Run from the repository root: npm run lint:js
import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["**/node_modules/**"] },
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: globals.node,
    },
    rules: {
      // Unused variables are almost always a mistake; a leading underscore marks an intentional one.
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none" }],
    },
  },
];

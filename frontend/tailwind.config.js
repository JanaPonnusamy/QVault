/** Tailwind for the Knowledge Research module's copied components only.
 * preflight is disabled so Tailwind adds NO global resets — Bootstrap 5
 * styling of all existing pages is untouched; only utility classes apply. */
export default {
  content: [
    "./src/pages/KnowledgeResearch*.tsx",
    "./src/components/knowledge-research/**/*.tsx",
  ],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
};

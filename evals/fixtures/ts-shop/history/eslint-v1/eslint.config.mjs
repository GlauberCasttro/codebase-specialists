// Flat config (ESLint 9). Two rules here encode architecture decisions:
//  - apps/web never imports @shop/api (ADR 0001): contracts live in @shop/shared.
//  - no enums / namespaces / parameter properties: node runs the api's .ts files with
//    type stripping, which only supports erasable syntax (see the 2025-05 boot crash).
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "**/node_modules/**", "**/test/fixtures/**"] },
  ...tseslint.configs.recommended,
  {
    rules: {
      "no-restricted-syntax": [
        "error",
        { selector: "TSEnumDeclaration", message: "Use a string-literal union; enums are not erasable." },
        { selector: "TSModuleDeclaration[kind='namespace']", message: "Namespaces are not erasable." },
        { selector: "TSParameterProperty", message: "Parameter properties are not erasable." }
      ],
      "@typescript-eslint/consistent-type-imports": "error"
    }
  }
);

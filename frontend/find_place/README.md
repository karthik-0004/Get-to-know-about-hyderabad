# React + Vite

## Google Maps Setup (Production)

If you see "This page can't load Google Maps correctly", the issue is usually key restrictions or billing in Google Cloud, not React code.

1. In Google Cloud Console, enable APIs for the same project as your key:
	- Maps JavaScript API
	- Places API
2. Ensure Billing is enabled for that project.
3. In API Keys, open the key used by `VITE_GOOGLE_MAPS_API_KEY` and configure:
	- Application restrictions: `HTTP referrers (web sites)`
	- Allowed referrers (example):
	  - `http://localhost:5173/*`
	  - `https://your-vercel-domain.vercel.app/*`
	  - `https://your-custom-domain.com/*`
4. In Vercel Project Settings -> Environment Variables, set:
	- `VITE_GOOGLE_MAPS_API_KEY=<your_maps_key>`
5. Redeploy after changing env vars.

Notes:
- Vite only injects variables prefixed with `VITE_`.
- Frontend keys are public by design; secure them with referrer restrictions and API restrictions.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

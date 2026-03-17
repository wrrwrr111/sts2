// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import fs from 'node:fs';
import path from 'node:path';

const parseEnvFile = (filePath) => {
	const out = {};
	if (!fs.existsSync(filePath)) return out;

	const text = fs.readFileSync(filePath, 'utf8');
	for (const rawLine of text.split(/\r?\n/)) {
		const line = rawLine.trim();
		if (!line || line.startsWith('#')) continue;

		const normalized = line.startsWith('export ') ? line.slice(7).trim() : line;
		const idx = normalized.indexOf('=');
		if (idx <= 0) continue;

		const key = normalized.slice(0, idx).trim();
		let value = normalized.slice(idx + 1).trim();
		if (
			(value.startsWith('"') && value.endsWith('"')) ||
			(value.startsWith("'") && value.endsWith("'"))
		) {
			value = value.slice(1, -1);
		}
		out[key] = value;
	}
	return out;
};

const envFromFile = {
	...parseEnvFile(path.join(process.cwd(), '.env')),
	...parseEnvFile(path.join(process.cwd(), '.env.local')),
};

const voteApiProxyTarget = (
	process.env.VOTE_API_PROXY_TARGET ?? envFromFile.VOTE_API_PROXY_TARGET
)?.trim();

// https://astro.build/config
export default defineConfig({
	integrations: [tailwind()],
	site: 'https://wrrwrr111.github.io',
	base: '/',
	vite: {
		server: {
			proxy: voteApiProxyTarget
				? {
						'/api': {
							target: voteApiProxyTarget,
							changeOrigin: true,
							secure: false,
						},
				  }
				: undefined,
		},
	},
});

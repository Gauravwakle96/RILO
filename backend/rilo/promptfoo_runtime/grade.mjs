// Rilo adapter to the actual MIT-licensed Promptfoo assertion engine.
// No user code, provider, template, or arbitrary Promptfoo configuration is loaded.
import './network_guard.mjs';
import { readFileSync } from 'node:fs';

const stdout = process.stdout.write.bind(process.stdout);
// Package logging must not contaminate the bounded JSON protocol or print source text.
console.log = console.info = console.warn = console.error = () => {};
process.stdout.write = () => true;
process.stderr.write = () => true;

try {
  const bytes = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 250000) throw new Error('Grading input is too large');
    bytes.push(chunk);
  }
  const input = JSON.parse(Buffer.concat(bytes).toString('utf8'));
  if (!Array.isArray(input.checks) || input.checks.length > 12) throw new Error('Invalid checks');
  const allowed = new Set(['equals', 'contains', 'icontains', 'not-contains', 'not-icontains', 'is-json']);
  const ids = new Set();
  for (const check of input.checks) {
    if (!allowed.has(check.type) || !['summary', 'response'].includes(check.target) ||
        typeof check.id !== 'string' || ids.has(check.id) ||
        (check.type !== 'is-json' && (typeof check.value !== 'string' || !check.value.trim() || check.value.length > 2000)) ||
        (check.type === 'is-json' && check.value != null) ||
        (typeof check.value === 'string' && /^(file:\/\/|package:)/i.test(check.value.trim()))) {
      throw new Error('Only bounded literal checks are accepted');
    }
    ids.add(check.id);
  }
  const version = JSON.parse(readFileSync(new URL('./node_modules/promptfoo/package.json', import.meta.url))).version;
  if (version !== '0.125.1') throw new Error('Promptfoo version does not match the pinned runtime');
  const { assertions } = await import('promptfoo');
  const results = [];
  for (const check of input.checks) {
    const output = check.target === 'summary' ? input.output.summary : JSON.stringify(input.output);
    if (typeof output !== 'string') throw new Error('No stored output to grade');
    const assertion = { type: check.type, metric: check.id };
    if (check.type !== 'is-json') assertion.value = check.value;
    const result = await assertions.runAssertions({
      test: { assert: [assertion] }, providerResponse: { output },
    });
    if (typeof result.pass !== 'boolean' || !Number.isFinite(result.score)) throw new Error('Invalid grader result');
    results.push({ id: check.id, passed: result.pass, score: result.score, reason: String(result.reason).slice(0, 4000) });
  }
  stdout(JSON.stringify({ version, checks: results }));
  process.exit(0);
} catch {
  stdout(JSON.stringify({ error: 'Promptfoo could not grade the stored answer. See runtime setup and supported checks.' }));
  process.exit(1);
}

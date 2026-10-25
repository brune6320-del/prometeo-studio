/* Comprueba el adaptador contra código real de Studio, sin modificar el frontend.
 * Uso: node test_tablero.cjs ruta/tablero.json [ruta/al/typescript.js]
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require(process.argv[3] || path.resolve(__dirname, '../../studio/frontend/node_modules/typescript'));
const cache = new Map();
function cargar(fichero) {
  if (cache.has(fichero)) return cache.get(fichero).exports;
  const mod = {exports: {}};
  cache.set(fichero, mod);
  const fuente = fs.readFileSync(fichero, 'utf8');
  const js = ts.transpileModule(fuente, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  const fn = vm.runInThisContext(`(function(require,module,exports){${js}\n})`, {filename: fichero});
  fn(nombre => cargar(path.resolve(path.dirname(fichero), nombre + '.ts')), mod, mod.exports);
  return mod.exports;
}
const {normalizeBoard} = cargar(path.resolve(__dirname, '../../studio/frontend/src/board/model.ts'));
const entrada = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
assert.equal(entrada.format, 'prometeo-studio-board');
const normalizado = normalizeBoard(entrada.board);
assert.ok(normalizado);
assert.deepEqual(normalizado, entrada.board, 'El normalizador no debe eliminar ni alterar tarjetas, PNG o marco');
assert.equal(normalizado.cards[0].datos.vista, 'mesa');
assert.equal(normalizado.cards[0].datos.hijos.length, normalizado.cards.length - 1);
console.log(`OK: ${normalizado.cards.length - 1} piezas conservadas por normalizeBoard de Studio.`);

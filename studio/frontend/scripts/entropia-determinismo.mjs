#!/usr/bin/env node
/** Comprueba que dos lotes con la misma semilla producen archivos idénticos (SHA-256). */
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(__dirname, '..');
const SCRIPT = path.join(__dirname, 'entropia.mjs');
const raiz = fs.mkdtempSync(path.join(os.tmpdir(), 'prometeo-entropia-det-'));

function hashArchivo(ruta) {
  return crypto.createHash('sha256').update(fs.readFileSync(ruta)).digest('hex');
}

function generar(salida) {
  const resultado = spawnSync(process.execPath, [SCRIPT, '--n', '2', '--semilla', 'determinismo', '--salida', salida], {
    cwd: FRONTEND,
    encoding: 'utf8',
  });
  if (resultado.status !== 0) {
    process.stderr.write(resultado.stdout || '');
    process.stderr.write(resultado.stderr || '');
    throw new Error(`El lote falló con código ${resultado.status}.`);
  }
}

try {
  const primero = path.join(raiz, 'a');
  const segundo = path.join(raiz, 'b');
  generar(primero);
  generar(segundo);

  const nombres = (directorio) => fs.readdirSync(directorio).filter((nombre) => !nombre.startsWith('.')).sort();
  const a = nombres(primero);
  const b = nombres(segundo);
  if (a.join('\n') !== b.join('\n')) throw new Error(`Los lotes no tienen los mismos archivos.\nA: ${a.join(', ')}\nB: ${b.join(', ')}`);

  const diferencias = [];
  for (const nombre of a) {
    const ha = hashArchivo(path.join(primero, nombre));
    const hb = hashArchivo(path.join(segundo, nombre));
    if (ha !== hb) diferencias.push(`${nombre}: ${ha} ≠ ${hb}`);
  }
  if (diferencias.length) throw new Error(`Archivos distintos con la misma semilla:\n${diferencias.join('\n')}`);
  console.log(`OK · misma semilla, ${a.length} archivos idénticos (PNG, index.html y manifest.json).`);
  fs.rmSync(raiz, { recursive: true, force: true });
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error(`Los lotes quedaron en ${raiz} para inspeccionarlos.`);
  process.exitCode = 1;
}

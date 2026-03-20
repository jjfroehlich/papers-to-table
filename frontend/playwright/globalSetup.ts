import type { FullConfig } from '@playwright/test'
import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, type ChildProcess } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(__dirname, '..', '..')
const runtimeDir = join(repoRoot, '.playwright-runtime')
const statePath = join(runtimeDir, 'e2e-state.json')
const outputRoot = join(repoRoot, 'artifacts', 'e2e')
const backendUrl = 'http://127.0.0.1:8000/api/runs'
const frontendUrl = 'http://127.0.0.1:4173'
const pythonCommand = process.env.PYTHON ?? 'python'
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm'

type ManagedProcess = {
  name: string
  pid: number
  logPath: string
}

function ensureRuntimeDir(): void {
  rmSync(runtimeDir, { recursive: true, force: true })
  mkdirSync(runtimeDir, { recursive: true })
}

function writeState(processes: ManagedProcess[]): void {
  writeFileSync(statePath, JSON.stringify({ processes }, null, 2))
}

function spawnManagedProcess(name: string, command: string, args: string[], cwd: string, extraEnv: Record<string, string> = {}): ChildProcess {
  const logPath = join(runtimeDir, `${name}.log`)
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...extraEnv },
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: process.platform !== 'win32',
  })

  const append = (chunk: Buffer) => {
    const line = chunk.toString()
    writeFileSync(logPath, line, { flag: 'a' })
  }
  child.stdout?.on('data', append)
  child.stderr?.on('data', append)

  if (child.pid == null) {
    throw new Error(`E2E harness startup failed before ${name} reported a PID.`)
  }

  const existing = readState()
  existing.push({ name, pid: child.pid, logPath })
  writeState(existing)
  child.unref()
  return child
}

function readState(): ManagedProcess[] {
  try {
    return JSON.parse(readFileSync(statePath, 'utf8')).processes as ManagedProcess[]
  } catch {
    return []
  }
}

async function waitForHttpReady(name: string, url: string, child: ChildProcess, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`${name} exited during startup. See ${join('.playwright-runtime', `${name}.log`)} for details.`)
    }
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // keep polling until timeout
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 250))
  }
  throw new Error(`${name} did not become ready within ${timeoutMs}ms. See ${join('.playwright-runtime', `${name}.log`)} for details.`)
}

async function assertBrowserRuntime(): Promise<void> {
  try {
    const browser = await chromium.launch({ headless: true })
    await browser.close()
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    throw new Error(
      'Playwright browser runtime is unavailable. Install Chromium with `cd frontend && npx playwright install chromium` and ensure the host has the required browser libraries. ' +
      `Original error: ${detail}`
    )
  }
}

async function prepareFixtureRun(): Promise<void> {
  await new Promise<void>((resolvePromise, rejectPromise) => {
    const child = spawn(pythonCommand, ['scripts/prepare_e2e_fixture_run.py', '--output-root', outputRoot], {
      cwd: repoRoot,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const stdout: Buffer[] = []
    const stderr: Buffer[] = []
    child.stdout?.on('data', (chunk) => stdout.push(chunk))
    child.stderr?.on('data', (chunk) => stderr.push(chunk))
    child.on('exit', (code) => {
      if (code === 0) {
        resolvePromise()
        return
      }
      rejectPromise(new Error(
        'Fixture preparation failed before e2e startup. ' +
        `stdout: ${Buffer.concat(stdout).toString()} stderr: ${Buffer.concat(stderr).toString()}`
      ))
    })
    child.on('error', (error) => {
      rejectPromise(new Error(`Fixture preparation could not start: ${error.message}`))
    })
  })
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  ensureRuntimeDir()
  writeState([])

  await assertBrowserRuntime()
  await prepareFixtureRun()

  const backend = spawnManagedProcess(
    'backend',
    pythonCommand,
    ['-m', 'uvicorn', 'backend.app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000'],
    repoRoot,
    { PAPER_TABLE_AGENT_OUTPUT_ROOT: outputRoot },
  )
  await waitForHttpReady('backend', backendUrl, backend, 30_000)

  const frontend = spawnManagedProcess(
    'frontend',
    npmCommand,
    ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '4173'],
    join(repoRoot, 'frontend'),
  )
  await waitForHttpReady('frontend', frontendUrl, frontend, 30_000)
}

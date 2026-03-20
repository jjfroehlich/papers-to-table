import { existsSync, readFileSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(__dirname, '..', '..')
const runtimeDir = join(repoRoot, '.playwright-runtime')
const statePath = join(runtimeDir, 'e2e-state.json')

type ManagedProcess = {
  name: string
  pid: number
  logPath: string
}

function killProcessTree(pid: number): void {
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' })
    return
  }

  try {
    process.kill(-pid, 'SIGTERM')
  } catch {
    try {
      process.kill(pid, 'SIGTERM')
    } catch {
      // already exited
    }
  }
}

export default async function globalTeardown(): Promise<void> {
  if (!existsSync(statePath)) return

  const state = JSON.parse(readFileSync(statePath, 'utf8')) as { processes?: ManagedProcess[] }
  for (const processState of state.processes ?? []) {
    killProcessTree(processState.pid)
  }

  rmSync(runtimeDir, { recursive: true, force: true })
}

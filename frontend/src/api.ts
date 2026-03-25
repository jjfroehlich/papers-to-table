import type { InputSummary, RunRecord, RunSummary } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Request failed with ${response.status}`)
  }

  return (await response.json()) as T
}

export async function createRun(configPath: string): Promise<{ run_id: string }> {
  return request('/api/runs', {
    method: 'POST',
    body: JSON.stringify({ config_path: configPath }),
  })
}

export async function listRuns(): Promise<RunRecord[]> {
  return request('/api/runs')
}

export async function getRunSummary(runId: string): Promise<RunSummary> {
  return request(`/api/runs/${runId}/summary`)
}

export async function getInputSummary(runId: string): Promise<InputSummary> {
  return request(`/api/runs/${runId}/input-summary`)
}

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RunDetail } from './RunDetail'
import type { RunData } from '../types'

const baseRun: RunData = {
  run_id: 'run_20240315_143022_abc123',
  status: 'completed',
  config_path: 'config.json',
  table_path: 'tests/fixtures/tables/literature_fixture.xlsx',
  schema_path: 'tests/fixtures/tables/schema.csv',
  pdf_dir: 'tests/fixtures/papers',
  output_dir: './runs',
  verify_mode: false,
  eval_mode: false,
  run_mode: 'normal',
  provider_token: 'lm_studio',
  provider_locality: 'local',
  provider_mode: 'unavailable',
  provider_text_model_id: 'text-model',
  provider_vision_model_id: null,
  provider_readiness_error: 'provider offline',
  prompt_hash: 'prompt-hash',
  config_hash: 'config-hash',
  schema_hash: 'schema-hash',
  parser_identity: 'docling',
  started_at: null,
  completed_at: null,
  current_stage: null,
  total_rows: 10,
  eligible_cells: 50,
  proposals_generated: 0,
  proposals_reviewed: 0,
  warnings: [],
  error_message: null,
  created_at: '2024-03-15T14:30:22Z',
}

describe('RunDetail', () => {
  it('shows run id', () => {
    render(<RunDetail run={baseRun} />)
    expect(screen.getByText('run_20240315_143022_abc123')).toBeTruthy()
  })

  it('shows LM Studio display name for lm_studio token', () => {
    render(<RunDetail run={baseRun} />)
    expect(screen.getByText('LM Studio')).toBeTruthy()
  })

  it('shows provider mode and model truth', () => {
    render(<RunDetail run={baseRun} />)
    expect(screen.getByText('unavailable')).toBeTruthy()
    expect(screen.getByText('text-model')).toBeTruthy()
  })

  it('shows error message when failed', () => {
    const failedRun = { ...baseRun, status: 'failed' as const, error_message: 'Cannot reach LM Studio' }
    render(<RunDetail run={failedRun} />)
    expect(screen.getByText('Cannot reach LM Studio')).toBeTruthy()
    expect(screen.getByText(/Run failed/)).toBeTruthy()
  })

  it('shows warnings when present', () => {
    const runWithWarnings = {
      ...baseRun,
      status: 'completed_with_warnings' as const,
      warnings: [{ category: 'unmatched_pdf', message: 'unmatched_1.pdf was not matched' }],
    }
    render(<RunDetail run={runWithWarnings} />)
    expect(screen.getByText('unmatched_1.pdf was not matched')).toBeTruthy()
  })

  it('shows verify mode status', () => {
    const verifyRun = { ...baseRun, verify_mode: true, run_mode: 'verify' as const }
    render(<RunDetail run={verifyRun} />)
    expect(screen.getByText('Yes')).toBeTruthy()
  })

  it('shows eval mode artifact truth', () => {
    const evalRun = {
      ...baseRun,
      eval_mode: true,
      run_mode: 'eval' as const,
      eval_artifacts: {
        gold_table: {
          source_reference: '/tmp/gold.xlsx',
          snapshot_path: 'inputs/gold_table.xlsx',
        },
        masked_working_table: {
          path: 'inputs/masked_working_table.xlsx',
        },
      },
    }
    render(<RunDetail run={evalRun} />)
    expect(screen.getByText('eval')).toBeTruthy()
    expect(screen.getByText('/tmp/gold.xlsx')).toBeTruthy()
    expect(screen.getByText('inputs/masked_working_table.xlsx')).toBeTruthy()
  })

  it('shows current stage when running', () => {
    const runningRun = { ...baseRun, status: 'running' as const, current_stage: 'load_inputs' }
    render(<RunDetail run={runningRun} />)
    expect(screen.getByText(/load_inputs/)).toBeTruthy()
  })
})

/**
 * T095 — Playwright e2e test for the core review loop.
 *
 * Tests the happy path from proposal selection through decision recording
 * and summary updates. Uses mocked API responses via route interception
 * since real backend pipelines are not available in e2e.
 */
import { expect, test } from '@playwright/test'

// Minimal fixture data for e2e mocking
const RUN_ID = 'run-e2e-01'
const PROPOSAL_ID = 'prop-e2e-01'

const mockRunRecord = {
  run_id: RUN_ID,
  status: 'completed',
  operator_status: 'completed',
  config_path: '/tmp/config.json',
  artifact_dir: `/tmp/runs/${RUN_ID}`,
  message: null,
  progress: { stage: null, item: null },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const mockRunSummary = {
  run_id: RUN_ID,
  status: 'completed',
  operator_status: 'completed',
  message: null,
  progress: { stage: null, item: null },
  config_path: '/tmp/config.json',
  artifact_dir: `/tmp/runs/${RUN_ID}`,
  verify_mode: false,
  table_path: '/tmp/table.xlsx',
  schema_path: '/tmp/schema.csv',
  pdf_dir: '/tmp/pdfs',
  output_dir: '/tmp/runs',
  target_columns: ['Sample size'],
  provider_name: 'LMStudio',
  model_name: 'mistral',
  provider_locality: 'local',
}

const mockProposals = [
  {
    proposal_id: PROPOSAL_ID,
    run_id: RUN_ID,
    pdf_id: 'pdf-1',
    row_id: 'row-1',
    column_name: 'Sample size',
    cell_id: 'cell-1',
    source_mode: 'text',
    proposal_state: 'actionable',
    support_label: 'moderate_evidence',
    proposed_value: '42',
    status_flags: [],
    latest_decision: 'undecided',
  },
]

const mockProposalDetail = {
  proposal_id: PROPOSAL_ID,
  run_id: RUN_ID,
  pdf_id: 'pdf-1',
  row_id: 'row-1',
  column_name: 'Sample size',
  cell_id: 'cell-1',
  source_mode: 'text',
  proposal_state: 'actionable',
  support_label: 'moderate_evidence',
  proposed_value: '42',
  rationale: 'The study enrolled 42 participants.',
  calculation: null,
  needs_more_evidence: false,
  status_flags: [],
  row_context: { row_id: 'row-1', Author: 'Smith 2020' },
  column_definition: { column_name: 'Sample size', description: 'Number of participants' },
  current_cell_value: null,
  evidence: [
    {
      evidence_id: 'ev-1',
      proposal_id: PROPOSAL_ID,
      pdf_id: 'pdf-1',
      source_type: 'text_quote',
      page: 3,
      quote_text: 'The study enrolled 42 participants.',
      highlight: null,
      figure_ref: null,
      caption_text: null,
      crop_path: null,
      full_page_path: null,
      anchor_confidence: 0.85,
    },
  ],
  latest_decision: 'undecided',
  latest_decision_record: null,
}

const mockDecisionRecord = {
  decision_id: 'dec-1',
  run_id: RUN_ID,
  proposal_id: PROPOSAL_ID,
  cell_id: 'cell-1',
  decision: 'accept',
  edited_value: null,
  decided_at: new Date().toISOString(),
}

const mockProgress = { total: 1, accepted_as_is: 0, accepted_with_edit: 0, rejected: 0, pending: 1 }
const mockProgressAfterAccept = { total: 1, accepted_as_is: 1, accepted_with_edit: 0, rejected: 0, pending: 0 }

test.describe('Review workspace e2e loop (T095)', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept API calls to return fixture data
    await page.route('**/api/runs', async (route) => {
      await route.fulfill({ json: [mockRunRecord] })
    })

    await page.route(`**/api/runs/${RUN_ID}/summary`, async (route) => {
      await route.fulfill({ json: mockRunSummary })
    })

    await page.route(`**/api/runs/${RUN_ID}/input-summary`, async (route) => {
      await route.fulfill({ status: 404, json: { detail: 'not found' } })
    })

    await page.route(`**/api/runs/${RUN_ID}/proposals`, async (route) => {
      await route.fulfill({ json: mockProposals })
    })

    await page.route(`**/api/runs/${RUN_ID}/proposals/${PROPOSAL_ID}`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: mockProposalDetail })
      } else {
        await route.fulfill({ json: mockProposalDetail })
      }
    })

    let decisionCount = 0
    await page.route(`**/api/runs/${RUN_ID}/proposals/${PROPOSAL_ID}/decision`, async (route) => {
      decisionCount++
      await route.fulfill({ json: mockDecisionRecord })
    })

    await page.route(`**/api/runs/${RUN_ID}/progress`, async (route) => {
      await route.fulfill({ json: decisionCount > 0 ? mockProgressAfterAccept : mockProgress })
    })

    await page.route(`**/api/runs/${RUN_ID}/matching/summary`, async (route) => {
      await route.fulfill({ json: { total: 1, matched: 1, unresolved: 0 } })
    })

    await page.route(`**/api/runs/${RUN_ID}/matching/unresolved`, async (route) => {
      await route.fulfill({ json: [] })
    })

    await page.route(`**/api/runs/${RUN_ID}/summaries/run`, async (route) => {
      await route.fulfill({ status: 404, json: { detail: 'not found' } })
    })

    await page.route(`**/api/runs/${RUN_ID}/summaries/reviewer`, async (route) => {
      await route.fulfill({ status: 404, json: { detail: 'not found' } })
    })

    await page.route(`**/api/runs/${RUN_ID}/downloads/available`, async (route) => {
      await route.fulfill({ json: { run_summary: false, reviewer_summary: false, workbook: false, audit_log: false } })
    })

    await page.goto('/')
  })

  test('shows run launch guidance on load', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Paper Table Agent' })).toBeVisible()
    await expect(page.getByText('Start run from config file')).toBeVisible()
  })

  test('run appears in run list and shows completed status', async ({ page }) => {
    await expect(page.getByText(/completed/)).toBeVisible()
  })

  test('review tab becomes active and shows review workspace for completed run', async ({ page }) => {
    // Click the Review tab
    await page.getByRole('button', { name: /Review/ }).click()
    // Should show the review workspace (not pre-review guidance)
    await expect(page.getByText('Review queue')).toBeVisible()
    await expect(page.getByText('Run summary')).toBeVisible()
    await expect(page.getByText('Unresolved')).toBeVisible()
  })

  test('proposal appears in queue after navigating to review', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText('Sample size')).toBeVisible()
    await expect(page.getByText(/1 pending/)).toBeVisible()
  })

  test('selecting a proposal shows detail and evidence', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()

    // Wait for queue to load
    await expect(page.getByText('Sample size')).toBeVisible()

    // Click the proposal in the queue
    const listbox = page.getByRole('listbox', { name: 'Proposals' })
    await listbox.getByRole('option').first().click()

    // Proposal detail should appear
    await expect(page.getByText('42')).toBeVisible() // proposed value
    await expect(page.getByText('The study enrolled 42 participants.')).toBeVisible() // rationale or evidence

    // Evidence pane should show quote fallback (no highlight coords)
    await expect(page.getByText(/No highlight coordinates/)).toBeVisible()
    await expect(page.getByText(/Page 3/)).toBeVisible()
  })

  test('accept action records a decision', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText('Sample size')).toBeVisible()

    // Select first proposal
    const listbox = page.getByRole('listbox', { name: 'Proposals' })
    await listbox.getByRole('option').first().click()

    // Wait for detail to load
    await expect(page.getByLabelText('Accept')).toBeVisible()

    // Click Accept
    await page.getByLabel('Accept').click()

    // Decision should be recorded (button click triggers API call)
    // After accepting, the decision badge should update
    await expect(page.getByTitle('accept')).toBeVisible({ timeout: 5000 })
  })

  test('reject action records a decision', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText('Sample size')).toBeVisible()

    const listbox = page.getByRole('listbox', { name: 'Proposals' })
    await listbox.getByRole('option').first().click()

    await expect(page.getByLabelText('Reject')).toBeVisible()
    await page.getByLabel('Reject').click()

    await expect(page.getByTitle('reject')).toBeVisible({ timeout: 5000 })
  })

  test('run summary tab shows summary panel', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await page.getByRole('tab', { name: 'Run summary' }).click()

    // Shows not-yet-available message when summaries aren't written yet
    await expect(page.getByText(/not yet available/)).toBeVisible()
  })

  test('unresolved tab shows no unresolved items for this run', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await page.getByRole('tab', { name: 'Unresolved' }).click()
    await expect(page.getByText(/No unmatched/)).toBeVisible()
  })

  test('keyboard shortcut n navigates to next in queue', async ({ page }) => {
    // With only one item in queue, this is a smoke test
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText('Sample size')).toBeVisible()

    const listbox = page.getByRole('listbox', { name: 'Proposals' })
    await listbox.getByRole('option').first().click()

    // Press 'n' to go next (only 1 item, so stays)
    await page.keyboard.press('n')
    // Should still show the same proposal
    await expect(page.getByText('Sample size')).toBeVisible()
  })

  test('provider and model info shown in context bar', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText(/LMStudio.*mistral/)).toBeVisible()
  })

  test('verify mode shown in context bar', async ({ page }) => {
    await page.getByRole('button', { name: /Review/ }).click()
    await expect(page.getByText(/Verify mode/)).toBeVisible()
    await expect(page.getByText('Off')).toBeVisible() // verify_mode: false
  })
})

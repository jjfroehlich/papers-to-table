import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

async function globalSetup() {
  const fixtureDir = path.resolve(__dirname, '../fixtures')
  await fs.mkdir(fixtureDir, { recursive: true })
  const markerPath = path.join(fixtureDir, 'prepared.json')

  await fs.writeFile(
    markerPath,
    JSON.stringify({ preparedAt: new Date().toISOString(), purpose: 'playwright fixture prep before server startup' }, null, 2),
    'utf-8',
  )
}

export default globalSetup
